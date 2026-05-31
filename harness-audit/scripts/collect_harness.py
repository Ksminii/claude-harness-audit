#!/usr/bin/env python3
"""Collect a token-efficient snapshot of a Claude Code harness.

Walks the global (~/.claude) and project (./.claude, ./CLAUDE.md) configuration
and emits a compact JSON snapshot: CLAUDE.md metrics, settings.json contents,
per-skill frontmatter + hygiene metrics, plugin enable/install sync, and agents.

The point is to let the analyzing Claude reason over metrics and extracted
frontmatter instead of reading dozens of full files. Read the full file ONLY
when the snapshot flags something worth a closer look.

Usage:
    collect_harness.py [--global-dir ~/.claude] [--project-dir .] [--pretty]

Output: JSON on stdout.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

WORD_RE = re.compile(r"\S+")
# Files that don't belong inside a skill (skill-creator: no auxiliary docs).
EXTRANEOUS_SKILL_FILES = {
    "readme.md", "readme", "installation_guide.md", "quick_reference.md",
    "changelog.md", "contributing.md", "license", "license.md", ".ds_store",
}
# Phrases that suggest "when to use" guidance lives in the body instead of the
# description (where the trigger actually belongs).
WHEN_TO_USE_BODY_RE = re.compile(
    r"^#+\s*(when to use|when should|usage|use this skill when)", re.IGNORECASE | re.MULTILINE
)


def count_text(path: Path):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"error": str(e)}
    lines = text.splitlines()
    return {
        "lines": len(lines),
        "words": len(WORD_RE.findall(text)),
        "bytes": len(text.encode("utf-8")),
    }


def parse_frontmatter(text: str):
    """Return (frontmatter_dict_or_raw, body) from a SKILL.md-style file."""
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    raw = text[3:end].strip()
    body = text[end + 4:]
    # Lightweight YAML: only top-level "key: value" and "key: |" block scalars.
    fm = {}
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2).strip()
        if val in ("|", ">", "|-", ">-", ""):
            # Block scalar: gather subsequent indented lines.
            block = []
            j = i + 1
            while j < len(lines) and (lines[j].startswith((" ", "\t")) or lines[j] == ""):
                block.append(lines[j].strip())
                j += 1
            fm[key] = " ".join(b for b in block if b).strip()
            i = j
        else:
            fm[key] = val
            i += 1
    return fm, body


def collect_claude_md(path: Path):
    if not path.exists():
        return None
    info = {"path": str(path)}
    info.update(count_text(path))
    return info


def collect_settings(path: Path):
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"path": str(path), "parse_error": str(e)}
    # Summarize rather than dump raw secrets-bearing blobs verbatim where huge.
    summary = {"path": str(path), "keys": sorted(data.keys())}
    if "hooks" in data:
        hooks = data["hooks"]
        summary["hooks"] = {
            event: [
                {
                    "matcher": entry.get("matcher"),
                    "commands": [h.get("command", h.get("type")) for h in entry.get("hooks", [])],
                }
                for entry in (entries if isinstance(entries, list) else [])
            ]
            for event, entries in (hooks.items() if isinstance(hooks, dict) else [])
        }
    if "permissions" in data:
        summary["permissions"] = data["permissions"]
    if "env" in data:
        summary["env_keys"] = sorted(data["env"].keys()) if isinstance(data["env"], dict) else data["env"]
    if "enabledPlugins" in data:
        summary["enabledPlugins"] = data["enabledPlugins"]
    # Surface remaining top-level scalar flags (autoCompactEnabled, etc.).
    summary["flags"] = {
        k: v for k, v in data.items()
        if k not in {"hooks", "permissions", "env", "enabledPlugins", "statusLine"}
        and not isinstance(v, (dict, list))
    }
    if "statusLine" in data:
        summary["hasStatusLine"] = True
    return summary


def collect_skill(skill_dir: Path):
    skill_md = skill_dir / "SKILL.md"
    info = {"name_dir": skill_dir.name, "path": str(skill_dir)}
    if not skill_md.exists():
        info["error"] = "no SKILL.md"
        return info
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    fm, body = parse_frontmatter(text)
    metrics = count_text(skill_md)
    info["skill_md"] = metrics
    if fm is None:
        info["frontmatter_error"] = "missing or malformed frontmatter"
    else:
        info["name"] = fm.get("name")
        desc = fm.get("description", "")
        info["description"] = desc
        info["description_words"] = len(WORD_RE.findall(desc))
        # Trigger heuristic: a good description says WHEN to use it.
        info["description_has_trigger"] = bool(
            re.search(r"\b(when|use this|trigger|invoke)\b", desc, re.IGNORECASE)
        )
        info["frontmatter_extra_keys"] = [
            k for k in fm.keys() if k not in {"name", "description"}
        ]
        if info.get("name") and info["name"] != skill_dir.name:
            info["name_mismatch"] = True
    info["body_has_when_to_use_section"] = bool(WHEN_TO_USE_BODY_RE.search(body or ""))
    info["over_500_lines"] = metrics.get("lines", 0) > 500
    # Vendored vs user-authored. Vendored skills (gstack/plugin ecosystems) carry
    # their own conventions and get overwritten on upgrade — best-practice findings
    # on them are noise. Heuristics: ecosystem frontmatter keys, a "(gstack)" tag,
    # or a package manifest sitting in the skill dir.
    extra = set(info.get("frontmatter_extra_keys", []) or [])
    desc_l = (info.get("description") or "").lower()
    has_manifest = (skill_dir / "package.json").exists() or (skill_dir / "conductor.json").exists()
    vendored = (
        "preamble-tier" in extra
        or ({"version", "allowed-tools"} <= extra)
        or "(gstack)" in desc_l
        or has_manifest
    )
    info["vendored"] = vendored
    info["vendored_signals"] = sorted(
        s for s, ok in (
            ("preamble-tier", "preamble-tier" in extra),
            ("version+allowed-tools", {"version", "allowed-tools"} <= extra),
            ("(gstack)-tag", "(gstack)" in desc_l),
            ("package-manifest", has_manifest),
        ) if ok
    )
    # Hygiene: extraneous files + resource dirs present.
    extraneous, has_refs, has_scripts, has_assets = [], False, False, False
    for child in skill_dir.rglob("*"):
        rel = child.relative_to(skill_dir)
        if child.is_dir():
            if rel.parts[0] == "references":
                has_refs = True
            elif rel.parts[0] == "scripts":
                has_scripts = True
            elif rel.parts[0] == "assets":
                has_assets = True
            continue
        if child.name.lower() in EXTRANEOUS_SKILL_FILES and child.parent == skill_dir:
            extraneous.append(child.name)
    info["extraneous_files"] = extraneous
    info["has_references"] = has_refs
    info["has_scripts"] = has_scripts
    info["has_assets"] = has_assets
    return info


def collect_plugins(global_dir: Path, enabled: dict):
    installed_path = global_dir / "plugins" / "installed_plugins.json"
    result = {"enabled": enabled or {}}
    enabled_keys = set((enabled or {}).keys())
    installed = {}
    if installed_path.exists():
        try:
            data = json.loads(installed_path.read_text(encoding="utf-8"))
            installed = data.get("plugins", {})
            result["installed"] = sorted(installed.keys())
            result["installed_versions"] = {
                k: (v[0].get("version") if isinstance(v, list) and v else None)
                for k, v in installed.items()
            }
        except Exception as e:
            result["parse_error"] = str(e)
            return result
    else:
        # No manifest: anything enabled is, by definition, not installed.
        result["installed"] = []
    installed_keys = set(installed.keys())
    result["enabled_not_installed"] = sorted(enabled_keys - installed_keys)
    result["installed_not_enabled"] = sorted(installed_keys - enabled_keys)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--global-dir", default=str(Path.home() / ".claude"))
    ap.add_argument("--project-dir", default=os.getcwd())
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    gdir = Path(args.global_dir).expanduser()
    pdir = Path(args.project_dir).expanduser()

    snapshot = {"global_dir": str(gdir), "project_dir": str(pdir)}

    # CLAUDE.md (global + project + nested project ones, capped).
    snapshot["claude_md"] = {
        "global": collect_claude_md(gdir / "CLAUDE.md"),
        "project": collect_claude_md(pdir / "CLAUDE.md"),
        "project_local": collect_claude_md(pdir / "CLAUDE.local.md"),
    }
    nested = []
    if pdir.exists():
        for p in sorted(pdir.rglob("CLAUDE.md")):
            if p in (pdir / "CLAUDE.md",):
                continue
            if any(part in (".git", "node_modules", ".claude") for part in p.parts):
                continue
            entry = {"path": str(p)}
            entry.update(count_text(p))
            nested.append(entry)
    snapshot["claude_md"]["nested"] = nested[:30]

    # settings (global + project).
    global_settings = collect_settings(gdir / "settings.json")
    snapshot["settings"] = {
        "global": global_settings,
        "project": collect_settings(pdir / ".claude" / "settings.json"),
        "project_local": collect_settings(pdir / ".claude" / "settings.local.json"),
    }

    # skills (global + project).
    skills = {}
    for label, base in (("global", gdir / "skills"), ("project", pdir / ".claude" / "skills")):
        items = []
        if base.exists():
            for d in sorted(base.iterdir()):
                if d.is_dir():
                    items.append(collect_skill(d))
        skills[label] = items
    snapshot["skills"] = skills

    # Duplicate detection: two skill dirs sharing the same frontmatter `name`
    # collide (the harness loads one; the other is dead weight). Report groups.
    name_map = {}
    for scope, items in skills.items():
        for s in items:
            nm = s.get("name")
            if nm:
                name_map.setdefault(nm, []).append("%s/%s" % (scope, s["name_dir"]))
    snapshot["duplicate_skill_names"] = {
        nm: dirs for nm, dirs in name_map.items() if len(dirs) > 1
    }

    # agents.
    agents = {}
    for label, base in (("global", gdir / "agents"), ("project", pdir / ".claude" / "agents")):
        if base.exists():
            agents[label] = sorted(p.name for p in base.glob("*.md"))
    snapshot["agents"] = agents

    # plugins.
    enabled = (global_settings or {}).get("enabledPlugins", {})
    snapshot["plugins"] = collect_plugins(gdir, enabled)

    json.dump(snapshot, sys.stdout, indent=2 if args.pretty else None, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
