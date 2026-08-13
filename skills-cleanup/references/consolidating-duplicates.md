# Consolidating Duplicates Within Runtime

How to find near-duplicate runtime skills, salvage unique content before archiving, and drive the merge through the curator CLI.

## Detecting & Resolving Duplicates Within Runtime (no exact-name collision required)

Exact-name collision across categories is rare, `find . -name SKILL.md | awk -F/ '{print $(NF-1)}' | sort | uniq -d` often returns nothing even when redundant skills exist. The real duplicates are **near-dupes**: two differently-named skills covering the same class (`devops/porkbun` stub vs pinned `external-services/porkbun-cli`; `software-development/simplify-code` vs pinned `coding/simplify`). Find them by eyeballing the flat name list for obvious pairs (`X` / `X-cli`, `Y` / `Y-code`, `simplify` / `simplify-code`), then for each candidate pair compare: identical/near-identical `description:`, line count + file count (`wc -l`, `find DIR -type f | wc -l`), and which one is `preloaded: true`. The thin, unpinned, or stub copy (e.g. one whose routing table points at sub-skill files that don't exist) is the one to retire; the fuller pinned one is canonical.

**Before archiving a near-dupe, salvage its unique content into the canonical, don't just delete.** Read BOTH SKILL.md bodies and diff what the retiree teaches that the keeper lacks. A "stub" often adds nothing (the porkbun root skill duplicated the CLI skill's coverage with a broken routing table → pure delete). But a real alternative implementation usually has ONE genuinely unique idea worth porting (`simplify-code`'s sole contribution was the **parallel 3-reviewer fan-out**, reuse/quality/efficiency reviewers via batch delegation, which `coding/simplify` lacked). Port that subsection into the canonical via `patch` FIRST, then archive the dupe. This is salvage-then-cut, the same triage as Mode 3 of the `simplify` skill.

**After archiving, scrub the generated indices** or stale entries linger and mislead future `skills_list`/lookup:
- `CATALOG.md`, delete the row(s) for the archived skill(s): `sed -i '' '/\[<name>\](<category>\/<name>\/)/d' CATALOG.md`
- `.bundled_manifest`, delete the `<name>:<hash>` line: `sed -i '' '/^<name>:/d' .bundled_manifest`
- Then grep to confirm nothing else references the archived names by name (SOUL.md, cron config, other skills' `references/`): `grep -rn "<name>" ~/.hermes/skills ~/.hermes/cron ~/.hermes/SOUL.md | grep -v skills-archive`. Only generated-index hits should remain after the sed passes; a live reference means you broke a dependency and must repoint it.

Archive dirs are date-stamped for recoverability: `mv devops/porkbun ~/.hermes/skills-archive/porkbun-stub-$(date +%Y%m%d)`.

## Driving Consolidation Through the Curator CLI (preferred over hand-rolled mv)

There is now a built-in curator (`hermes curator`) that owns runtime-skill lifecycle. For a manual consolidation it is the right tool, not raw `mv` into `~/.hermes/skills-archive/`: it takes a recoverable snapshot, archives to `~/.hermes/skills/.archive/` (restorable by name), and keeps `.usage.json` telemetry consistent. The curator's OWN dry-run is also the best way to GET a consolidation plan you can execute by hand:

```bash
# set a cheap aux model FIRST if you'll run the LLM pass (else it bills your main chat model)
# then preview merges + the rename map without mutating anything:
hermes curator run --consolidate --dry-run        # writes ~/.hermes/logs/curator/<ts>/REPORT.md
cat ~/.hermes/logs/curator/$(ls -t ~/.hermes/logs/curator | head -1)/REPORT.md
```

The dry-run's `--consolidate` stdout cuts the LLM summary mid-sentence; read the full proposal from `REPORT.md` / `run.json` in the run dir, not the stdout tail. `consolidate` defaults OFF in config and the dry-run mutates nothing, so this is safe to run any time to audit the library. The auto-transition pass leaves `use=0 never-triggered` skills alone (it treats `use=0` as absence-of-evidence, not staleness), so a clean library legitimately yields few/no auto-archives.

Execute an approved merge by hand:

```bash
hermes curator backup                              # explicit snapshot (run also auto-backs-up)
hermes curator archive <absorbed-skill>            # -> ~/.hermes/skills/.archive/<name>, recoverable
hermes curator restore <name>                      # undo
hermes curator list-archived                       # confirm
hermes curator status | grep -A4 'agent-created'   # confirm the count dropped
```

**Package-integrity merge discipline (re-home, fold, THEN archive, never flatten):**
1. **Re-home support files first.** If the absorbed skill ships `scripts/`/`references/`/`templates/`/`assets/`, `mv` them into the umbrella's matching dir and rename to a descriptive, non-colliding basename (e.g. `references/pr-773-example.md` -> `verbatim-persona-corpus/references/sources-md-pr-773-example.md`). Do NOT flatten only `SKILL.md` into another skill's `references/` and orphan its scripts.
2. **Fold only the UNIQUE content.** Diff both bodies; the umbrella often already covers most of the territory. Add a labeled subsection for what the retiree genuinely teaches that the keeper lacks, plus a one-line pointer to each re-homed support file. (Real session: `notion` already had the full "Restructuring a Page" section, so only the bulk-callout-inject + stale-URL-link-audit + dashed-vs-dashless-ID pieces needed folding.)
3. **`hermes curator archive` the now-absorbed skill**, then verify the umbrella's frontmatter still parses (`grep -m1 '^name:'`) and every re-homed file is present.

**When a skill is absorbed as a reference, update everything that named it.** A common consolidation shape is folding a whole skill into a bigger umbrella as `references/<topic>.md` (real: `research-summary-surge-page` → `surge-deploy`'s SKILL + `references/research-summary-page-style.md`). The absorbed skill's OLD name then survives as a dangling backtick reference in SOULs, crons, and other skills. Immediately after the merge, `grep -rl '<absorbed-name>' ~/.hermes/skills ~/.hermes/profiles/*/SOUL.md ~/.hermes/cron` and repoint each hit to "the `<umbrella>` skill" (or its specific reference file), and add the umbrella's category symlink into any consuming profile that lacks it. This is the write-side counterpart to the read-side "A Referenced Skill Reports 'Missing'" playbook below.

**Cross-category merges need explicit user sign-off.** Absorbing a skill from a PUBLIC category (e.g. `visual-design/`) into a gitignored `internal/` one removes its content from the public skills surface. The curator flags this as a reviewer caveat and defers; surface it to the user before executing and do not silently take it (real case: `live-demo-backends` (visual-design) -> `static-site-instant-db` (internal) pulled the chat-UI multiplayer patterns off the public surface, landed only because the user explicitly OK'd all three merges).
