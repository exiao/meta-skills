---
name: skill-improver
description: "Eval-driven skill optimizer: runs a skill repeatedly, scores outputs against binary evals, mutates the prompt via structured edits, and keeps only changes that improve a held-out validation score (cross-model optimizer/target, three-way splits, golden cases, checkpoint resume). Use when: optimize/improve this skill, make this skill better, run autoresearch on, self-improve skill, benchmark/eval my skill, run evals on."
---

> **Source:** Karpathy autoresearch + SkillOpt (Microsoft Research, arxiv:2605.23904) + GEPA reflective prompt evolution (Agrawal et al., arxiv:2507.19457) + Meta-Harness end-to-end harness optimization (Lee et al., arxiv:2603.28052) + howtoeval.com (Ben Hylak, May 2026). See `references/structured-edits.md` for edit op spec, `references/eval-guide.md` for eval writing (including refusal evals, trajectory evals, and golden cases), `references/pitfalls.md` for known failure modes, `references/self-diagnostics.md` for the diagnostic capture protocol, `references/skillopt-architecture.md` for the SkillOpt comparison and roadmap, `references/pareto-selection.md` for GEPA-style Pareto frontier parent selection, `references/system-aware-merge.md` for the two-parent crossover operator, `references/meta-harness-proposer.md` for the full-trace filesystem-browsing edit proposer, `references/dashboard-and-data-formats.md` for the dashboard spec and artifact schemas, `references/worked-example.md` for a full run walkthrough and operational tips, `references/mutation-principles.md` for how to mutate well.

# Skill Optimizer

## the loop

Take any existing skill, define what "good output" looks like as binary yes/no checks, then run this loop:

1. **Audit and read the skill.** Run `skill-audit` on the target skill, then read SKILL.md and linked references. Capture obvious structural/routing issues, but do not edit yet.
2. **Gather the eval setup.** Confirm 8-12 test inputs, 3-6 binary evals, model config, run count, budget cap, and golden cases. Split inputs into train/validation/test.
3. **Establish the baseline.** Copy the unchanged skill into the working directory, run train + validation with the target model, score it, and create the dashboard/checkpoint.
4. **Score outputs with binary evals.** Include refusal evals and trajectory evals when the skill's failure mode depends on uncertainty or process, not just final text.
5. **Diagnose failures from full training traces.** Let the optimizer browse the per-candidate training execution traces (every tool call, every turn, the exact divergence step) plus train/selector scores and source, while keeping validation outputs and traces sealed, and cite where each failing run went wrong (Meta-Harness), instead of getting a compressed "which eval failed" summary. See `references/meta-harness-proposer.md`.
6. **Select a parent from the Pareto frontier.** Don't always mutate the single best. Keep every validation-accepted candidate that's best on at least one training task alive in a pool, and sample the parent weighted by train tasks won (GEPA-style). See `references/pareto-selection.md`.
7. **Propose one change.** Either a structured edit (append/insert_after/replace/delete) on the sampled parent, or — when the frontier has ≥2 members — a System Aware Merge of two frontier parents (`references/system-aware-merge.md`).
8. **Validate before keeping.** Reject any golden-case regression and any change that fails to improve held-out validation. Keep only measured improvements (added to the pool); log all rejects.
9. **Repeat, then seal it.** Use the rejected-edit buffer and slow updates until plateau/budget/user stop, then score the sealed test set once and deliver the single best file plus artifacts.

**Output:** An improved skill copy + `results.tsv` log + `changelog.md` of every mutation attempted + a live HTML dashboard you can watch in your browser. The original SKILL.md is never overwritten.

---

## why this exists

Most skills work about 70% of the time. The other 30% you get garbage. The fix isn't to rewrite the skill from scratch. It's to let an agent run it dozens of times, score every output, and tighten the prompt until that 30% disappears.

A separate (usually stronger) model analyzes failures while the target model executes, because the same model can't see its own blind spots.

---

## before starting: gather context

**STOP. Do not run any experiments until all fields below are confirmed with the user. Ask for any missing fields before proceeding.**

1. **Target skill** -- Which skill do you want to optimize? (need the exact path to SKILL.md)
2. **Test inputs** -- What 8-12 different prompts/scenarios should we test the skill with? (variety matters. These get split into train/validation/test sets. Minimum 5 for graceful degradation, but 8-12 is the target for three-way splits. See [references/eval-guide.md](references/eval-guide.md) for why this matters.)
3. **Eval criteria** -- What 3-6 binary yes/no checks define a good output? (see [references/eval-guide.md](references/eval-guide.md) for how to write good evals)
4. **Model configuration** -- Pick one of three options:

   | Config | Optimizer (analyzes) | Target (executes) | Best for |
   |--------|---------------------|-------------------|----------|
   | **A (default)** | claude-opus-4-6 | gpt-5.5 | Skills that run on OpenAI models in production. Opus catches GPT blind spots. |
   | **B** | gpt-5.5 | claude-opus-4-6 | Skills that run on Anthropic models in production. GPT catches Opus blind spots. |
   | **C (same model)** | session model | session model | Quick runs, cost-sensitive, or when you just want to iterate fast. |

   Default is **A** (opus optimizes, gpt executes). The key principle: the optimizer should be a different architecture than the target so it can see systematic biases the target can't. If the user doesn't specify, use A. If they say "same model" or "no cross-model," use C.
5. **Runs per experiment** -- How many times should we run the skill per mutation? Default: 3. (more runs = more reliable scores, but slower. 3-5 is the sweet spot.)
6. **Budget cap** -- Optional. Max number of experiment cycles before stopping. Default: no cap (runs until you stop it).
7. **Golden cases** -- Optional but recommended. Which test inputs are golden cases? Golden cases are scenarios that MUST always pass, typically derived from real production failures or critical user paths. They represent "bugs you refuse to reintroduce." Golden cases are always placed in the training set (never held out) so regressions are caught immediately. Any mutation that causes a golden case to regress on ANY eval is discarded instantly, regardless of net score improvement. If the user doesn't specify, ask: "Are any of these inputs critical paths that should never regress? Those become golden cases."

### data split

Inputs get split into three sets:

| Set | Share | Purpose | When used |
|-----|-------|---------|-----------|
| **Training** | 50% | Rollout + failure analysis + success analysis | Every experiment |
| **Validation** | 25% | Accept/reject gate (keep vs discard decision) | Every experiment |
| **Test** | 25% | Final honest evaluation (never seen during optimization) | Only at the very end |

Example with 8 inputs: 4 train, 2 validation, 2 test.

**Graceful degradation:** If the user provides only 5-7 inputs, fall back to a two-way split (60% train, 40% validation, no test set). If 4 or fewer, use all inputs for both training and validation (no split). Always tell the user what split you're using and why more inputs would help.

**Golden case placement:** Golden cases are always assigned to the training set, never randomized into validation or test. They are scored every experiment alongside regular training inputs. In the dashboard, golden cases are marked with a 🔒 indicator. In `results.json`, each input has an `"is_golden": true/false` field.

**Persist the split assignments.** Record which inputs landed in train/val/test (by ID or prompt text) in `checkpoint.json`, not just the counts. On resume, reuse that exact membership; reshuffling can leak a sealed test prompt into training.

---

## step 1: audit and read the skill

Before changing anything, audit and understand the target skill completely.

1. Run `skill-audit` on the target skill directory. Capture the scorecard and recommended fixes.
2. Read the full SKILL.md file.
3. Read any files in `references/` that the skill links to.
4. Identify the skill's core job, process steps, and output format.
5. Note any existing quality checks or anti-patterns already in the skill.
6. Separate audit findings into:
   - **Deterministic obvious fixes** (broken references, stale commands, malformed frontmatter, routing description issues)
   - **Behavioral hypotheses** that need eval evidence before changing

Do NOT skip this. The audit pre-pass finds low-hanging structural problems, but it does not replace the eval loop. Do not edit the original SKILL.md; pass deterministic audit fixes into the experiment loop by applying them only to the working copy as the first candidate mutation, or by including them in the optimizer prompt context as required edit context. They still pass through the baseline/validation gate.

---

## step 1.5: saturation pass (optional)

Before writing evals, review real executions of the skill to understand its actual failure modes. This step is **optional** for new or low-usage skills, but **mandatory** for high-value skills with production history (e.g. meta-ads-cli, memory-gc).

1. Search episode logs and session transcripts for 10-20 real executions of the target skill. Use the `recall` skill or `grep` through `~/.hermes/episodes/` and `~/.hermes/sessions/`.
2. For each execution, note:
   - Did it succeed or fail?
   - What was the failure mode? (wrong output, wrong process, silent failure, confabulation, tool error)
   - Did the user correct or work around anything?
   - Were there any surprising successes?
3. Stop when you hit **saturation**: the same failure patterns start repeating.
4. Use these patterns to inform both your test inputs (step 2's scenarios) and eval criteria (step 2's binary checks). Production failures make excellent golden cases (see item 7 in context gathering).

The goal is to avoid designing evals in a vacuum. Real usage reveals failure modes that synthetic test inputs miss.

---

## step 2: build the eval suite

Convert the user's eval criteria into a structured test. Every check must be binary: pass or fail, no scales.

**Format each eval as:**

```
EVAL [number]: [Short name]
Question: [Yes/no question about the output]
Pass condition: [What "yes" looks like — be specific]
Fail condition: [What triggers a "no"]
```

**Rules for good evals:**
- Binary only. Yes or no. No "rate 1-7" scales. Scales compound variability and give unreliable results.
- Specific enough to be consistent. "Is the text readable?" is too vague. "Are all words spelled correctly with no truncated sentences?" is testable.
- Not so narrow that the skill games the eval. "Contains fewer than 200 words" will make the skill optimize for brevity at the expense of everything else.
- 3-6 evals is the sweet spot. More than that and the skill starts parroting eval criteria back instead of actually improving.

See [references/eval-guide.md](references/eval-guide.md) for detailed examples of good vs bad evals.

### refusal evals (optional)

Some skills should refuse when they lack sufficient context, encounter out-of-domain queries, or receive stale/unreliable data. For these skills, add **refusal eval inputs**: test cases where the correct behavior is to say "I don't know" or "I can't reliably answer this."

```
REFUSAL_INPUT [number]: [Short description]
Scenario: [The input prompt]
Why refuse: [Why the skill should refuse rather than attempt an answer]
```

Refusal inputs use **inverted scoring**: the skill passes if it refuses (acknowledges uncertainty, declines to answer, flags insufficient data), and fails if it produces a confident answer. Include 2-3 refusal inputs alongside your normal test inputs. They participate in the same data split.

This matters most for skills that handle real data: financial data, user-facing research, production diagnostics. A confident wrong answer erodes trust faster than an honest refusal builds it.

### trajectory evals (optional)

Standard evals judge the final output. Trajectory evals judge the **process**: did the skill call the right tools in the right order? Did it retrieve context before generating? Did it check for errors?

```
TRAJECTORY_EVAL [number]: [Short name]
Question: [Yes/no question about the execution path, not the output]
Pass condition: [What the trajectory should include]
Fail condition: [What indicates a broken process]
```

Examples:
- "Did the skill load the reference file before generating output?" (context retrieval)
- "Did the skill call the data API before making claims about current prices?" (tool ordering)
- "Did the skill check for error responses before proceeding?" (error handling)

Trajectory evals require capturing the full tool-call sequence during each run. Log intermediate steps (tool names, order, key arguments) alongside the final output. A skill that produces correct output through a wrong process is fragile and will break on novel inputs.

**Max score calculation:** Train and validation sets differ in size, so compute their ceilings separately:
```
max_train = [number of evals] × [runs per experiment] × [number of training inputs]
max_val   = [number of evals] × [runs per experiment] × [number of validation inputs]
```
The test ceiling is computed the same way but only used at final evaluation.

---

## step 3: check for existing checkpoint (resume support)

Before creating anything new, check if `autoresearch-[skill-name]/` already exists with a `checkpoint.json` file.

**If checkpoint exists:**
0. If it has no `best_skill_hash` or the `[name].md.best` snapshot is missing, it's a half-written pre-baseline run — start fresh (step 4).
1. Read `checkpoint.json`: last experiment, best score/experiment, slow update count, and the split membership (which inputs are train/val/test). Reuse that exact membership; never re-split.
2. Read `results.json` for full experiment history
3. Read `rejected_edits.json` for the rejected-edit buffer
4. Read `slow_updates.json` for longitudinal comparison history
4b. Read `pool.json` and `score_matrix.json` to restore the candidate pool and per-task scores, and confirm `traces/` holds the per-candidate execution traces the proposer reads. If pool/matrix are missing on an otherwise-valid checkpoint (a pre-Pareto run), rebuild a single-member pool from `[name].md.best` as the resume seed (for example `cand_0` with `strategy: "resume_best"`, `experiment: best_experiment`, and `skill_file: "cand_0.md"`). Populate that seed's `score_matrix.json` row from the **best experiment's** training per-eval results if they were persisted; otherwise rerun `[name].md.best` on the recorded training split and overwrite the train-only matrix cells from those fresh scores. Never assign the original baseline's scores to a later `.best` unless the `.best` hash matches the baseline. If `traces/` is absent or missing the sampled candidate (a pre-Meta-Harness run), do a **training-only trace refresh before 6.0/6a proposes anything**: restore `[name].md.best` (or the frozen `skill_file` for each restored pool member you may sample), re-run that candidate on the recorded training split, capture `traces/cand_<id>/run_*.md`, and fill any missing train-only `score_matrix.json` cells from those runs. Do not run validation during this refresh and do not expose validation outputs; once the sampled candidate's traces exist, resume at 6.0 with trace-grounded proposal. Never let the first post-resume proposal fall back to stale summaries or empty evidence.
5. Restore `[name].md` from `[name].md.best` if it no longer matches `best_skill_hash` (a prior run was interrupted mid-mutation). Resume only from the last accepted state.
6. Tell the user: "Found existing run at experiment [N] with best val_score [X]%. Resume or start fresh?"
7. If resume: skip baseline, load all state, continue from experiment N+1
8. If fresh: move the old directory to `autoresearch-[skill-name]-backup-[timestamp]/` and start over

**If no checkpoint:** proceed to step 4 (baseline).

---

## step 4: generate the live dashboard

Before running any experiments, create the working directory `autoresearch-[skill-name]/` if it does not already exist (step 5 populates it; the dashboard write below needs it to exist first). Then create a live HTML dashboard at `autoresearch-[skill-name]/dashboard.html` and open it in the browser. It auto-refreshes from `results.json` and shows the train/validation score curves, per-experiment keep/discard bars, per-eval breakdown, rejected-edit buffer, diagnostics frequency, and golden case status.

The full dashboard requirements, the `results.json` schema, and the `results.tsv` schema are in [references/dashboard-and-data-formats.md](references/dashboard-and-data-formats.md).

**Critical:** the held-out test set is NEVER scored during the run. `results.json` carries only train and validation scores throughout; `final_test_score` is added once, at the very end (step 8).

---

## step 5: establish baseline

Run the skill AS-IS before changing anything. This is experiment #0.

1. **Ask the user what to name the new version.** Example: "What should I call the optimized version? (e.g., anti-slop-v2, anti-slop-optimized)" The user picks the name.
2. Create a working directory: `autoresearch-[skill-name]/` inside the skill's folder
3. **Copy the original SKILL.md into the working directory as `[user-chosen-name].md`** -- this is the copy you will mutate. NEVER edit the original SKILL.md. All mutations happen on this copy only.
4. Also save `SKILL.md.baseline` in the working directory (identical to the original -- this is your revert target and slow-update comparison anchor)
5. Create `results.tsv`, `results.json`, `rejected_edits.json` (empty array), `slow_updates.json` (empty array), and `dashboard.html`. Open the dashboard. Don't create `checkpoint.json` yet (step 9).
6. Run the skill using **only the train + validation sets** with the **target model**. Score every output against every eval. Capture the full execution trace of every training run to `traces/cand_0/run_*.md` (same format as step 6d) — the baseline traces are what the first proposer round reads. Leave the test set sealed until final evaluation (step 8).
7. Record the baseline: `train_score` and `val_score` independently. The test set is scored once, at step 8.
8. **Snapshot the baseline as the initial accepted best AND seed the candidate pool:** copy `[user-chosen-name].md` to `[user-chosen-name].md.best` and record its hash. Freeze the baseline pool member's skill text by also copying it to `cand_0.md`. Create `pool.json` containing this one baseline candidate (`id: "cand_0"`, `parent_id: null`, `skill_file: "cand_0.md"`) and write its per-task training pass-rates into `score_matrix.json`. The `cand_0.md` copy is what selection/merge read once the working copy advances or is restored from another parent. This is the accepted state and the single-member pool until the first KEEP.
9. Create `checkpoint.json` now (after the `.best` snapshot), with `best_skill_hash`, the split membership, and `pool_ids: ["cand_0"]` (schema in [references/dashboard-and-data-formats.md](references/dashboard-and-data-formats.md)).

**results.tsv format (tab-separated):**

```
experiment	train_score	val_score	max_train	max_val	status	description
0	70.0%	65.0%	12	6	baseline	original skill — no changes
```

**IMPORTANT:** After establishing baseline, confirm the score with the user before proceeding. If baseline is already 90%+, the skill may not need optimization. See [references/pitfalls.md](references/pitfalls.md) for why high baselines can be misleading.

---

## step 6: run the experiment loop

This is the core optimization loop. Once started, run autonomously until stopped.

### 6.0. select the parent from the Pareto frontier (the GEPA step)

Before diagnosing or mutating, pick WHICH candidate to branch from. Do **not** default to the single highest-`val_score` candidate — that greedy choice is what gets the loop stuck in a local optimum.

1. Read `score_matrix.json`: the per-task (`input_id` × `eval_name`, training set only) pass-rate of every candidate in `pool.json`. This is the diagram's Scores Matrix.
2. Compute the **Pareto frontier**: every candidate that is the best (or tied-best) on at least one task. A candidate winning even one task survives.
3. **Sample the parent** from the frontier, weighted by number of tasks won, tie-breaking toward smaller skill size (simplicity > coverage).
4. On the very first experiments the pool has one candidate (the baseline), so the frontier is that candidate and this step trivially returns it — identical to the old greedy behavior. The frontier only matters once KEEPs have grown the pool.

Full algorithm (frontier + weighted sampling + tie-break) in [references/pareto-selection.md](references/pareto-selection.md). Validation is never used for selection — it stays a pure accept/reject gate (6f).

The rest of step 6 (diagnosis, mutation, gating) operates on the **sampled parent**, not on "the current best." Where steps below say "the working copy," read it as "a working copy seeded from the sampled parent." The parent sampled by 6.0 has its own candidate `id` (call it `sampled_id`); do not confuse that with the lineage `parent_id` field stored on children in `pool.json`. The sampled candidate's failure outputs, diagnostics, and traces are not re-derived from the pool's pass-rate matrix — they are read from that candidate's own persisted `traces/cand_<sampled_id>/` archive, which 6d wrote when that candidate was first evaluated. The retention rule (see `references/meta-harness-proposer.md`) **never prunes a pool member's traces**, so even when 6.0 samples an older non-current candidate, 6a has that candidate's actual per-run failure text to diagnose from. The only exception is the resume repair in step 3.4b: if an old checkpoint lacks those traces, capture the sampled candidate's train traces before 6.0/6a, then continue.

### 6a. failure pattern clustering (optimizer model)

Don't pre-digest failures into a paragraph and hand the optimizer a summary. That aggressive feedback compression is exactly what Meta-Harness (arxiv 2603.28052) identifies as why text optimizers underperform on skill code: the summary tells you the failure's destination ("failed the accuracy eval"), not the wrong turn that caused it. Instead, run the **optimizer model** as a short agentic loop with file-read tools scoped to `autoresearch-[skill-name]/`, and let it investigate the full execution traces before proposing anything. Full protocol (the trace archive layout, the proposer prompt, cross-candidate comparison, cost bounds): [references/meta-harness-proposer.md](references/meta-harness-proposer.md).

The proposer reads, for the failing runs on the **sampled parent** (`sampled_id`, the candidate id returned by 6.0 — not the child's `parent_id` lineage field):
- `traces/cand_<sampled_id>/run_*.md` — the FULL trace of each run: every tool call, every intermediate turn, retries, and the exact step where the run diverged (not just the final output).
- `score_matrix.json` plus a proposer-safe history export — train/selector per-task scores, lineage, keep/discard status, and prior rejected edit hypotheses. Do **not** give the proposer raw `results.json` if it contains validation rows, per-validation-case failures, validation traces, or validation grader reasons.
- `rejected_edits.json` — edits already tried (do not repeat these or minor variants).
- any `cand_<id>.md` source it wants to compare against.

Validation remains an accept/reject gate only: 6f may record aggregate validation scores for the dashboard/checkpoint, but validation outputs, validation traces, and validation failure reasons must not enter the proposer-readable archive. If `results.json` is the dashboard source of truth, generate a separate train-only `proposer_context.json` (or equivalent in-memory view) for 6a instead of handing over the dashboard file.

It must find the exact step each failing run went wrong, citing the trace lines that prove it, and — when a prior candidate passed an input the parent fails — diff the right run against the wrong run on that same input (the highest-signal evidence available). Then it groups failures by root-cause pattern, reports how many runs share each, and recommends the single highest-impact pattern to fix.

Log the failure patterns AND the cited trace evidence (file + line) in the experiment record, so a later reviewer can audit why an edit was made.

### 6a.5. post-failure self-diagnosis (target model)

For each failing run on the training set, replay the input to the **target model** (not the optimizer) with this prompt:

> "You previously attempted this task and produced: [failing output]. The expected behavior was: [eval criteria that failed]. You were wrong. What would need to change in your instructions for you to get this right?"

Collect all self-diagnoses and pass them to the optimizer model in step 6c (edit proposal) as additional signal alongside the failure clusters. The target model has information about its own reasoning chain that the optimizer can only infer from the outside.

**Key caveat:** Treat self-diagnoses as clues, not truth. The target model's self-analysis is biased (it rationalizes its own mistakes). The optimizer should weigh self-diagnoses alongside its own failure clustering, not defer to them. If the self-diagnosis contradicts the failure cluster analysis, the optimizer's analysis takes priority.

**Cost control:** This step adds one LLM call per failing run. If more than 5 runs failed, sample the 5 most representative failures (one per failure cluster from step 6a) rather than replaying all of them.

### 6b. success pattern analysis (optimizer model)

If there are passing outputs on the training set, also analyze them:

"Here are [N] successful outputs. The current skill is: [skill content].

Identify behavior patterns that are common across them and NOT already covered by the current skill. Only propose additions if the patterns are genuinely non-obvious and generalizable. Do not propose changes that would fix failures; that's handled separately."

Success-derived edits are lower priority than failure-derived edits. If both target the same area, keep the failure edit. Skip this step if all outputs are failing (nothing to analyze).

### 6c. propose structured edits (optimizer model)

Based on the failure clustering (and optionally success analysis), propose edits in structured JSON format. If step 1 found deterministic obvious fixes, seed the first proposal with those deterministic fixes as the candidate mutation before proposing behavioral hypotheses:

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
2. Split each SKILL.md into sections by `##`/`###` headings (plus the YAML frontmatter as a pseudo-section). For each section: if it evolved (differs from `SKILL.md.baseline`) in exactly one parent, take that parent's version; if both evolved it, ask the optimizer model to merge the two variants; if neither, keep the baseline version; if exactly one parent deleted a baseline section, honor the deletion.
3. **Materialize the merged child into the working copy** (`[user-chosen-name].md`) before evaluating — the merge path skips 6a→6d's structured-edit application, so nothing else writes it. Reassemble the chosen sections and overwrite `[user-chosen-name].md`: emit baseline sections in baseline heading order, then any parent-added sections (present in a parent but not baseline) in that parent's original order, appended after the baseline body but before the SLOW_UPDATE block. Don't drop a new section just because it has no baseline slot — `system-aware-merge.md` treats a one-parent addition as an evolved section to include. Then continue at 6d step 3 (run training). Without this write, 6d would evaluate the unchanged parent / a no-op instead of the merged child.
4. The merged child is a candidate like any other: it passes through the same regression guard (6e, against the **better** of the two parents) and validation gate (6f), and a discard goes to the rejected-edit buffer tagged `"strategy": "merge"`.

Never recombine the SLOW_UPDATE protected region — the merged child inherits that block verbatim from the higher-`val_score` parent. Full algorithm and the optimizer merge prompt: [references/system-aware-merge.md](references/system-aware-merge.md).

### 6d. apply edits and run training set (target model)

1. Apply the structured edits to `[user-chosen-name].md` with protected-region checks.
2. Log the apply report.
3. Run the updated skill on **training inputs** using the **target model**.
4. **Capture the full execution trace of every run** to `traces/cand_<id>/run_<input>_r<n>.md` — the verbatim tool calls, arguments, results/errors, intermediate turns, retries, and final output, NOT a summary. This is the evidence the next round's proposer (6a) reads. Format and retention rules: [references/meta-harness-proposer.md](references/meta-harness-proposer.md). The candidate's `<id>` is assigned now (it becomes a pool member only if 6f KEEPs it; if discarded, its traces are retained for the last 3 rounds then pruned).
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

Before proceeding to validation, check for regressions on the training set. With Pareto selection the comparison baseline is the **sampled parent** (the lineage this child branched from in 6.0), not the global accepted-best — otherwise a child that improves a non-global frontier lineage but is still below the global best on some eval would be discarded here before the sampled-parent gate in 6f ever runs, defeating the whole point of keeping non-best lineages alive.

1. Compare per-eval pass/fail against the **sampled parent's** per-task pass history (from its `score_matrix.json` slice), not the global accepted-best and not the previous (possibly discarded) record. For a fresh 1-candidate pool the sampled parent *is* the accepted best, so this reduces to the old behavior.
2. **Golden case check (strict, against the global best):** Golden cases are absolute and lineage-independent. If ANY golden case regresses on ANY eval **relative to the global best**, **discard immediately**: revert `[user-chosen-name].md` to the working-copy parent it was seeded from and log the discard reason as `"golden_case_regression"` in the rejected-edit buffer. No exceptions, regardless of net score improvement. Golden cases are the "memory of bugs you refuse to reintroduce."
3. If any non-golden eval that was passing **on the sampled parent** now fails on any training input: regression detected.
4. If the net training score is lower or equal **versus the sampled parent** after the regression: **discard immediately** — revert `[user-chosen-name].md` to the working-copy parent it was seeded from (mandatory, or the next experiment builds on the rejected edit), skip the validation gate, and add to the rejected-edit buffer with a "regression" tag.
5. If the net training score is still higher **than the sampled parent's** despite the regression: proceed to validation gate (the improvement outweighs the regression).

After any 6e discard reverts the working copy to its seeded parent, **restore the global best into the working copy** (`copy [user-chosen-name].md.best → [user-chosen-name].md`) before continuing — the seeded parent may be a non-global pool member, and a following slow update (6i) or final stop (8) runs and ships `[user-chosen-name].md`. Equivalently, mutate sampled parents on a scratch copy and only ever leave `.best` in the working path. The candidate's traces under `traces/cand_<id>/` are kept per the retention rule even on discard, so nothing is lost.

Track per-eval pass history per candidate (in `score_matrix.json`) so you always know what each parent was passing before.

### 6f. validation gate (target model)

Run the updated skill on **validation inputs** using the **target model**. Score every output.

**Keep/discard decision based on validation score:**
- Val score improved over the **sampled parent's** val score (or, for a merge, over the **better** of the two parents — the higher-`val_score` one, so a merge can't regress against its stronger parent) → **KEEP.** Then:
  1. Reuse the **same `cand_<id>` assigned in 6d** (do not mint a new one) and **freeze its skill text**: copy the current `[user-chosen-name].md` to that candidate's `skill_file` (e.g. `cand_3.md`). Keeping the id stable is what lets a later 6a find this pool member's failures under the `traces/cand_<id>/` archive 6d already wrote; a fresh id here would orphan those traces. The pool schema's selection and merge steps read these frozen files, so a kept candidate must have one before the working copy is reverted or advances.
  2. Add it to `pool.json` (with its `parent_id`, or `parents` pair for a merge, its `skill_file`, its per-task matrix slice, and train/val scores) and write its per-task training results into `score_matrix.json`.
  3. If it is also the highest-`val_score` candidate seen so far, snapshot it as the global best: copy `[user-chosen-name].md` to `[user-chosen-name].md.best` and record its hash in `checkpoint.json` as `best_skill_hash`.
  4. **If it is NOT the new global best** (it only beat a lower-val sampled parent), restore the global best into the working copy before continuing: copy `[user-chosen-name].md.best` back over `[user-chosen-name].md`. The pool keeps the frozen `cand_N.md`, so nothing is lost, but the working copy / `.best` must stay the global best — later slow-update (6i) and final delivery (8) run and ship `[user-chosen-name].md`, so leaving a non-global candidate there would test/deliver the wrong artifact.

  The pool is what 6.0 samples from; `.best` is only the single artifact delivered at the end.
- Val score stayed the same → **DISCARD.** Revert the working copy to `[user-chosen-name].md.best`. The change added complexity without measurable improvement on held-out data.
- Val score got worse → **DISCARD.** Revert the working copy to `[user-chosen-name].md.best`.

Comparing against the **sampled parent** (not the global best) is what lets a non-best frontier candidate improve along its own lineage: a child only needs to beat the parent it branched from to earn a place in the pool.

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
4. Update `pool.json` and `score_matrix.json` (if kept — the candidate and its per-task scores join the pool that 6.0 samples from)
5. Update `checkpoint.json`: `{last_experiment, best_val_score, best_experiment, slow_update_count, best_skill_hash, split, pool_ids}` (keep the persisted split membership and pool intact across saves)
6. Append to `changelog.md` (see step 7)

### 6i. slow update (every 5 experiments)

Every 5th experiment, pause the fast loop and run a longitudinal regression check:

1. Re-run the **training inputs only** through TWO skills using the **target model**:
   - (a) the original `SKILL.md.baseline`
   - (b) the current best `[user-chosen-name].md`

   Training only — validation stays a pure gate (6i.6), so val outcomes never feed the guidance prompt.
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
6. **Gate the guidance like any other mutation.** Re-score train and validation independently. Keep the guidance only if train improves and validation doesn't regress; otherwise revert it (or remove it on the first slow update) and log `"rejected"` in `slow_updates.json`. If kept, update `[user-chosen-name].md.best`/`best_skill_hash` **and register the accepted skill as a full pool candidate**: assign it a fresh `cand_N` id, capture and write its train-run execution traces under `traces/cand_N/run_*.md` (same format and retention as 6d — without these the proposer's full-trace contract breaks the next time this member is sampled), freeze it to `cand_N.md`, add it to `pool.json` (with `parent_id` = the best it was built on, `skill_file`, and `"strategy": "slow_update"`), and write its per-task training results into `score_matrix.json`. Otherwise the delivered best becomes a skill absent from the pool, and the next 6.0 selection or merge can't sample, score, or diagnose the actual current best.
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

---

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

When the loop stops:

### 8a. run held-out test set

**Only if a held-out test set exists.** The degraded splits (5-7 inputs create no
test set; 4 or fewer create no split at all) leave nothing to score here. In those
minimum-input runs, skip this step and report "no honest test score (insufficient
inputs for a held-out set)" instead of inventing a test result — deliver the train
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

**The original SKILL.md is NEVER modified.** Do NOT offer to overwrite it. Do NOT copy the working file over it. The user decides what to do with the improved version.

---

## reference material

- **Mutation principles** (how to mutate well: subtract before adding, structural rules over phrase bans): [references/mutation-principles.md](references/mutation-principles.md)
- **Output file tree** (what the run produces): [references/dashboard-and-data-formats.md](references/dashboard-and-data-formats.md)
- **Worked example** (full diagram-generator run walkthrough), **operational tips** (cross-model setup, timeout handling, idea recovery), and **how this connects to other skills**: [references/worked-example.md](references/worked-example.md)
- **SkillOpt architecture comparison and roadmap** (mechanisms not yet implemented): [references/skillopt-architecture.md](references/skillopt-architecture.md)

---

## the test

A good optimization run:

1. **Started with a baseline** -- never changed anything before measuring the starting point
2. **Used binary evals only** -- no scales, no vibes, no "rate this 1-10"
3. **Split the data** -- training, validation, and (ideally) test sets are separate
4. **Used structured edits** -- every mutation is a typed operation with a target, not freeform rewriting
5. **Selected parents by Pareto frontier** -- branched from per-task winners sampled by tasks won, not always the single average-best (GEPA), so the search didn't collapse into one lineage
6. **Proposed edits from full traces** -- the optimizer read each failing run's verbatim execution trace and cited the exact step it diverged (Meta-Harness), not a compressed "which eval failed" summary
7. **Tracked rejections** -- the rejected-edit buffer prevented repeating failed approaches
8. **Checked for regressions** -- both per-experiment (regression guard) and longitudinally (slow update)
9. **Kept a complete log** -- every experiment recorded, kept or discarded, with edit ops and apply reports
10. **Improved the honest score** -- test set score improved, not just training or validation
11. **Ran autonomously** -- didn't stop to ask permission between experiments

If the skill "passes" all evals but the actual output quality hasn't improved, the evals are bad, not the skill. Go back to step 2 and write better evals.
