# Category Reorganization Workflow

Use when the user says the skills repo has too many top-level categories, categories are in the wrong place, or categories should be merged/deleted.

## Runtime-only reorg (vs public-repo reorg)

The playbook below (worktree, `git rm`, README/CLAUDE.md edits, PR) is for the PUBLIC repo `~/projects/skills`. When the user says "runtime only" / "don't touch the public mirror," the mechanics differ:

- **Deletion uses `trash`, NOT `rm`.** `rm` is BANNED in this runtime (SOUL guard). A bulk `rm -rf` loop over empty dirs **silently no-ops every iteration** and leaves all the dirs in place — you'll think you cleaned up and you didn't. Use `trash "$dir"` (moves to ~/.Trash, recoverable). The guard error names the fix; don't reach for `/bin/rm` or `HERMES_ALLOW_RM=1` to force it.
- **Moves: `git mv` works and is clean.** `~/.hermes/skills` IS a git repo (`git rev-parse --is-inside-work-tree` → true), so `git mv old/skill newcat/skill` records 100+ moves as renames (R), not delete+add. Verify with `git status --short | awk '{print $1}' | sort | uniq -c` (expect mostly R, plus D for deleted dirs, M for edited index/cron files).
- **Regenerate the catalog with the script, don't hand-edit.** After moves/deletes: `cd ~/.hermes/skills && python3 scripts/generate_catalog.py` regenerates BOTH `CATALOG.md` and `README.md` from the live tree. Hand-editing rows is error-prone and the script overwrites them anyway. Then grep the generated docs for stale old paths to confirm: `grep -nE '\((oldcat/(subdir)|retired-cat)/' CATALOG.md README.md` should be empty.
- **No PR.** Runtime changes land as uncommitted edits in the runtime git repo. Ask the user whether to commit them or leave loose; don't open a PR against the public mirror.

### "Will the auto-backup pick this up?" — verify the push actually works, don't assume

Runtime skill changes get versioned by the `com.hermes.auto-backup` launchd job (`~/.hermes/bin/auto-backup.sh`, every 30 min): it auto-commits ALL of `~/.hermes` and pushes to `github.com/exiao/hermes-backup`. It hides `skills/.git` during `git add -A` so the skills tree is captured as plain file content (not a submodule pointer), so yes, every move/delete/edit you make is in scope. You do NOT need to commit anything yourself.

BUT the push has been observed silently broken for DAYS. When the user asks "will the backup catch this," actually verify both halves (commit AND push), don't just say yes:

```bash
cd ~/.hermes && /usr/bin/git status -sb | head -1        # "## main...origin/main [ahead N]" — N>0 means stranded
tail -4 logs/auto-backup.log                              # look for "Repository not found" / "push failed"
```

Recurring root cause (a credential/account mismatch, NOT a setup error to ignore): `hermes-backup` is a PRIVATE repo visible only to the `exiao` GitHub account, but the script's plain `git push` resolves whatever the GLOBAL git credential helper hands back for github.com — often the default `cpe-research` token, which has no access → GitHub returns `remote: Repository not found`. Commits keep landing locally (recoverable) while nothing reaches GitHub.

Confirm the diagnosis, then fix:
```bash
gh-as exiao gh repo view exiao/hermes-backup --json name,visibility,pushedAt   # exists+private, pushedAt = date backup actually broke
cd ~/.hermes && HERMES_BACKUP_BYPASS=1 git-pin-account exiao                   # pin repo-local to exiao; concurrency-safe, no global switch
```
After pinning, you CANNOT push from the agent session yourself: `git push origin main` is blocked by the block-dangerous-merges guard (direct-to-main), and the `HERMES_BACKUP_BYPASS` only applies in the launchd context, not your session. Trigger the real job instead:
```bash
launchctl kickstart -k system/com.hermes.auto-backup    # gui/<uid>/ domain often 502s; system/ works. then re-check status -sb shows no "ahead"
```
This is a higher-priority fix than the cleanup itself (a broken backup means days of unprotected work) — surface it to the user as its own finding, with the date it broke (the `pushedAt` above), not a footnote.

### A "dead" category (zero SKILL.md) can still be LIVE DATA — verify before deleting

The "Empty bloat" rule (zero SKILL.md → delete) is necessary but NOT sufficient. A category folder can hold no skills yet still be read/written by a cron job or another skill. Real burn: `analytics/aso-weekly-report/snapshots/*.json` had zero SKILL.md but the weekly ASO cron prompt AND `app-store/aso/aso-weekly-report/SKILL.md` both read/write that snapshot dir. Deleting it would have silently broken the cron's week-over-week diff.

Before deleting ANY zero-skill folder, check it isn't referenced as a data path:
```bash
NAME=analytics   # the folder about to be deleted
grep -rn "$NAME/" ~/.hermes/cron/jobs.json ~/.hermes/skills --include='*.md' --include='*.json' \
  | grep -v -E '\.curator_backups/|/output/|\.bak'
```
If it's live data, MOVE it under the owning skill (`git mv analytics/aso-weekly-report/snapshots app-store/aso/aso-weekly-report/snapshots`) and update every path reference: the skill SKILL.md(s) AND the live `cron/jobs.json` prompt (then `python3 -c "import json;json.load(open('cron/jobs.json'))"` to confirm it's still valid JSON). Only DESCRIPTION-only / truly-unreferenced folders are safe to `trash`.

### Verify before AND after, with explicit checks

- **Before moving:** confirm every source `SKILL.md` exists and every destination is clear (no collision) — a one-shot loop testing `[ -f "$src/SKILL.md" ]` and `[ ! -e "$dst" ]` catches typos before you `git mv` 17 things.
- **Before deleting:** confirm each folder has `find "$d" -name SKILL.md | wc -l` == 0 AND no non-DESCRIPTION files (`find "$d" -type f ! -name DESCRIPTION.md`).
- **After:** assert NO category is left empty, the total `SKILL.md` count is unchanged (nothing lost in a move), and `skill_view(name='<moved-skill>')` loads from its new path with linked files resolving.
- **Leave dated historical lists alone.** A "Categories removed on <date>" list in a SKILL.md is a record, not a live reference — don't try to "fix" it to match the new tree.

#### A SKILL.md COUNT is not enough — diff the SET of skill NAMES before vs after

Real burn (2026-06-17): a reorg deleted "41 empty category folders" and its self-report said "All 347 skills intact." It was wrong — the deletion also swept away `internal/cpe-research/` (a 708-file, `preloaded: true` skill), and SIX cron jobs that load `cpe-research` by name started silently failing ("Skill(s) not found and skipped") for over an hour before anyone noticed. A bare count comparison missed it because the count was asserted in prose, not computed, and a folder-delete pass can take a whole skill dir with it.

So the after-check must compute and DIFF the actual name set, never just eyeball a number:
```bash
# BEFORE any moves/deletes (run from ~/.hermes/skills):
find . -name SKILL.md -not -path '*/.curator_backups/*' -not -path '*/.archive/*' \
  | sed 's#/SKILL.md##; s#^\./##' | sort > /tmp/skills-before.txt
# ... do the reorg ...
# AFTER:
find . -name SKILL.md -not -path '*/.curator_backups/*' -not -path '*/.archive/*' \
  | sed 's#/SKILL.md##; s#^\./##' | sort > /tmp/skills-after.txt
# Every line here MUST be an intentional move (path changed) — a basename that
# disappears entirely is a LOST skill, stop and recover it:
comm -23 <(sed 's#.*/##' /tmp/skills-before.txt | sort) <(sed 's#.*/##' /tmp/skills-after.txt | sort)
```
If `comm -23` (basenames present before, absent after) is non-empty, you deleted a real skill — do NOT report success. Empty `internal/`-namespaced skills count too; the "empty category folder" cleanup must exclude any dir that contains a `SKILL.md` anywhere beneath it, not just at its top level.

#### After a delete pass, re-validate every cron `skills` reference still resolves

Cron jobs name skills by bare name in their `skills` array (`cpe-research`, `babysit-pr`), independent of category path. A delete that removes a skill those jobs depend on won't surface until the job next runs. Close the loop in the same pass:
```bash
python3 - <<'PY'
import json, pathlib
home = pathlib.Path.home() / ".hermes"
names = {p.parent.name for p in (home/"skills").rglob("SKILL.md")
         if ".curator_backups" not in p.parts and ".archive" not in p.parts}
jobs = json.load(open(home/"cron"/"jobs.json"))
jobs = jobs if isinstance(jobs, list) else jobs.get("jobs", jobs)
for j in jobs:
    for s in (j.get("skills") or []) + ([j["skill"]] if j.get("skill") else []):
        if s not in names:
            print(f"MISSING: job {j.get('name')!r} references skill {s!r} that no longer exists")
PY
```
Any `MISSING:` line is a broken dependency you introduced — restore the skill (recovery playbook below) before declaring the reorg done.

### Creating a NEW category and moving skills into it (runtime-only)

The inverse of merge/delete: user wants a brand-new category (e.g. `thinking/`) and asks which existing skills should move there. Workflow that worked end to end:

1. **Pick the members by CLASS, not keyword.** A `grep -ri` for "decision|brainstorm|reasoning|mental model" across all SKILL.md descriptions returns mostly FALSE POSITIVES (domain skills that mention "tradeoff"/"decision" in passing). Read each candidate's `description:` and keep only the domain-AGNOSTIC ones. Leave domain-bound skills where they are even if they touch the theme (e.g. `creative-ideation` stays in creative, `spike` stays in coding, a marketing-scoped psychology skill is borderline — surface it and let the user decide). Present the tight set + the defensible-maybes and ask which to include before moving.
2. **Create the dir + DESCRIPTION.md** with the standard frontmatter shape (`---\ndescription: ...\n---`), one concise sentence naming the class.
3. **Pin as needed.** Pinning = add `preloaded: true` as its own line right after the `description:` line in each SKILL.md frontmatter. Check current state first: `grep -l "preloaded: true" <skill>/SKILL.md`. To add it across files: `perl -0pi -e 's/^(description:.*\n)---/$1preloaded: true\n---/m' a/SKILL.md b/SKILL.md`. Verify each ended with exactly one `preloaded: true`.
4. **Move with `git mv`** (preserves history as renames): `git mv research/another-perspective thinking/another-perspective`.
5. **Trim the SOURCE categories' DESCRIPTION.md** so they no longer advertise the moved skills (e.g. drop "office hours frameworks (YC, Sahil)" from research's DESCRIPTION after moving them out).
6. **Add the new category row to CLAUDE.md's category table** (AGENTS.md symlinks to it). Keep the table's existing order.
7. **Regenerate**: `python3 scripts/generate_catalog.py` rewrites CATALOG.md + README.md.
8. **A nested sub-skill rides along.** If a moved skill contains a nested sub-skill (its own `SKILL.md` in a subdir, e.g. `yc-office-hours/plan-design-review/`), the catalog counts it too — so the new category's count can be N+1 vs the N skills you moved. That's correct, not a bug; don't "fix" it.

### After a move, audit what BREAKS (path-based) vs what SURVIVES (name-based)

When the user follows up with "do any other things reference these skills? correct those," the discriminator is: **skill-to-skill invocations resolve by skill NAME, not folder path, so they survive a `git mv` untouched. Only things that group skills by CATEGORY or hardcode a path break.** Don't mass-edit every match a grep returns — most are fine.

Run the audit, then triage:
```bash
cd ~/.hermes && grep -rn -E "oldcat/(skillA|skillB)|moved-skill-name" \
  config.yaml cron/ memories/ plugins/ skills/ \
  --include="*.md" --include="*.yaml" --include="*.yml" --include="*.json" --include="*.py" 2>/dev/null \
  | grep -vE "/skills/<newcat>/|/\.git/|/\.worktrees/|/\.archive/|/\.curator_backups/|CATALOG.md|README.md|plans/archive/|/output/|\.usage\.json|sessions/"
```
The exclude list is doing real work: `cron/output/`, `.curator_backups/`, `.usage.json`, and `sessions/` produce HUNDREDS of historical/generated matches that are noise — never edit those. (A bare `grep -rn` without the source-tree filter, or against `~/` including `sessions/`, will dump megabytes and time out.) After filtering, classify the survivors:

- **BREAKS — fix these:** files that list pinned skills BY CATEGORY (`skills-meta/skill-preloading/SKILL.md` has a `**research:** a, b` line), the category table in `skills/CLAUDE.md`/`AGENTS.md`, and source-category `DESCRIPTION.md`s that still advertise the moved skill. These are path/category-coupled and now wrong.
- **SURVIVES — leave alone:** every `**skill-name**: for X` cross-reference in another skill's SKILL.md/references, `cron/jobs.json` `skills` arrays (bare names), and `INSTALL.md` use-case bundles (bare names). They resolve by name; the move is invisible to them. Re-verify the catalog regenerates clean (`generate_catalog.py`) and report the BREAKS-fixed / SURVIVES-left split rather than silently editing everything.

### Decoupling the runtime skills clone from its public origin (auto-backup hide block)

If `skills/.git` no longer exists (the public `exiao/skills` clone was removed and skills now live as plain files inside the `hermes-backup` repo), the auto-backup script's `skills/.git` hide/restore block (`mv skills/.git skills/.git-hidden` around `git add -A`) becomes DEAD CODE — the `if [ -d skills/.git ]` never fires. When the user says "remove the hiding, it's handled separately now," verify the premise first (`ls -ld skills/.git`, `git -C skills rev-parse --show-toplevel` should resolve to `~/.hermes`, not skills/), then delete the block AND its now-stale comments (the "temporarily hide it / submodule gitlink" and "dirty submodule" rationale comments are no longer true). `bash -n bin/auto-backup.sh` to confirm syntax. The inert `skills/.git/` + `skills/.git-hidden/` lines in `.gitignore` are harmless guards — leave them unless asked. Removing the block does NOT change that backup still pushes all of `~/.hermes` (skills included) to the private mirror; it never pushed to `exiao/skills`.

### Gotcha: a malformed DESCRIPTION.md crashes generate_catalog.py for the WHOLE repo

`scripts/generate_catalog.py` calls `parse_simple_frontmatter` on every `*/DESCRIPTION.md` and RAISES `ValueError: <path> is missing YAML frontmatter` if any one of them lacks the opening `---` fence — aborting the entire regen, not just that category. This is a pre-existing landmine unrelated to your change (seen: `apple/DESCRIPTION.md` had body text but no leading `---`). When the generator dies on a DESCRIPTION.md you didn't touch, fix that file's frontmatter (wrap to `---\ndescription: <one line>\n---\n`) so the regen can complete; it's in-scope because the repo can't regenerate otherwise. After fixing, re-run and confirm `Generated CATALOG.md and README.md with <N> skills`.

## Bloat detection

A category is bloat if any of the following hold:

1. **Zero skills.** A directory has no `SKILL.md` files anywhere inside it (only DESCRIPTION.md stubs, scripts/, or assets/).
2. **DESCRIPTION-only subdirs.** Subdirectories contain only a DESCRIPTION.md with no actual skills beneath them (e.g. `mlops/evaluation/DESCRIPTION.md` but no skill dir).
3. **Namespace collision.** A category name exists both at root and as a subcategory elsewhere (`last30days/` at root and `marketing/last30days/`).
4. **Missing DESCRIPTION.md.** Categories without DESCRIPTION.md lack self-documentation.
5. **Project-specific content at root.** Categories like `ops-center/`, `reference/`, `yuanbao/` that are not reusable skill classes.

To audit quickly:
```python
import os
root = os.environ.get("REPO_ROOT", ".")
for name in sorted(os.listdir(root)):
    path = os.path.join(root, name)
    if os.path.isdir(path) and not name.startswith("."):
        skill_count = sum(1 for dp, dn, fn in os.walk(path) if "SKILL.md" in fn)
        has_desc = os.path.exists(os.path.join(path, "DESCRIPTION.md"))
        print(f"{name:30s} skills={skill_count} has_desc={has_desc}")
```

## Reorganization playbook

### 1. Decide destination for each category

- **Project-specific skills** (ops-center, reference, fintary, yuanbao) → move to `~/.hermes/skills/internal/` (already gitignored in `.gitignore`).
- **Overlapping category** with few skills (software-development, video-production) → merge skills into the richer existing category (`coding/`, `creative/video-production/`).
- **Empty bloat** (mlops with only DESCRIPTION stubs) → `git rm -r` the entire category.
- **Namespace collision** (last30days at root vs marketing/last30days/) → delete the one with 0 actual skills; the real skill lives under marketing/.

### 2. Always use a worktree

```bash
cd ~/projects/skills
git worktree add ~/projects/_worktrees/skills-reorg -b reorganize-categories origin/main
```

Work in the worktree. Do NOT copy/move files in the main working directory; accidental writes there pollute the runtime checkout.

### 3. Move/merge skills safely

```bash
cd ~/projects/_worktrees/skills-reorg

# Copy (do NOT move) skills into target category
# Use cp -R so the source stays intact until git rm is staged
cp -R software-development/spike coding/

# For project-specific skills, copy to ~/.hermes/skills/internal/
cp -R ops-center/ops-center-codebase-review ~/.hermes/skills/internal/
```

### 4. Remove old categories (git rm, never rm -rf)

```bash
# For tracked directories only
git rm -r ops-center reference yuanbao software-development video-production mlops

# If a directory is untracked (not in git), do NOT use git rm.
# Just remove it with your system's safe delete (trash/rm -d), then rm the empty dir.
```

Pitfall: `git rm` fails if the pathspec doesn't match tracked files. Check first:
```bash
git ls-files --error-unmatch "$dir" >/dev/null 2>&1 && echo tracked || echo untracked
```

### 5. Update README.md categories table

- Remove deleted category rows.
- Update skill counts for merged categories (e.g. coding 23 → 28).
- Keep the table sorted by the actual root directory listing.

### 6. Update README.md sections

Remove whole dead sections and their skill tables. Also remove or update the `## All Skills` subsections that list individual skills from deleted categories.

### 7. Update CLAUDE.md category table

CLAUDE.md usually has a smaller category table near the top. Remove rows for deleted categories there too, or they become stale instructions.

### 8. Stage and verify

```bash
git add coding/ creative/ README.md CLAUDE.md
git status --short
```

Expected: only renames (R), deletions (D), and modifications (M). No `??` untracked additions from the old paths.

### 9. Commit and PR

One logical change per PR. Do not mix skill content edits with category reorganization.
