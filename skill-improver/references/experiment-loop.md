# The Experiment Loop (step 6 in full)

Every sub-step of the core optimization loop: parent selection, failure clustering, self-diagnosis, success analysis, edit proposal, merge, apply/run, regression guard, PACE gate, rejected-edit buffer, logging, slow update, and stopping criteria.

This is the core optimization loop. Once started, run autonomously until stopped.

### 6.0. select the parent from the Pareto frontier (the GEPA step)

Before diagnosing or mutating, pick WHICH candidate to branch from. Do **not** default to the single highest-`val_score` candidate, that greedy choice is what gets the loop stuck in a local optimum.

1. Read `score_matrix.json`: the per-task (`input_id` × `eval_name`, training set only) pass-rate of every candidate in `pool.json`. This is the diagram's Scores Matrix.
2. Compute the **Pareto frontier**: every candidate that is the best (or tied-best) on at least one task. A candidate winning even one task survives.
3. **Sample the parent** from the frontier, weighted by number of tasks won, tie-breaking toward smaller skill size (simplicity > coverage).
4. On the very first experiments the pool has one candidate (the baseline), so the frontier is that candidate and this step trivially returns it, identical to the old greedy behavior. The frontier only matters once KEEPs have grown the pool.

Full algorithm (frontier + weighted sampling + tie-break) in [references/pareto-selection.md](references/pareto-selection.md). Validation is never used for selection, it stays a pure accept/reject gate (6f).

The rest of step 6 (diagnosis, mutation, gating) operates on the **sampled parent**, not on "the current best." Where steps below say "the working copy," read it as "a working copy seeded from the sampled parent."

### 6a. failure pattern clustering (optimizer model)

Don't pre-digest failures into a paragraph and hand the optimizer a summary. That aggressive feedback compression is exactly what Meta-Harness (arxiv 2603.28052) identifies as why text optimizers underperform on skill code: the summary tells you the failure's destination ("failed the accuracy eval"), not the wrong turn that caused it. Instead, run the **optimizer model** as a short agentic loop with file-read tools scoped to `autoresearch-[skill-name]/`, and let it investigate the full execution traces before proposing anything. Full protocol (the trace archive layout, the proposer prompt, cross-candidate comparison, cost bounds): [references/meta-harness-proposer.md](references/meta-harness-proposer.md).

The proposer reads, for the failing runs on the **sampled parent** (`cand_<parent_id>`):
- `traces/cand_<parent_id>/run_*.md`, the FULL trace of each run: every tool call, every intermediate turn, retries, and the exact step where the run diverged (not just the final output).
- `score_matrix.json` / `results.json`, per-task scores for every candidate.
- `rejected_edits.json`, edits already tried (do not repeat these or minor variants).
- any `cand_<id>.md` source it wants to compare against.

It must find the exact step each failing run went wrong, citing the trace lines that prove it, and, when a prior candidate passed an input the parent fails, diff the right run against the wrong run on that same input (the highest-signal evidence available). Then it groups failures by root-cause pattern, reports how many runs share each, and recommends the single highest-impact pattern to fix.

Log the failure patterns AND the cited trace evidence (file + line) in the experiment record, so a later reviewer can audit why an edit was made.

### 6a.5. post-failure self-diagnosis (target model)

For each failing run on the training set, replay the input to the **target model** (not the optimizer) with this prompt:

> "You previously attempted this task and produced: [failing output]. The expected behavior was: [eval criteria that failed]. You were wrong. What would need to change in your instructions for you to get this right?"

Collect all self-diagnoses and pass them to the optimizer model in step 6c (edit proposal) as additional signal alongside the failure clusters. The target model has information about its own reasoning chain that the optimizer can only infer from the outside.

**Key caveat:** Treat self-diagnoses as clues, not truth. The target model's self-analysis is biased (it rationalizes its own mistakes). The optimizer should weigh self-diagnoses alongside its own failure clustering, not defer to them. If the self-diagnosis contradicts the failure cluster analysis, the optimizer's analysis takes priority.

**Cost control:** This step adds one LLM call per failing run. If more than 5 runs failed, sample the 5 most representative failures (one per failure cluster from step 6a) rather than replaying all of them. The step is optional on target models that already self-critique; the optimizer's trace clustering in step 6a is the higher-signal path.

### 6b. success pattern analysis (optimizer model)

If there are passing outputs on the training set, also analyze them:

"Here are [N] successful outputs. The current skill is: [skill content].

Identify behavior patterns that are common across them and NOT already covered by the current skill. Only propose additions if the patterns are genuinely non-obvious and generalizable. Do not propose changes that would fix failures; that's handled separately."

Success-derived edits are lower priority than failure-derived edits. If both target the same area, keep the failure edit. Skip this step if all outputs are failing (nothing to analyze).

### 6c. propose structured edits (optimizer model)

Based on the failure clustering (and optionally success analysis), propose edits in structured JSON format:

```json
{
  "reasoning": "why these edits address the highest-impact failure pattern",
  "edits": [
    {"op": "replace", "target": "exact text to find in skill", "content": "replacement text"},
    {"op": "append", "content": "new section to add at end"},
    {"op": "insert_after", "target": "heading or text to insert after", "content": "new content"},
    {"op": "delete", "target": "exact text to remove"}
  ]
}
```

See [references/structured-edits.md](references/structured-edits.md) for the full edit op spec, protected region rules, and fallback behavior.

**Key rules:**
- Edits targeting content between `<!-- SLOW_UPDATE_START -->` and `<!-- SLOW_UPDATE_END -->` are automatically skipped (protected region).
- `append` inserts before the SLOW_UPDATE markers if they exist.
- If the LLM produces freeform text instead of JSON, treat the entire response as an `append` op.
- Generate a per-edit apply report: `{op, target_preview, content_preview, status}` where status is one of: `applied`, `skipped_protected`, `skipped_not_found`, `error`.

### 6c-merge. System Aware Merge (optimizer model, alternative to 6a-6c)

Mutation branches from ONE parent. When the Pareto frontier has **≥2 distinct members**, with probability ~0.3 skip the 6a→6c mutation path and instead produce the child by **merging two frontier parents** section-by-section.

1. Sample 2 distinct candidates A and B from the frontier (same task-win weighting as 6.0).
2. Split each SKILL.md into sections by `##`/`###` headings. For each section: if it evolved (differs from `SKILL.md.baseline`) in exactly one parent, take that parent's version; if both evolved it, ask the optimizer model to merge the two variants; if neither, keep the baseline version.
3. The merged child is a candidate like any other: it passes through the same regression guard (6e) and validation gate (6f), and a discard goes to the rejected-edit buffer tagged `"strategy": "merge"`.

Never recombine the SLOW_UPDATE protected region, the merged child inherits that block verbatim from the higher-`val_score` parent. Full algorithm and the optimizer merge prompt: [references/system-aware-merge.md](references/system-aware-merge.md).

### 6d. apply edits and run training set (target model)

1. Apply the structured edits to `[user-chosen-name].md` with protected-region checks.
2. Log the apply report.
3. Run the updated skill on **training inputs** using the **target model**.
4. **Capture the full execution trace of every run** to `traces/cand_<id>/run_<input>_r<n>.md`, the verbatim tool calls, arguments, results/errors, intermediate turns, retries, and final output, NOT a summary. This is the evidence the next round's proposer (6a) reads. Format and retention rules: [references/meta-harness-proposer.md](references/meta-harness-proposer.md). The candidate's `<id>` is assigned now (it becomes a pool member only if 6f KEEPs it; if discarded, its traces are retained for the last 3 rounds then pruned).
5. Score every output against every eval, and record each run's per-eval verdict (with the grader's reason) into the head of its trace file so the proposer sees scores and trace together.

### 6d.5. self-diagnostics capture

After each run completes but before scoring, ask the **target model** to report on its own execution:

> "You just completed this task. Before I score your output, report any moments where you: (a) lacked sufficient context to be confident, (b) guessed or assumed instead of verifying, (c) had a tool call fail or return unexpected data, (d) were unsure which approach to take. Report each as: `DIAGNOSTIC: [category] [one-line description]`. Categories: `missing_context`, `guessed`, `tool_failure`, `low_confidence`, `none`. If everything went smoothly, report `DIAGNOSTIC: none`."

Log diagnostics alongside eval scores in `results.json` under a `"diagnostics"` array per run:

```json
{"input": "...", "diagnostics": [
  {"category": "missing_context", "description": "No reference file for enterprise pricing tiers"},
  {"category": "guessed", "description": "Assumed USD currency without checking"}
]}
```

During failure clustering (step 6a), the optimizer model receives diagnostics alongside failing outputs. A failure where the agent reported low confidence is a higher-signal fix target than a silent failure, because the agent already knows what went wrong. Surface diagnostic frequency in the dashboard: a skill that reports `guessed` on 40% of runs has a calibration problem, not just an output quality problem.

Self-diagnostics also feed into refusal eval design: if the agent consistently reports `missing_context` on certain input types, those are candidates for refusal inputs.

### 6e. regression guard

Before proceeding to validation, check for regressions on the training set:

1. Compare per-eval pass/fail against the **last ACCEPTED (kept) experiment's** pass history, not just the previous record (which may be a discarded candidate). Track per-eval pass history keyed to the accepted-best state.
2. **Golden case check (strict):** If ANY golden case regresses on ANY eval, **discard immediately**: revert `[user-chosen-name].md` to the accepted best (`[user-chosen-name].md.best`) and log the discard reason as `"golden_case_regression"` in the rejected-edit buffer. No exceptions, regardless of net score improvement. Golden cases are the "memory of bugs you refuse to reintroduce."
3. If any non-golden eval that was previously passing now fails on any training input: regression detected.
4. If the net training score is lower or equal after the regression: **discard immediately**, revert `[user-chosen-name].md` to the accepted best (mandatory, or the next experiment builds on the rejected edit), skip the validation gate, and add to the rejected-edit buffer with a "regression" tag.
5. If the net training score is still higher despite the regression: proceed to validation gate (the improvement outweighs the regression).

Track per-eval pass history across experiments so you always know what was passing before.

### 6f. validation gate: PACE acceptance (target model)

Run the updated skill on **validation inputs** using the **target model**. Score
every output. The keep/discard decision is made by the **PACE acceptance gate**
(`scripts/pace_accept.py`), NOT by a greedy "val score went up" comparison. The
greedy rule is uncontrolled adaptive multiple testing, across a long run it
p-hacks itself into churn. PACE is the mechanism this loop exists for; route every
accept decision through it. See [references/pace-acceptance.md](references/pace-acceptance.md).
For running this loop as a long-lived background lane, see
[references/hill-climber-lane-runbook.md](references/hill-climber-lane-runbook.md).

1. Build the **paired** per-instance reward arrays on the SAME validation instances,
   same order: `candidate_scores[i]` and `incumbent_scores[i]` (the incumbent =
   the **sampled parent**; cache its per-instance val scores so you only re-run the
   candidate). With multiple runs per instance, average the runs into one score per
   instance so the arrays stay paired and equal-length.
2. Call the gate:

   ```python
   from scripts.pace_accept import pace_accept
   dec = pace_accept(candidate_scores, incumbent_scores,
                     alpha=0.05,
                     reward_kind="score",          # "exit_code" for deterministic harnesses
                     reward_range=R,               # a-priori reward span (max-min); strict guarantee
                     min_instances=8)
   ```

   For a **deterministic/binary** harness (exit-code 0/1, pytest pass/fail with no
   sampling variance) pass `reward_kind="exit_code"`: the gate takes the exact
   golden-case fast-path (commit iff the candidate improved on every paired instance,
   any per-instance regression rejects). `reward_range` (the harness's known max−min
   score span) is **required** so the e-process uses the strict, non-peeking
   normalizer, it is a fixed a-priori constant, set before seeing data.
3. Act on `dec.verdict`, this IS the accept decision, no separate greedy check:
   - **`commit`** → **KEEP.** The e-process crossed 1/alpha: a statistically-real
     gain. Add the new candidate to `pool.json` (with its `parent_id`, or `parents`
     pair for a merge, its per-task matrix slice, and train/val scores) and write its
     per-task training results into `score_matrix.json`. If it is also the highest
     `val_score` candidate seen so far, snapshot it as the global best: copy
     `[user-chosen-name].md` to `[user-chosen-name].md.best` and record its hash in
     `checkpoint.json` as `best_skill_hash`.
   - **`reject`** → **DISCARD.** The gain (if any) is not distinguishable from noise
     at level alpha. Revert the working copy to the sampled parent; log the discard
     (step 6g) with the PACE diagnostics (`wealth`, `threshold`, `n_used`, `mean_diff`).
   - **`continue`** → **underpowered:** fewer than `min_instances` paired validation
     instances. Do NOT commit on too-few samples. Gather more validation instances if
     you can; otherwise this is the lane's signal to **BLOCK for a bigger held-out
     set** rather than guessing.
4. **Log the full `PaceDecision`** (verdict, wealth, threshold, n_used/n_total,
   mean_diff, trace) into the experiment record so every keep/reject is
   auditable as a measured number, not a judgment call.

Comparing against the **sampled parent** (not the global best) is what lets a
non-best frontier candidate improve along its own lineage: a child only needs to beat
the parent it branched from (and survive the PACE gate against it) to earn a place in
the pool. The hard golden-case regression check (step 6e) still runs first and is an
unconditional discard regardless of the PACE verdict.

### 6g. handle discard: rejected-edit buffer

When an edit is discarded, add it to `rejected_edits.json`:

```json
{
  "experiment_id": 3,
  "edits": [{"op": "replace", "target": "...", "content": "..."}],
  "hypothesis": "why this was expected to help",
  "train_score_before": 75.0,
  "train_score_after": 70.0,
  "val_score_before": 65.0,
  "val_score_after": 60.0,
  "reason": "regression on eval 2: text legibility",
  "evals_regressed": ["Text legibility"]
}
```

Cap the buffer at the last 10 entries. Inject the buffer into the failure clustering prompt (step 6a) so the optimizer model doesn't repeat ineffective edits.

### 6h. log and checkpoint

After every experiment (kept or discarded):
1. Append to `results.tsv`
2. Update `results.json` (dashboard data)
3. Update `rejected_edits.json` (if discarded)
4. Update `pool.json` and `score_matrix.json` (if kept, the candidate and its per-task scores join the pool that 6.0 samples from)
5. Update `checkpoint.json`: `{last_experiment, best_val_score, best_experiment, slow_update_count, best_skill_hash, split, pool_ids}` (keep the persisted split membership and pool intact across saves)
6. Append to `changelog.md` (see step 7)

### 6i. slow update (every 5 experiments)

Every 5th experiment, pause the fast loop and run a longitudinal regression check:

1. Re-run the **training inputs only** through TWO skills using the **target model**:
   - (a) the original `SKILL.md.baseline`
   - (b) the current best `[user-chosen-name].md`

   Training only, validation stays a pure gate (6i.6), so val outcomes never feed the guidance prompt.
2. Classify each training input into one of four categories:
   - **improved**: was failing with baseline, now passes with current
   - **regressed**: was passing with baseline, now fails with current
   - **persistent_fail**: fails with both
   - **stable_success**: passes with both
3. If previous slow-update guidance exists, include it for reflection.
4. Send the comparison to the **optimizer model**:

   "Here is a longitudinal comparison of the same [N] training tasks under the original skill vs the current optimized skill after [M] experiments.

   Improved: [list]
   Regressed: [list]
   Persistent failures: [list]
   Stable successes: [list]

   Previous guidance (active during the last round of optimization):
   [previous guidance or '(none, this is the first slow update)']

   Which parts of the previous guidance helped? Which hurt? Which persistent failures remain unaddressed?

   Write 2-4 high-level guidance notes for the next round of optimization. These will be injected into a protected section of the skill that step-level edits cannot modify."

5. Write the guidance into the working skill copy between `<!-- SLOW_UPDATE_START -->` and `<!-- SLOW_UPDATE_END -->` markers. If these markers don't exist yet, add them at the end of the skill.
6. **Gate the guidance like any other mutation.** Re-score train and validation independently. Keep the guidance only if train improves and validation doesn't regress; otherwise revert it (or remove it on the first slow update) and log `"rejected"` in `slow_updates.json`. Update `[user-chosen-name].md.best`/`best_skill_hash` if kept.
7. Each accepted slow update overwrites the previous guidance (not accumulating).
8. Log to `slow_updates.json`.

### 6j. stopping criteria

**NEVER STOP to ask the user if you should continue.** They may be away from the computer. Run autonomously until:
- The user manually stops you
- You hit the budget cap (if one was set)
- You hit 95%+ val_score for 3 consecutive experiments (diminishing returns)
- **Saturated training set:** all training outputs pass but validation still fails or
  stays below threshold. The optimizer then has no training failure clusters to drive
  6a/6c, so the loop has no actionable signal. When this happens, stop and report an
  overfitting / data-coverage warning, and recommend adding or reshuffling more
  training inputs rather than looping with nothing to fix.
