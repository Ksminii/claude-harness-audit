---
name: harness-audit
description: |
  Audit a Claude Code harness — global and project CLAUDE.md, settings.json hooks,
  permissions, installed skills, and plugins/MCP — and produce a prioritized
  improvement report, then optionally apply fixes with approval. Checks against
  skill-creator/hooks best practices, finds conflicts and contradictions between
  instructions/hooks/skills, and flags token-efficiency problems (bloated CLAUDE.md,
  duplicate triggers, cold content loaded every session). Use when the user asks to
  "audit my harness", "review my CLAUDE.md / hooks / skills / settings", "improve my
  Claude Code setup", "why won't my skill trigger", "clean up my config", or wants a
  health check of their ~/.claude or project .claude.
  Proactively suggest after the user installs new skills/plugins, edits settings.json
  or CLAUDE.md, or reports that a skill won't trigger or that hooks aren't firing.
---

# Harness Audit

Analyze a Claude Code harness and report prioritized, actionable improvements.
Three lenses: **best-practice compliance**, **conflicts/contradictions**, and
**token efficiency**.

## Modes

Decide the mode FIRST, before collecting anything:

- **Suggest mode** (default, read-only) — analyze and produce the report. Propose
  every fix concretely but make **no** changes. End after the report.
- **Fix mode** — do everything Suggest mode does, then apply approved fixes
  (step 5).

Pick the mode from how the skill was invoked:

- Args contain `suggest` / `report` / `dry-run` → Suggest mode.
- Args contain `fix` / `apply` / `auto` → Fix mode.
- Otherwise ask with AskUserQuestion: "Suggest mode (report only) / Fix mode
  (apply changes)" — two options, single-select. Default-recommend Suggest mode.

State the chosen mode in the first line of your response so the user knows
whether changes will be made.

## Workflow

### 1. Collect the snapshot

Run the collector — it extracts metrics and frontmatter so you reason over a
compact snapshot instead of reading dozens of files:

```bash
python3 <skill_dir>/scripts/collect_harness.py --pretty --project-dir "$PWD"
```

Default `--global-dir` is `~/.claude`. The JSON covers CLAUDE.md (global +
project + nested), settings.json (hooks/permissions/flags/plugins, global +
project + local), every skill's frontmatter + hygiene metrics, agents, and
plugin enable/install sync. Read it fully before analyzing.

### 2. Load the criteria

Read `references/best-practices.md` — the checklist for each component with
severity guidance. Apply it to the snapshot. Do NOT re-derive the rules from
memory; the reference is the source of truth and explains *why* each flag matters.

### 3. Investigate flagged items

The snapshot points; it doesn't conclude. For anything it flags, open the actual
file to confirm before reporting:

- A skill with `description_has_trigger: false` or `body_has_when_to_use_section:
  true` → read its SKILL.md to draft the fix.
- A CLAUDE.md flagged as long/duplicative → read it and quote the offending lines.
- A hook flagged fragile/injection-prone → read the exact command in settings.json.
- Suspected skill↔skill trigger overlap → compare the two descriptions directly.
- `duplicate_skill_names` non-empty → two dirs share one `name`; `diff` them and
  recommend removing the redundant one.

Never report a finding you haven't confirmed against the real file. Quote the
specific text. **Scope skill findings by `vendored`** (see best-practices.md):
length/structure/style issues apply only to `vendored: false` skills; for
vendored skills report only breakage (name collisions, duplicates, broken
SKILL.md), since hand-edits get wiped on the next plugin upgrade.

### 4. Produce the report

Group findings by component (CLAUDE.md / Hooks / Permissions / Skills /
Plugins-MCP / Cross-cutting). Within each, order by severity (High → Medium →
Low). For every finding give:

- **What** — the issue, with the file path and a quote of the offending text.
- **Why** — the concrete cost (wasted tokens every session, skill never triggers,
  hook silently fails, two rules contradict).
- **Fix** — the specific edit. For text, show the proposed before/after.

Lead with a 3-5 line summary: total findings by severity, and the top 3 highest-
leverage fixes. Be honest — if the harness is in good shape, say so and keep the
report short. Don't invent problems to fill a template. Push non-actionable
observations into a "Notes (no action)" bucket rather than inflating the count.

See `references/example-report.md` for a full worked example of the expected
output shape and quality bar (including the Fix-mode "Applied changes" addendum).

Use this finding format:

```
### [HIGH] Skill `foo` has no trigger in its description
- File: ~/.claude/skills/foo/SKILL.md
- Quote: "description: A tool for processing widgets."
- Cost: The description never says WHEN to use it, so the skill rarely triggers — dead weight.
- Fix: Append trigger contexts, e.g. "...Use when the user asks to 'process widgets', mentions widget batches, or ..."
```

### 5. Apply fixes — Fix mode only

In **Suggest mode**, stop after step 4. Do not edit anything.

In **Fix mode**, after presenting the report, ask which fixes to apply (offer
"all High", "all", or a hand-picked subset). Apply only approved ones:

- **CLAUDE.md / SKILL.md text** → Edit directly.
- **settings.json** (hooks, permissions, flags) → this is the harness config. If
  the `update-config` skill is available, prefer routing settings.json changes
  through it; otherwise edit carefully and preserve valid JSON. **Always back up**
  settings.json before editing (copy to `settings.json.bak`).
- **Deleting extraneous skill files** → confirm each path with the user first.
- Re-run the collector after applying to confirm the flags cleared.

Never modify settings.json, delete files, or rewrite CLAUDE.md without explicit
approval of that specific change. Don't touch anything outside the harness.

## Done when

- **Suggest mode**: the report is delivered with a summary + severity-ranked,
  file-cited, confirmed findings, and a Notes bucket for non-actionable items.
- **Fix mode**: above, plus every user-approved fix applied, an "Applied changes"
  section listing what changed / was skipped, and the collector re-run to confirm
  the corresponding flags cleared.

## Maintaining this skill

The collector has tests. After editing `scripts/collect_harness.py`, run:

```bash
python3 <skill_dir>/scripts/collect_harness_test.py
```

All tests must pass before relying on the snapshot. Add a test when adding a new
detection (it's how the `enabled_not_installed`-without-manifest case was caught).

## Scope notes

- This skill is read-mostly. Mutations happen only in step 5, only with approval.
- Some frontmatter keys (`version`, `allowed-tools`, `preamble-tier`,
  `benefits-from`) come from plugin ecosystems (gstack, superpowers) and are not
  errors — see best-practices.md. Don't flag a whole plugin's convention as broken.
- Plugin-provided skills live under `~/.claude/plugins/cache/...`; the collector
  scans `~/.claude/skills` and `./.claude/skills`. The user's own skills are the
  primary audit target — note plugin skills exist but don't rewrite vendored ones.
