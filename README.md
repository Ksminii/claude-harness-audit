# claude-harness-audit

An [Agent Skill](https://docs.claude.com/en/docs/claude-code/skills) that audits your
Claude Code harness. It analyzes the global and project `CLAUDE.md`, `settings.json`
(hooks, permissions, flags), installed skills, and plugin/MCP configuration, then
produces a **prioritized improvement report** — and, if you want, applies the fixes
after your approval.

## What it checks

Analysis runs through three lenses:

- **Best-practice compliance** — violations measured against `skill-creator` / hooks guidance
- **Conflicts & contradictions** — instructions that clash, hook/instruction redundancy, skill-trigger collisions
- **Token efficiency** — bloated `CLAUDE.md`, duplicate triggers, cold content loaded every session

Key checks:

| Area | What it looks at |
|------|-----------|
| CLAUDE.md | Length/token cost, restating defaults, vague rules, conflicts, leaked secrets |
| Hooks | Shell robustness, idempotency, matcher correctness, injection risk, hot-path latency |
| Skills | Description triggers, when-to-use in body, >500 lines, **duplicate skills**, extraneous files |
| Plugins/MCP | enabled↔installed sync, version anomalies |

Vendored skills (e.g. gstack) and user-authored skills are **classified
automatically**, so length/style findings are suppressed for vendored skills that
get overwritten on upgrade — keeping the report free of noise.

## Install

```bash
git clone https://github.com/Ksminii/claude-harness-audit.git
cp -r claude-harness-audit/harness-audit ~/.claude/skills/
```

Claude Code picks it up automatically in subsequent sessions.

## Usage

Trigger it from a session with phrases like:

- "audit my harness"
- "why won't my skill trigger"
- "review my CLAUDE.md / settings / skills"

### Modes

- **Suggest mode** (default, read-only) — report only, no file changes
- **Fix mode** — after the report, applies approved changes (`settings.json` is backed up first)

Pass `suggest` or `fix` as an argument to set the mode directly; otherwise the
skill asks you to choose at the start.

## Layout

```
harness-audit/
├── SKILL.md                     # Workflow (collect → criteria → verify → report → fix)
├── references/
│   ├── best-practices.md        # Per-component criteria + severity guidance
│   └── example-report.md        # Output quality bar (worked example)
└── scripts/
    ├── collect_harness.py        # Deterministic snapshot collector (token-saving)
    └── collect_harness_test.py   # Collector tests
```

`collect_harness.py` builds a compact JSON snapshot of metrics and frontmatter
instead of reading dozens of files in full, which keeps token usage low during
analysis.

## Development

After editing the collector, run the tests:

```bash
python3 harness-audit/scripts/collect_harness_test.py
```

Add a test whenever you add a new detection.

## License

[MIT](LICENSE)
