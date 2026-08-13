# steipete/agent-scripts skill-cleaner — Reference Notes

Source: https://github.com/steipete/agent-scripts/blob/main/skills/skill-cleaner/SKILL.md
Script: skills/skill-cleaner/scripts/skill-cleaner.ts (937 lines, TypeScript)
Date reviewed: 2026-05-25

## What it does (Codex/OpenClaw focused)

1. **Prompt budget math** — calculates token cost per skill (ceil(utf8_bytes / 4)), total budget used, budget ceiling (2% of context window), and Codex's truncation cascade (full descriptions -> equal truncation -> omit)
2. **Usage scanning** — greps session logs (.jsonl) for $skill mentions, SKILL.md reads, and skill-use traces to find unused skills
3. **Duplicate detection** — Jaccard similarity on word sets of descriptions AND body content. Flags near-copies (body >= 95% similar, or body >= 85% AND desc >= 85%)
4. **Description bloat flagging** — long descriptions where tighter wording saves budget
5. **Multi-root dedup** — finds same-name skills across Codex built-ins, plugins, repo, personal roots
6. **Delete priority** — system skills > direct codex > plugin > personal/repo copies

## What we adopted for Hermes (in bulk-budget-report.sh)

- Token cost formula: ceil(bytes/4)
- Budget ratio: desc tokens vs 2% of context window
- Usage from episodes (not sessions — too slow)
- Dupe detection via Python Jaccard on preloaded skill descriptions
- Flags: UNUSED, HEAVY_DESC (>200 bytes), LARGE_BODY (>20KB)

## What we skipped (Codex-specific, not applicable)

- Multi-root dedup (Hermes has one skill root)
- Codex budget cascade simulation (truncation then omission; Hermes doesn't do this)
- Config.toml parsing for disabled plugins
- JSONL session log scanning patterns ($skill, path references)
- Model context window lookup from ~/.codex/models_cache.json
- Auto-generated description suggestions (we have skill-creator's description optimizer)

## Key implementation lessons

- awk for YAML parsing must handle three formats: `description: "quoted"`, `description: unquoted`, and `description: |` (block scalar with indented continuation lines)
- grep -rl inside while-read loops consumes stdin; always redirect loop input from a file
- Per-skill session grep is O(skills * session_bytes); episodes are sufficient and 100x faster
- Jaccard with stop word removal at 40% threshold found zero preloaded pairs in our library (good: descriptions are distinct)
