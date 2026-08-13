# Drift, budget, and usage checks

Run these on top of the structural checklist. They catch decay the checklist can't see: a
perfectly-structured skill pointing at code that moved.

## Codebase drift

Skills that name file paths, line counts, constants, or API contracts go stale silently as the
code changes. Run this when preloading a batch of skills, or when a skill gave wrong guidance.

1. **File existence**: every path in the skill still exists in the repo.
2. **Line counts**: `wc -l`. Drift over 10% means the file changed substantially.
3. **Constants and enums**: if the skill lists every value of a constant (notification types,
   endpoints), grep the source to confirm none were added or removed.
4. **Feature existence**: features from PRs that were reverted or never merged. Check key files
   exist on the default branch.
5. **Local paths**: normalize stale ones (`~/bloom`, `~/clawd/`) to `~/projects/<repo>`.
6. **Default branch**: some repos use master, others main. The skill must match.
7. **CLI commands**: referenced subcommands still exist. Check `--help`.

Real failures this caught: docs for Portfolio Analytics files that don't exist on master; an
`ema_alerts` notification type listed but never added to the codebase; a
`~/clawd/scripts/pr-preflight.sh` that doesn't exist, breaking the workflow on step one.

## Budget

Token cost = ceil(utf8_bytes / 4).

- **B1, description weight**: under 200 bytes (~50 tokens). Also flag a volatile string in it
  (an ISO date, "today", "current", a churning version number). It mutates the cached prompt
  prefix every turn. Descriptions should be evergreen.
- **B2, body weight**: SKILL.md under 20KB (~5K tokens when loaded). Over that, move content to
  references/.
- Full report across all skills: `bash ~/.hermes/skills/skills-meta/skills-cleanup/references/bulk-budget-report.sh`

**B1 only bites on preloaded skills.** Hermes uses a two-tier index: only `preloaded: true`
skills render their description in the system prompt, everything else collapses to a category
count line (`agent/skill_utils.py: get_skills_preload_all`, `extract_skill_description`). In one
audit, 475 skills had over-length descriptions but only 30 were preloaded, so the real waste was
~228 tokens, not the ~42,000 a naive sum implied. On a non-preloaded skill, an over-long
description is a routing-clarity problem, not a budget one. Score it, but don't sell it as a
token saving.

## Usage

A skill that never triggers is dead weight, especially preloaded.

1. Scan `~/.hermes/episodes/` for the skill name.
2. Scan recent `~/.hermes/sessions/` for `SkillView` / `skill_view` calls naming it.
3. Report last-used date and count over 30 and 90 days.
4. Zero uses in 90 days is an unused candidate. Cron-only skills are the exception.

## Forked-from-upstream skills

Some skills are private forks of one that ships with Hermes upstream. Assess drift from the seed,
not just from the codebase.

1. **Find the seed even when the name changed.** Forks get renamed (`hermes-agent` to
   `assistant-runtime`) and relocated (`autonomous-ai-agents/` to `internal/`), so name greps
   miss. Search a stable opening sentence:
   `grep -rl "<distinctive seed sentence>" ~/.hermes/hermes-agent/skills`. The `author:` and
   `homepage:` frontmatter confirm lineage.
2. **Diff against current upstream, not your local checkout**, which lags main. Pull the live
   file: `gh api repos/<owner>/<repo>/contents/<path> --jq .content | base64 -d`.
3. **Most fork content is yours.** Once a fork has accreted a private runbook, "update from
   upstream" is mostly meaningless. Surface the small delta, treat the bulk as a private-content
   refresh.

## Gap audits: grep the tree, don't eyeball a folder

When the question is "do we already have a skill for X?", the failure mode is searching the
obvious subfolder and missing a sibling one level up. Naming is not reliable.

Real case: asked whether video-editing skills existed, an agent scanned only
`creative/video-production/*` descriptions, concluded the cut/concat/grade pipeline was missing,
and proposed building it. `creative/video-editor` sat one level up and already covered
trim/concat/overlay/audio. The user had to say "look harder."

Grep the full tree by capability keyword, using the underlying tool or verb rather than the
feature name you have in mind:

```bash
cd ~/.hermes/skills
grep -rliE "ffmpeg|concat|lut3d|whisper|transcrib|color grade" --include=SKILL.md . | sort -u
```

Any description-only scan is preliminary. Confirm with a content grep before asserting absence.
