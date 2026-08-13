---
name: skills-cleanup
description: "Find and remove duplicate or unused skills, and publish the library to a public repo. Use for clean up my skills, too many skills, skill budget report."
tags: [skills, maintenance, cleanup]
---

## Skills Repo Cleanup

### Key Facts
- Runtime skills: `~/.hermes/skills/` (plain files, no .git, backed up by hermes-backup)
- Public repo: `~/projects/skills` (git: exiao/skills on GitHub, manually curated)
- Runtime is the source of truth. The public repo is a curated subset, not a mirror.
- Automated skill creation nudge is **disabled** (`creation_nudge_interval: 0` in config.yaml)
- Agent scans `~/.hermes/skills/` and `skills.external_dirs` (currently empty), nothing else
- Archive of removed duplicates/untracked skills: `~/.hermes/skills-archive/`
- Sync cron is **paused** (was `d21431bbea17`). Public repo updates are manual.
- As of 2026-05-12, `~/.hermes/skills/.git` has been removed, so runtime is pure files. hermes-backup is SUPPOSED to handle versioning, but do NOT trust it blindly. The backup repo's skills tree has been seen STALE, with HEAD stuck weeks back while still logging "staging changes", so a deleted skill left no recoverable history there.
- Check HEAD's date before relying on it. The public mirror (`~/projects/skills`) is the more reliable recovery source.
- Public repo structure (10 categories): app-store, coding, design, external-services, investing, memory, skills-meta, thinking, video, writing. (Skill count grows over time, derive it live, don't trust a number cached here.)
- CLAUDE.md is canonical; AGENTS.md symlinks to it. All tables sorted alphabetically.

### Which public repo? (there is more than one)

Eric maintains SEVERAL public skills repos. Confirm the target before building, do
not assume the first `~/projects/skills`-looking dir is the one meant:
- `exiao/skills` (`~/projects/skills`), the big **category-nested** catalog
  (`<category>/<skill>/SKILL.md`). README tracks per-category counts + a grand total.
- `exiao/meta-skills` (`~/projects/meta-skills`), a small **FLAT** repo of
  skill-authoring/auditing skills (`<skill>/SKILL.md` at root, no category dir).
  README has a "The skills" table, one row per skill.
- `exiao/investingskills`, investing-only.

See "Publishing Personal Skills to a DIFFERENT Public Repo" below for the full
target-selection + layout-matching discipline; it is the #1 thing to get right before
touching files.

### Curator pin gotchas (bundled refusal + pinned-skill autonomous-edit block)

**`curator pin` only accepts agent-created skills.** `hermes curator pin <skill>` on a BUNDLED or HUB-INSTALLED skill no-ops with `'<skill>' is bundled or hub-installed — cannot pin (only agent-created skills participate in curation)`, hit in a real session on `plan`. Do not chase it.

Bundled skills are already exempt from the Curator's auto-archive/consolidate pass, so the protection a pin would give is implicit. Set `preloaded: true` for visibility and move on, and do not retry.

When pinning a mixed list, expect bundled and hub entries to no-op, and report them as skipped alongside already-pinned ones.

**Bundled skills also refuse the autonomous end-of-session PATCH pass.** In the end-of-session skill-update pass, `skill_manage patch`/`edit` on a BUNDLED skill such as `github-pr-workflow` is refused with `Refusing background curator patch for bundled skill '<name>'.` Bundled skills are protected, so route the learning to a non-bundled umbrella that covers the territory instead.

That is why public-repo PR pitfalls that would naturally live in the bundled `github-pr-workflow` land here in `skills-cleanup`, which owns public-repo publishing.

**A PINNED agent-created skill is off-limits to the autonomous end-of-session skill-update pass.** Both `skill_manage edit` and `write_file` get refused with `Refusing background curator edit for pinned skill '<name>': pinned skills are off-limits to autonomous maintenance.`

To capture a learning that belongs in a pinned umbrella during that pass, route it into a DIFFERENT non-pinned umbrella that covers the territory, or ask the user to `hermes curator unpin <name>` first.

That routing rule is why curator and pin facts live here in skills-cleanup rather than in the pinned skill-preloading, and why cross-skill-reference lessons that would otherwise go to the pinned `skill-audit` land here too.

Interactive user-directed edits are a separate, allowed path.

**skill_manage action mangling (`mcp_patch` / `mcp_write_file`).** In the autonomous skill-update pass, `skill_manage` with action `patch` or `write_file` can fail with `Unknown action 'mcp_patch'` / `'mcp_write_file'` because the runtime prefixes `mcp_`, even on a clean retry with identical args. Do NOT loop on it.

Use `edit` with the FULL updated SKILL.md text passed as `content`, and `create` for a new skill. Re-firing the same `patch`/`write_file` call just repeats the failure.

### Git Auth for exiao/skills
The default `GH_TOKEN` env var (cpe-research PAT) cannot create PRs on `exiao/skills`. The exiao token lives in `~/.hermes/.env` as `EXIAO_SKILLS_GITHUB_TOKEN` (moved out of the git remote URL on 2026-05-30 for security, do NOT re-embed it in the remote):
```bash
source ~/.hermes/.env
GH_TOKEN="$EXIAO_SKILLS_GITHUB_TOKEN" gh pr create ...
GH_TOKEN="$EXIAO_SKILLS_GITHUB_TOKEN" gh pr close ...
```
For plain `git push` the repo-local credential helper in `~/projects/skills/.git/config` already supplies the token from this env var at runtime, so a push just needs `EXIAO_SKILLS_GITHUB_TOKEN` exported (source `.env` first). Do not extract the token from the remote URL, it is no longer there.

On Eric's machine, `gh-as exiao gh ...` and `git-pin-account exiao` also work against `exiao/skills`. These are the per-process account wrappers from `github-pr-workflow` references/erics-machine.md, and they are the preferred concurrency-safe path inside a worktree. Pin the account once in the worktree, then plain `git push`/`gh` use exiao.

The guard-layer rule still applies, so split `git push` and `gh pr create` into separate commands, because a combined `push && pr create` can trip the merge guard's substring match.

### Recovering a Deleted / Missing Runtime Skill

When a session or cron reports `Skill(s) not found and skipped: <name>` but SOUL.md, a cron job, or another skill still references it by name, the skill dir was deleted while its references survived. Treat it as a real breakage rather than a setup error, since dependent crons flail (an issue-fixer cron falls back to writing a digest instead of fixing).

Load `references/recovering-a-deleted-runtime-skill.md` for the full playbook. It covers confirming gone vs archived, mapping live references, recovering content, repairing broken `references/` pointers, and verifying the skill loads. 
Recover from the mirror first, use hermes-backup ONLY if HEAD is recent, then rebuild runtime-only files like `scripts/collect_prs.py` from a `~/.hermes/memories/*.md` spec or the SKILL.md's own inline description.

The hermes-backup tree can be stale, so the public mirror `~/projects/skills` is the more reliable source, and flag the stale auto-backup to the user as a separate, higher-priority fix.

**But first rule out CONSOLIDATION, not deletion.** After any curation pass, a "missing" referenced skill has usually just been renamed or folded into a sibling as a `references/*.md` file, so its body still exists under a new name. The recovery playbook rebuilds content, so do NOT jump to it until a content grep confirms the body exists nowhere.

See "A Referenced Skill Reports 'Missing'" under Cross-Skill Reference Validation below.

### Loading a Skill Whose Name Collides Across Dirs

`skill_view(name='<bare-name>')` FAILS when more than one skill shares that name across the runtime dir and `skills.external_dirs`, or across categories. It refuses to guess and returns the matching paths. For example `notion` resolves to `productivity/notion/SKILL.md`, `creative/popular-web-designs/templates/notion.md`, and `creative/baoyu-article-illustrator/references/styles/notion.md`.

Pass the **full categorized path** instead of the bare name (`skill_view(name='productivity/notion')`). When a skill name feels generic (notion, twitter, research, design), reach for the category-qualified name on the FIRST call to avoid the wasted round-trip.

Files under `references/` and `templates/` inside other skills can carry colliding basenames too, but those are support files rather than loadable skills, so the categorized path of the actual SKILL.md is always the one you want.

### How Duplicates Happen
- The agent's automated skill creator places new skills in `~/.hermes/skills/<category>/<name>/`
- It picks category based on the LLM's judgment, no strict enumeration of valid categories
- This creates duplicates when skills already exist under a different canonical category in the git repo

### Cleanup Workflow
1. Compare local untracked files (`git status`) against remote (`git ls-tree -r --name-only origin/main`)
2. Identify duplicates (same skill name, different category) and local-only skills
3. Move duplicates to `~/.hermes/skills-archive/` (recoverable)
4. For genuinely new local-only skills worth keeping: branch, commit, PR

### Consolidating duplicates within runtime

Near-dupes (`X` vs `X-cli`, `simplify` vs `simplify-code`) matter more than exact-name collisions. Salvage the retiree's unique content into the canonical skill first, then archive through `hermes curator archive`, then scrub `CATALOG.md` and `.bundled_manifest`.

See [references/consolidating-duplicates.md](references/consolidating-duplicates.md) for the detection greps, the curator dry-run flow, package-integrity merge discipline, and the cross-category sign-off rule.

### Usage-Based Cleanup

Run the budget report to find dead weight:
```bash
bash ~/.hermes/skills/skills-meta/skills-cleanup/references/bulk-budget-report.sh
```

This lists every skill with token cost, body size, usage count, and last-used date. Focus on:
- **UNUSED flag:** Preloaded but 0 uses in 90 days. Unpin (`preloaded: true` -> remove) or archive.
- **HEAVY_DESC flag:** Description over 200 bytes. Tighten the wording.
- **LARGE_BODY flag:** SKILL.md over 20KB. Move content to `references/`.

### Dead Skill Detection

Skills that are pinned but never triggered waste system prompt tokens on every message.

1. Run the bulk budget report (above)
2. Filter to UNUSED flags
3. Cross-check: is this skill cron-only? (cron config names skills directly, so no episode/session trace is expected)
4. If not cron-only: unpin by removing `preloaded: true` from frontmatter. Don't delete; it stays browsable via `skills_list(category=...)`.
5. The repo owner merges, never push to main directly

### Preserving Dirty Runtime Checkout Before Switching Branches

Do not do cleanup or PR work directly in the runtime checkout (`~/.hermes/skills`). Preserve first, then move the review work into a project worktree:

```bash
cd ~/projects/skills
git fetch origin main
BRANCH="wip/preserve-skills-$(date +%Y%m%d)"
git worktree add ~/projects/_worktrees/$BRANCH -b "$BRANCH" origin/main
```

Copy or patch only the intentional skill changes into the worktree. Exclude generated/runtime state (`.usage.json`, `.usage.json.lock`, `.curator_state`, `.curator_backups/`, temporary reports, moved-file markers). Before committing, inspect `git diff --name-status` and stage explicit files rather than blanket-adding the runtime checkout.

For longer cleanup/review checklists, see `references/runtime-skills-preservation.md` and `references/runtime-snapshot-pr-review.md`.

### Publishing to a public repo

All git and GitHub mechanics for getting runtime skill work onto a public repo live in [references/publishing-to-public-repos.md](references/publishing-to-public-repos.md).

It covers porting a single runtime edit, publishing a brand-new skill dir, and the public repo review checklist and redaction grep.

It also covers the `gh pr create` foreground-guard false positive and lost `--body-file`, stale-base rebasing, force-push consent, and the worktree upstream trap where plain `git push` pushes nothing. Publishing to a DIFFERENT public repo such as `exiao/meta-skills` and moving a category into a brand-new repo via the bootstrap-to-main dance are there too.

Read it before touching any file in a public checkout. For the frontmatter and shell-snippet hazard greps that Codex flags every round, see `references/sanitizing-references.md`.

### Categories That Were Full Duplicates (removed 2026-05-01)
github/, autonomous-ai-agents/, software-development/, mlops/, media/, mcp/, leisure/, red-teaming/, note-taking/, email/, smart-home/, gaming/, analytics/, diagramming/, domain/, feeds/, gifs/, inference-sh/, dogfood/

### Inherited Client Examples

Skills templated from a client project often have dead examples baked in (wrong audience, irrelevant copy, client-specific search queries). These mislead creative generation. Load `references/inherited-client-examples.md` for detection, cleanup rules, and a worked example.

### Pitfalls with bulk-budget-report.sh

- **Multiline YAML descriptions:** Skills use `description: |` (block scalar), `description: "quoted"`, and `description: unquoted`. The extraction awk must handle all three. The script already does, but if you rewrite, test against all formats.
- **Session grep is too slow:** Grepping `~/.hermes/sessions/` per-skill takes minutes (hundreds of JSON files). The script only scans episodes, which is fast and sufficient since episode summaries mention loaded skills.
- **Preloaded count drift:** The script counts `preloaded: true` in frontmatter. The skill-preloading skill lists 51, but the script may find more if skills were pinned ad-hoc without updating the list. Trust the script's count.
- **While-read + grep stdin conflict:** If a `while read` loop reads from a pipe AND the loop body runs `grep -rl`, grep can consume stdin from the pipe and silently skip lines. Fix: write `find` output to a temp file first, then `while read < file`.
- **Dupe detection uses Python Jaccard:** The bash loop + python3 inline approach is fast enough for ~65 preloaded skills. Stop words are filtered. Threshold is 40%. If no pairs hit 40%, descriptions are well-differentiated.
- See `references/steipete-skill-cleaner-notes.md` for the original source analysis (steipete/agent-scripts) that inspired the budget report.

### Full Repo Overhaul

When the user wants to completely replace the public repo contents with a curated subset (new categories, different skill selection), load `references/full-repo-overhaul.md`. It covers the destructive replacement workflow, credential scanning, cross-skill reference validation, the CI review loop, and the exiao token workaround for PR creation.

Validating cross-skill references before the first push prevents 3-6 rounds of CI churn.

### Category Reorganization

When categories feel off or there are too many top-level folders, load `references/category-reorganization.md`. It covers bloat detection, merging overlapping categories, moving project-specific skills to `internal/`, creating a new category, and the runtime-only variant.

It documents two traps. A bulk `rm -rf` silently no-ops here, so use `trash`, and `generate_catalog.py` crashes when any `*/DESCRIPTION.md` lacks its `---` fence.

For regenerating README.md and CATALOG.md after any move, see `references/readme-catalog-generation.md`.

### README Maintenance

When adding, removing, or renaming skills, update the README.md category table with accurate skill counts. Verify counts with `find <category> -name SKILL.md | wc -l`. Tables must be alphabetically sorted. Attribution section must include full source repo links (see git history commit `a4b8e27` for the canonical attribution list).

### Cross-Skill Reference Validation

After bulk skill deletions, moves, or renames, scan for broken cross-references BEFORE pushing. This is the #1 source of reviewer churn in reorganization PRs, and it caused 6 rounds of CI review in the 2026-05-12 overhaul.

Check both backticked (`skill-name`) and plain text references (**skill-name**, /skill-name, prose mentions). See `references/full-repo-overhaul.md` for the full scan script and fix strategies.

### A Referenced Skill Reports "Missing": Search for Its Consolidated Home Before Rebuilding

When a SOUL, cron, or another skill names a skill by backtick and it doesn't load, the default assumption "it was deleted, recover it" is often WRONG. The more common cause after any curation pass is **consolidation**, where the skill got renamed or folded into a sibling as a `references/*.md` file and the old name went stale silently.

Rebuilding it duplicates content that already exists under a new name.

Distinguish consolidated-vs-deleted before acting:

1. **Grep the whole tree for the skill's DISTINCTIVE CONTENT, not its name.** The name is exactly what changed. A consolidated skill keeps its body, so search for a signature phrase, verb, or tool it taught.

   In a real case a SOUL referenced `research-summary-surge-page`, which didn't exist anywhere by name. Grepping for its subject (`verdict-first`, the `surge.sh` layout) found it folded into `devops/surge-deploy/references/research-summary-page-style.md`. The workflow half became the `surge-deploy` SKILL, and the layout half became one of its reference files.
   ```bash
   grep -rln "<distinctive phrase the missing skill taught>" ~/.hermes/skills
   grep -rl  "<old-skill-name>"                              ~/.hermes/skills ~/.hermes/profiles/*/SOUL.md
   ```
2. **Two consolidation shapes to expect:** (a) renamed skill (same dir shape, new `name:`), repoint references to the new name; (b) absorbed-as-reference (the whole skill became `references/<topic>.md` inside a larger umbrella), repoint references to "the `<umbrella>` skill's `<topic>.md` reference," not to a bare skill name that no longer resolves.
3. **Fix the wiring rather than rebuilding.** Add the missing category/skill symlink into the consuming profile if absent (`profiles/<p>/skills/<cat>/<skill>` → `~/.hermes/skills/<cat>/<skill>`), then update every stale mention in the SOUL, cron, or skill.

   Verify the symlink resolves through to the referenced reference file (`cat profiles/<p>/skills/<cat>/<skill>/references/<file>.md | head`). Only fall back to the "Recovering a Deleted / Missing Runtime Skill" playbook once a content grep confirms the body exists NOWHERE under any name.
4. **SOUL edits take effect at next session boot** (SOUL is read once at start), so the repoint won't self-verify in the current session, confirm by resolving the symlink and grepping the SOUL for any remaining stale name instead.
