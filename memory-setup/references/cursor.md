# Cursor Setup

Platform-specific install for the memory system in Cursor. For the entry format, categories, episode format, recall, and GC, see the shared spec in [`../SKILL.md`](../SKILL.md).

Cursor has no `~/.hermes`-style plugin that can run an extractor model for you, so the mapping differs from Claude Code. In Cursor, an **always-applied rule is the primary engine** (it loads and captures memory in-context, reliably and at zero extra token cost), and **hooks** are an optional automation layer.

**Cursor itself is the LLM, so no external CLI is required.** The reliability trick is to have the rule capture memory **incrementally** — writing each durable fact the moment it appears, in the same turn — rather than at session end. Sessions often end with no final agent turn, so any "save it at the end" strategy silently loses data. The optional `cursor-agent` hook below is only a backstop for catching the final turns automatically; if you have no CLI, incremental rule capture alone is a complete setup.

## How the concepts map

| Generic concept | Cursor primitive |
|-----------------|------------------|
| Load memory at session start | `alwaysApply` rule (`.cursor/rules/memory.mdc`) — instructs the agent to read the store first |
| Operating instructions (AGENTS.md / CLAUDE.md) | The same rule, or your `AGENTS.md` (Cursor reads it) |
| Session-end extraction hook | `sessionEnd` hook in `.cursor/hooks.json` → script that spawns `cursor-agent` (optional) |
| Daily GC | `memory-gc.py` run via `cron` / `launchd` |

Scope is your choice: project-local (`<repo>/.cursor/`, memory tied to one repo) or global (`~/.cursor/`, shared across all projects). Project hooks and user hooks **merge**, so a project `.cursor/hooks.json` coexists with an existing `~/.cursor/hooks.json`.

## Directory layout

```
.cursor/
├── rules/
│   └── memory.mdc          ← alwaysApply rule: load + capture + recall (the engine)
├── hooks.json              ← optional: sessionEnd → extraction hook
├── hooks/
│   └── memory-extract.sh   ← optional: spawns cursor-agent to extract at session end
└── memory/
    ├── MEMORY.md           ← hot memory
    ├── USER.md             ← user profile
    ├── memory-gc.py        ← daily decay / drain / prune
    └── episodes/
        ├── YYYY-MM-DD.md   ← daily summaries
        └── .pending.md     ← overflow queue
```

## The rule (primary mechanism)

`.cursor/rules/memory.mdc` — `alwaysApply: true` so it loads every session:

```markdown
---
description: Persistent cross-session memory. Load at session start, capture durable facts, recall on demand.
alwaysApply: true
---

# Memory

This workspace has a persistent memory store at `.cursor/memory/`.

## At session start
Read `.cursor/memory/MEMORY.md` and `.cursor/memory/USER.md` before substantive work.

## Capturing memory (save incrementally — do not wait for session end)
Append the moment a durable fact appears. As soon as the user states a durable fact,
preference, decision, correction, or constraint, append it to `.cursor/memory/MEMORY.md`
in the same turn — do not defer to the end of the session (sessions often end with no
final turn, so deferred saves are lost). Format: `[YYYY-MM-DD][cat] content`, preceded by
a `§` line. (Categories and decay rules: see the shared spec in SKILL.md.) Skip small talk
and noise. If MEMORY.md exceeds ~100 entries, append to `.cursor/memory/episodes/.pending.md` instead.

## Recalling the past
Search in order, stop when confident: hot (MEMORY.md/USER.md) → episodes/*.md (grep by tag/date) → raw chat history.
Use both exact (ripgrep) and meaning-based search.
```

## Optional step: automatic session-end extraction (`cursor-agent`)

This step is **entirely optional** — skip it if you only have the Cursor app, since incremental rule capture already covers you. If `cursor-agent` is installed *and authenticated* (`cursor-agent login`; it has its own auth, separate from `gh`), you can add a `sessionEnd` hook as a backstop that auto-extracts the final turns. Keep it **opt-in** (LLM calls cost tokens) and **recursion-guarded** (the extractor's own session would otherwise re-trigger the hook in an infinite loop). Any headless agent CLI works in place of `cursor-agent` (e.g. `claude -p`, `codex exec`, `gemini -y`).

`.cursor/hooks.json`:

```json
{
  "version": 1,
  "hooks": {
    "sessionEnd": [
      { "command": ".cursor/hooks/memory-extract.sh" }
    ]
  }
}
```

`.cursor/hooks/memory-extract.sh` (make it executable):

```bash
#!/usr/bin/env bash
set -uo pipefail
# Recursion guard: the extractor runs cursor-agent, whose sessionEnd re-fires this hook.
[ "${CURSOR_MEMORY_EXTRACTING:-}" = "1" ] && exit 0
# Opt-in: rule-based capture is the default; enable via CURSOR_MEMORY_AUTO_EXTRACT=1
[ "${CURSOR_MEMORY_AUTO_EXTRACT:-}" = "1" ] || exit 0

input="$(cat 2>/dev/null || true)"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MEM="$REPO/.cursor/memory"
if command -v jq >/dev/null 2>&1; then
  T="$(printf '%s' "$input" | jq -r '.transcript_path // .transcript // empty' 2>/dev/null || true)"
else
  T=""
fi
[ -n "$T" ] && [ -f "$T" ] || exit 0

DATE="$(date +%F)"
PROMPT="Read the transcript at $T and $MEM/MEMORY.md (to avoid dupes). Append durable
memories to $MEM/MEMORY.md as [$DATE][cat] content lines (each preceded by §), and a
one-paragraph episode to $MEM/episodes/$DATE.md. Skip noise. Be terse. Do nothing else."

CURSOR_MEMORY_EXTRACTING=1 nohup cursor-agent -p -f --output-format text "$PROMPT" >/dev/null 2>&1 &
exit 0
```

Hooks fail open and exit fast so they never block Cursor. Enable extraction with `export CURSOR_MEMORY_AUTO_EXTRACT=1`. After editing `hooks.json`, check **Settings → Hooks**; restart Cursor if the hook doesn't load.

## Notes

- `mdc` rules live only in `.cursor/rules/`; there is no global rules file, so for cross-project memory either use a global `~/.cursor/rules/memory.mdc` or rely on a per-repo rule.
- Cursor's `sessionEnd` payload shape can vary; the hook above probes common transcript fields and no-ops if none is found.
- The rule alone is a complete, reliable setup — the hook is purely a backstop.
