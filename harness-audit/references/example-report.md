# Example Audit Report

A worked example of the output `harness-audit` should produce. Match this shape,
density, and honesty. This is illustrative — never copy its specific findings;
report only what the live snapshot and file inspection actually show.

---

## Sample (Suggest mode)

> **Mode: Suggest (read-only).** No files were changed.
>
> **Summary** — 44 skills (38 vendored / 6 user-authored), 1 global CLAUDE.md
> (11 lines), 1 Stop hook, 4 enabled plugins. **2 findings: 1 High, 1 Low.**
> The harness is in good shape; most "long skill" hits are vendored gstack
> skills and are not actionable. Top fix: resolve the duplicate browser skill.
>
> ### Skills
>
> **[HIGH] Duplicate skill — `connect-chrome` is byte-identical to `open-gstack-browser`**
> - Files: `~/.claude/skills/connect-chrome/SKILL.md`, `~/.claude/skills/open-gstack-browser/SKILL.md`
> - Quote: both declare `name: open-gstack-browser` (770 lines each, `diff` = identical)
> - Cost: two dirs share one `name`, so the harness loads one and the other is
>   dead weight; `connect-chrome`'s dir name also mismatches its `name`.
> - Fix: delete the redundant `connect-chrome/` dir. NOTE: vendored (gstack) — a
>   `gstack-upgrade` may recreate it; the durable fix is upstream.
>
> ### Plugins
>
> **[LOW] `clangd-lsp` enabled, version "unknown"**
> - File: `~/.claude/plugins/installed_plugins.json`
> - Cost: a stale/odd install can behave unexpectedly; cosmetic otherwise.
> - Fix: reinstall via the plugin manager if it misbehaves; ignore otherwise.
>
> ### Notes (no action)
> - 33 vendored skills run 500–2500 lines — that's the gstack ecosystem
>   convention, not a defect. Don't hand-edit; changes are wiped on upgrade.
> - Global CLAUDE.md is tight (11 lines) and conflict-free. 

---

## What makes this report good

- **Leads with a 3-5 line summary** + finding counts by severity + the single
  highest-leverage fix. The reader knows the verdict before any detail.
- **Honest** — says the harness is healthy and pushes noise into a "Notes (no
  action)" bucket instead of inflating the finding count.
- **Every finding quotes the offending text** and names the exact file path.
- **Cost is concrete** ("dead weight", "wiped on upgrade") — never "this is bad
  practice" with no consequence.
- **Fixes are specific and caveated** — the duplicate fix flags that it's
  vendored and may not stick.
- **Scopes by vendored** — length findings live only in Notes for vendored
  skills; the High finding survives because a `name` collision is real breakage
  regardless of authorship.

## Fix-mode addendum

In Fix mode, append an "Applied changes" section after acting:

> ### Applied changes
> - ✅ Backed up `settings.json` → `settings.json.bak`
> - ✅ Deleted `~/.claude/skills/connect-chrome/` (user-approved)
> - ↩︎ Skipped: clangd-lsp reinstall (user declined)
> - Re-ran collector: `duplicate_skill_names` now empty. ✔
