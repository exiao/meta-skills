# Mega-file accretion: diagnosis and split

The decay pattern for a long-lived, append-only skill. Every session adds a reference file and
sometimes an inline section, nobody dedups. It fails S2, B2, and C4 at once.

## The four symptoms

- **Orphan references.** Reference files nothing points to, unreachable unless grepped by luck.
  Half the references orphaned is a hard C4 fail. Fix is wiring (a "Reference index" section
  grouping pointers by domain) plus consolidation.
- **Duplicate reference clusters.** Near-identical files on one topic (`gemini-cli-retry-after.md`,
  `gemini-cli-retry-fallback.md`, `gemini-cli-codeassist-fallback.md`). Each cluster of 2-5 files
  folds into one canonical. Diff before trashing so unique lines survive.
- **Inline/reference duplication.** The same troubleshooting body appears as an inline H3 in
  SKILL.md AND as a reference file, sometimes 2-3 times inline. `grep -nE "^### " SKILL.md`
  reveals repeats (three "Incognito" headers in one real case). Hoist inline bodies into
  references, leave one pointer.
- SKILL.md past 500 lines / 20KB, which breaks pointer-loading. Score this as the root cause,
  not as a collection of separate failures.

## Symptom check

```bash
cd <skill-dir>
# orphan check: reference files NOT pointed to from SKILL.md
comm -23 <(ls references/*.md | xargs -n1 basename | sort -u) \
         <(grep -oE 'references/[a-z0-9-]+\.md' SKILL.md | sed 's#references/##' | sort -u)
ls references/ | sort   # eyeball duplicate-topic clusters
```

If a large fraction of references are orphans (real case: 30 of 60), or you see 3-5 files on the
same topic, the file needs splitting, not editing.

## The split procedure

This took one 101KB / 1849-line file down to a 17KB / 268-line router, 60 references to 46,
zero orphans.

1. **Map clusters before touching anything.** Read the full SKILL.md. List its section headers and
   every reference filename. Identify duplicate-topic clusters (pick one canonical name each) and
   which inline sections are triplicated.
2. **Consolidate clusters with parallel subagents, diff before trash.** Delegate one merge per
   cluster: "read these N files, write ONE `references/<canonical>.md` consolidating under H2
   sections, preserve ALL code/commands/pitfalls verbatim, dedupe only identical sentences, add a
   TOC if over 100 lines, and report a coverage map (each source, which section absorbed it). Do
   NOT delete originals." The coverage map is the proof nothing was lost. Subagents run
   concurrently because each owns a non-overlapping file group. Cap at 5 concurrent merges, run
   the rest in a second wave. For 2 or 3 clusters, do the merges yourself.
3. **Verify canonicals exist and are substantial, THEN trash originals.** `wc -l` each new file.
   Only after confirming, `trash` (never `rm`) the superseded originals, so a merge that dropped
   something is recoverable.
4. **Rewrite SKILL.md as a router.** Keep inline the architecture everything builds on and the
   config facts. Replace the giant troubleshooting wall with a grouped "Reference index" (one-line
   pointer per file, by domain) and a compact symptom-to-reference quick-map table. Extract long
   inline command dumps and internals into their own reference files.
5. **Validate BOTH directions.** Re-run the orphan check AND the inverse (pointed-to but missing on
   disk, meaning broken links from your own index). Both must be empty. Then `skill_view(name)` to
   confirm it loads and every `linked_files` entry resolves. Re-check B2 (`wc -c SKILL.md` under
   20KB) and S2 (under 500 lines).

## Pitfalls

- When rewriting the index, don't leave "legacy pointer" lines for files you just trashed. The
  inverse check will catch them as broken links.
- Don't assert counts you can't verify (tool or toolset totals). Soften to a range or drop them
  rather than carry a wrong number forward.
