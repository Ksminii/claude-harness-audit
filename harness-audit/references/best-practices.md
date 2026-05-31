# Harness Best-Practice Criteria

Reference checklist for auditing a Claude Code harness. Each section lists what
to flag and why. Findings should cite the specific file/key and quote the
offending text. Severity guidance: **High** = actively harms behavior or wastes
context every session; **Medium** = real but situational; **Low** = polish.

## Table of Contents
- [CLAUDE.md](#claudemd)
- [Hooks (settings.json)](#hooks-settingsjson)
- [Permissions & flags](#permissions--flags)
- [Skills](#skills)
- [Plugins & MCP](#plugins--mcp)
- [Cross-cutting: conflicts & duplication](#cross-cutting-conflicts--duplication)

---

## CLAUDE.md

Loaded into context **every** session, so every line pays rent.

- **Length / token cost** (High if very long). A global CLAUDE.md should be
  tight. Hundreds of lines of instructions is a smell — flag bloat and propose
  moving rarely-needed detail into a skill or reference doc that loads on demand.
- **Duplicating defaults** (Medium). Instructions restating what Claude already
  does ("write clean code", "be helpful", generic git etiquette) waste tokens.
  Flag and suggest deletion.
- **Relative dates / stale facts** (Medium). "as of last month", "currently v2"
  rot. Recommend absolute dates or removal.
- **Vague / unactionable** (Medium). "Be careful", "use best practices" give no
  decision criteria. Flag as noise unless paired with a concrete rule.
- **Imperative & specific is good**. Rules like "before any git work, read X" or
  "send a completion ping only on explicit request" are well-formed — concrete
  trigger + action.
- **Conflicts with skills/hooks** (High). See cross-cutting section.
- **Secrets** (High). Tokens, keys, internal URLs in CLAUDE.md leak into every
  context and any transcript. Flag for relocation to env/secret store.

## Hooks (settings.json)

Hooks run real shell commands the harness executes on lifecycle events
(`Stop`, `PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `SessionStart`, …).

- **Shell robustness** (High). A hook that can exit non-zero may block or noise
  up the event. Look for trailing `; true` / `|| true` guards on best-effort
  hooks (good), and flag fragile commands lacking them.
- **Idempotency / one-shot correctness** (Medium). Flag patterns that fire every
  time when they should fire once (e.g. a notify that doesn't consume its flag).
  A consume-the-flag pattern (`[ -f F ] && rm -f F && …`) is correct.
- **Matcher correctness** (High). For `PreToolUse`/`PostToolUse`, a missing or
  wrong `matcher` means the hook runs on the wrong tools (or all of them). Verify
  the matcher regex matches the intended tool names.
- **Blocking / latency** (Medium). Hooks on hot paths (every tool call, every
  prompt) that run slow commands add latency to every action. Flag heavy work on
  hot events.
- **Hardcoded absolute paths / machine-specific** (Low–Medium). Portable only if
  intended for one machine; note it.
- **Quoting & injection** (High). Unquoted `$(...)` / variables interpolating
  untrusted input (e.g. prompt text, filenames) into a shell command is an
  injection risk. Flag.
- **Silent failure** (Medium). A hook whose failure mode is invisible (no log, no
  exit signal) is hard to debug — note when there's no observability.

## Permissions & flags

- **`defaultMode: "auto"` / `skipAutoPermissionPrompt: true`** (Medium, context-
  dependent). These reduce friction but also reduce guardrails. Note the
  tradeoff; don't assume it's wrong — the user may want it.
- **Overly broad allow rules** (Medium). Permission allowlists with wildcards
  like `Bash(*)` defeat the purpose. Flag broad grants; suggest narrowing.
- **`autoCompactEnabled: false`** (Low). Valid choice; just note it means long
  sessions won't auto-summarize — relevant if combined with very large CLAUDE.md.
- **env** (High for secrets). Secrets in `env` are readable; flag if sensitive.

## Skills

Judged by `references/best-practices` of skill-creator itself. The snapshot
extracts per-skill metrics — use them.

**Vendored vs user-authored — scope findings correctly.** The snapshot tags each
skill `vendored: true/false` (`vendored_signals` shows why: `preamble-tier`,
`version+allowed-tools`, a `(gstack)` description tag, or a `package.json`/
`conductor.json` in the dir). Vendored skills belong to plugin ecosystems
(gstack, superpowers, …) and are **overwritten on upgrade** — do NOT report
length/structure/style findings on them, and never propose hand-edits to them
(the fix won't survive `gstack-upgrade`). The audit's real target is
`vendored: false` skills. For vendored skills, report ONLY breakage that the user
must act on regardless of authorship: `name` collisions/mismatches, duplicates,
missing/malformed SKILL.md. Everything else about a vendored skill is, at most, a
one-line note ("N vendored skills run long — that's the ecosystem's convention").

- **Description quality** (High — it's the only trigger signal). The description
  must say **what it does AND when to use it** (triggers/contexts). Flag any
  skill where `description_has_trigger` is false or the description is purely a
  capability statement with no "use when…". This is the single highest-leverage
  fix because a skill that never triggers is dead weight.
- **`name` mismatch** (Medium). `name:` in frontmatter ≠ directory name
  (`name_mismatch` flag) can break invocation. Flag.
- **Extra frontmatter keys** (Low–Info). skill-creator says only `name` and
  `description` belong in frontmatter. Keys like `version`, `allowed-tools`,
  `preamble-tier` are used by some ecosystems (e.g. gstack/superpowers) — note
  them as non-standard but don't treat as errors if clearly part of a plugin
  convention. Flag unexpected/typo'd keys.
- **"When to use" in body** (Medium). `body_has_when_to_use_section` true means
  trigger guidance is in the body, where it's NOT read before triggering — it
  belongs in the description. Flag and suggest moving it up.
- **Over 500 lines** (Medium). `over_500_lines` true → SKILL.md should be split
  via progressive disclosure into `references/`. Flag, but check: some mature
  skills legitimately run long. Recommend splitting the coldest sections out.
- **Extraneous files** (Low–Medium). `extraneous_files` (README.md, CHANGELOG,
  INSTALLATION_GUIDE, etc.) don't belong in a skill. Flag for deletion.
- **Duplicate skills** (High). The snapshot's `duplicate_skill_names` lists
  groups of skill dirs sharing the same frontmatter `name`. Two dirs with one
  `name` collide — the harness loads one, the other is dead weight (and may be
  byte-identical). Confirm with `diff` and recommend deleting the redundant dir.
- **Duplicate / overlapping triggers** (Medium). Two skills whose descriptions
  claim the same triggers create ambiguity about which fires. Cross-check
  descriptions for collisions and flag pairs.
- **No SKILL.md / malformed frontmatter** (High). `error` or `frontmatter_error`
  → the skill is broken. Flag.

## Plugins & MCP

- **enabled-but-not-installed** (High). `enabled_not_installed` non-empty → a
  plugin is referenced in settings but missing on disk; it silently does nothing.
  Flag.
- **installed-but-not-enabled** (Low–Info). `installed_not_enabled` → dead weight
  on disk, or intentionally paused. Note it.
- **Version "unknown"** (Low). A plugin with `version: unknown` may be stale or
  mis-installed. Note; suggest reinstall if behaving oddly.
- **MCP servers needing auth** (Info). If a `mcp-needs-auth-cache.json` or similar
  shows servers pending authentication, note that headless/cron runs won't have
  those tools.

## Cross-cutting: conflicts & duplication

The highest-value findings often span components:

- **CLAUDE.md vs skill conflict** (High). A CLAUDE.md rule that contradicts a
  skill's instructions. Per superpowers ordering, user CLAUDE.md wins — but the
  conflict still causes confusion. Flag the pair and quote both.
- **CLAUDE.md vs hook redundancy** (Medium). An instruction telling Claude to do
  something a hook already does deterministically (or vice versa). Prefer the
  hook (deterministic) and trim the instruction, or note the redundancy.
- **Skill ↔ skill trigger overlap** (Medium). Covered above; list colliding pairs.
- **Instruction that should be a hook** (Medium). "Always run X after editing"
  phrased as a CLAUDE.md rule is unreliable (model may forget) — a PostToolUse
  hook is deterministic. Suggest converting automated/"every time" rules to hooks.
- **Hook that should be an instruction** (Low). Rare; a hook doing judgment-heavy
  work a model should decide. Note if seen.
