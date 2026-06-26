# System Aware Merge (crossover operator)

GEPA's second proposal strategy (Agrawal et al. 2026, arxiv 2507.19457, Figure 1, right column: "System Aware Merge"). The reflective-mutation path produces a child from ONE parent; merge produces a child from TWO frontier parents by recombining their sections. SKILL.md step 6c-merge points here.

---

## why crossover

Mutation explores locally around one parent. Merge does something mutation can't: it combines a module that evolved well in candidate A with a different module that evolved well in candidate B, in a single step. If A learned to handle task T (by improving section X) and B learned to handle task U (by improving section Y), their merge can handle both T and U immediately. This is how the Pareto pool's diversity gets *consolidated* instead of just maintained.

---

## when to merge vs mutate

At step 6c, choose the proposal strategy probabilistically:

- **Merge** with probability ~0.3, but ONLY when the Pareto frontier has ≥2 distinct members. Otherwise there's nothing to merge.
- **Reflective mutation** (the existing 6a→6c path) otherwise.

Tune the 0.3 down if merges keep getting discarded (the pool isn't diverse enough yet) or up if the frontier is wide and mutations are saturating.

---

## "modules" = SKILL.md sections

GEPA merges per-module in a compound AI system. Here, the modules are the SKILL.md's top-level sections (split on `##` / `###` headings). Treat each section as an independently-evolvable unit.

---

## the merge algorithm

Sample 2 distinct candidates A and B from the frontier (use the same task-win weighting as parent selection; see `pareto-selection.md`). Then, section by section:

```
for each section S (matched by heading across A and B):
    a_changed = (A.S != baseline.S)     # did this section evolve in A's lineage?
    b_changed = (B.S != baseline.S)     # did it evolve in B's lineage?

    if a_changed and not b_changed:  take A's S       # A improved it, B didn't
    elif b_changed and not a_changed:  take B's S     # B improved it, A didn't
    elif a_changed and b_changed:      ask optimizer  # both evolved → optimizer picks
    else:                              take baseline.S # neither touched it
```

The "did it evolve" test compares against `SKILL.md.baseline` (the frozen original), which is exactly why the baseline snapshot is kept around. A section is "evolved" if it differs from baseline, byte-for-byte after normalizing whitespace.

When both parents evolved the same section, send both versions to the **optimizer model**:

> "Two optimized variants of the same skill section are below. Variant A comes from a candidate strong on tasks [list]; variant B from one strong on tasks [list]. Produce a single merged section that keeps the improvements of both without contradiction. If they truly conflict, pick the one whose strengths cover more tasks. Return only the merged section text."

---

## guards

- **Never merge across the SLOW_UPDATE protected region.** The `<!-- SLOW_UPDATE_START -->`…`<!-- SLOW_UPDATE_END -->` block is owned by the slow-update process (6i). The merged child inherits this block verbatim from whichever parent has the higher val_score; the optimizer is not asked to recombine it.
- **Section-set mismatch.** If A and B don't have the same set of section headings (a prior mutation added/removed a section), include any section present in either parent: take it from whichever parent has it; if both have it, apply the rule above.
- **Same constraint pipeline.** A merged child is a candidate like any other. It goes through the full constraint check (size limit, growth cap, frontmatter integrity, non-empty body) and the minibatch eval gate (6f). No special-casing — merges that don't improve held-out val are discarded and logged to the rejected-edit buffer with `"strategy": "merge"`.

---

## logging

Record merges in `changelog.md` and `results.json` like any experiment, but tag the strategy and the parents:

```json
{
  "id": 9,
  "strategy": "merge",
  "parents": ["cand_4", "cand_7"],
  "merged_sections": {"## tool priority": "from_A", "## output format": "optimizer_merged"},
  "train_score": 88.0,
  "val_score": 84.0,
  "status": "keep"
}
```

This makes the candidate pool's branching structure (the diagram's tree) reconstructable: mutation children have one `parent_id`, merge children have a `parents` pair.
