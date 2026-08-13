# Changelog and Final Delivery (steps 7 and 8)

The per-experiment research log, the held-out test run, and what to hand back at the end.

## step 7: write the changelog

After each experiment (whether kept or discarded), append to `changelog.md`:

```markdown
## Experiment [N] — [keep/discard/regression/slow-update]

**Train score:** [X]% | **Val score:** [Y]%
**Edit ops:** [list of ops applied, e.g., "replace: swapped vague instruction for specific hex codes"]
**Apply report:** [N applied, M skipped, K errors]
**Hypothesis:** [Why this change was expected to help]
**Result:** [What actually happened — which evals improved/declined]
**Failure patterns:** [Clusters identified this round]
**Rejected-edit buffer:** [N entries, most recent: "..."]
```

This changelog is the most valuable artifact. It's a research log that any future agent (or smarter future model) can pick up and continue from.

---

## step 8: final evaluation and delivery

### 8a. run held-out test set

**Only if a held-out test set exists.** The degraded splits (5-7 inputs create no
test set; 4 or fewer create no split at all) leave nothing to score here. In those
minimum-input runs, skip this step and report "no honest test score (insufficient
inputs for a held-out set)" instead of inventing a test result, deliver the train
and validation deltas only.

When a test set exists, score the **test inputs** (never seen during optimization)
for the first time. Run them through BOTH `SKILL.md.baseline` (to get the honest
baseline test score) and the best optimized skill, using the **target model**. The
delta between the two is the honest improvement number.

**Overfitting warning:** If val_score improved significantly but test_score didn't, the optimization overfit to the validation set. Flag this explicitly in the summary.

### 8b. deliver results

Present:

1. **Score summary:** Baseline → Final for each set that exists (train, val, and test when a held-out test set was created; otherwise state the test score is unavailable)
2. **Total experiments run:** How many mutations were tried
3. **Keep rate:** How many mutations were kept vs discarded
4. **Top 3 changes that helped most** (from the changelog)
5. **Remaining failure patterns** (what the skill still gets wrong)
6. **Slow update history** (how many longitudinal checks, what regressions were caught)
7. **Rejected-edit buffer** (what was tried and failed, for future reference)
8. **The improved [user-chosen-name].md** (in the working directory, original SKILL.md untouched)
9. **Location of all artifacts** for reference

Include only the items that carry information for this run. A three-experiment run does not need a slow-update section or a rejected-edit dump.

**The original SKILL.md is NEVER modified.** Do NOT offer to overwrite it. Do NOT copy the working file over it. The user decides what to do with the improved version.
