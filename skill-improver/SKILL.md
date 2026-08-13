---
name: skill-improver
preloaded: true
description: "Optimize a skill by running it, scoring against evals, and keeping only validated gains. Use for optimize this skill, make this skill better, run autoresearch."
---

> **Source:** Karpathy autoresearch + SkillOpt (Microsoft Research, arxiv:2605.23904) + GEPA reflective prompt evolution (Agrawal et al., arxiv:2507.19457) + Meta-Harness end-to-end harness optimization (Lee et al., arxiv:2603.28052) + howtoeval.com (Ben Hylak, May 2026).

# Skill Optimizer

## the loop

Take any existing skill, define what "good output" looks like as binary yes/no checks, then run this loop:

1. **Audit and read the skill.** Run `skill-audit` on the target skill, then read SKILL.md and linked references. Capture obvious structural/routing issues, but do not edit yet.
2. **Gather the eval setup.** Confirm 8-12 test inputs, 3-6 binary evals, model config, run count, budget cap, and golden cases. Split inputs into train/validation/test.
3. **Establish the baseline.** Copy the unchanged skill into the working directory, run train + validation with the target model, score it, and create the dashboard/checkpoint.
4. **Score outputs with binary evals.** Include refusal evals and trajectory evals when the skill's failure mode depends on uncertainty or process, not just final text.
5. **Diagnose failures from full traces.** Let the optimizer browse the per-candidate execution traces (every tool call, every turn, the exact divergence step) plus scores and source, and cite where each failing run went wrong (Meta-Harness), instead of getting a compressed "which eval failed" summary. See [references/meta-harness-proposer.md](references/meta-harness-proposer.md).
6. **Select a parent from the Pareto frontier.** Don't always mutate the single best. Keep every candidate that's best on at least one task alive in a pool, and sample the parent weighted by tasks won (GEPA-style). See [references/pareto-selection.md](references/pareto-selection.md).
7. **Propose one change.** Either a structured edit (append/insert_after/replace/delete) on the sampled parent, or, when the frontier has ≥2 members, a System Aware Merge of two frontier parents ([references/system-aware-merge.md](references/system-aware-merge.md)).
8. **Validate before keeping (PACE gate).** Any golden-case regression is an unconditional reject. Route keep/discard through the PACE gate (`scripts/pace_accept.py`, step 6f), not a greedy "val went up" check. KEEP on `commit`, DISCARD on `reject`, BLOCK on `continue` for a bigger held-out set. Log every reject with its PACE diagnostics.
9. **Repeat, then seal it.** Use the rejected-edit buffer and slow updates until plateau/budget/user stop, then score the sealed test set once and deliver the single best file plus artifacts.

**Output:** An improved skill copy + `results.tsv` log + `changelog.md` of every mutation attempted + a live HTML dashboard you can watch in your browser. The original SKILL.md is never overwritten.

---

## why this exists

Most skills work about 70% of the time. The other 30% you get garbage. Rewriting the skill from scratch does not fix that. Let an agent run it dozens of times, score every output, and tighten the prompt until that 30% disappears.

A separate (usually stronger) model analyzes failures while the target model executes, because the same model can't see its own blind spots.

---

## before starting: gather context

**STOP. Do not run any experiments until all fields below are confirmed with the user. Ask for any missing fields before proceeding.**

Confirm all seven: target skill path, 8-12 test inputs, 3-6 binary eval criteria, model configuration, runs per experiment (default 3), budget cap (default none), and golden cases.

Model configuration is one of three:

| Config | Optimizer (analyzes) | Target (executes) | Best for |
|--------|---------------------|-------------------|----------|
| **A (default)** | claude-opus-4-6 | gpt-5.5 | Skills that run on OpenAI models in production. Opus catches GPT blind spots. |
| **B** | gpt-5.5 | claude-opus-4-6 | Skills that run on Anthropic models in production. GPT catches Opus blind spots. |
| **C (same model)** | session model | session model | Quick runs, cost-sensitive, or when you just want to iterate fast. |

Default is **A**. The optimizer should be a different architecture than the target so it can see systematic biases the target can't. If the user says "same model" or "no cross-model," use C.

Inputs split 50% training / 25% validation / 25% test. Golden cases always land in training and are never held out.

**PACE needs a powered validation set.** The gate returns `continue` until at least 8 paired validation instances exist, which means ≈32+ total inputs before it can auto-commit. Smaller runs gather and BLOCK instead of auto-accepting. Do not lower `min_instances` to fit a tiny split.

Full detail (all seven fields verbatim, the split table, graceful degradation for 4-7 inputs, golden-case placement, persisting split membership) is in [references/run-setup.md](references/run-setup.md).

---

## step 1: audit and read the skill

Run `skill-audit` on the target skill directory, read the full SKILL.md and every file in its `references/`, and identify the core job, process steps, and output format. Separate findings into deterministic obvious fixes and behavioral hypotheses that need eval evidence.

Do NOT skip this. The audit pre-pass does not replace the eval loop. Audit fixes are applied only to the working copy and still pass through the baseline/validation gate. Steps in full: [references/run-setup.md](references/run-setup.md).

---

## step 1.5: saturation pass (optional)

Mine real executions before writing evals. Run `python scripts/mine_sessions.py --skill <skill-name>` to extract every session turn where the skill was actually invoked, paired with the real response. Optional for new skills, mandatory for high-value skills with production history (e.g. meta-ads-cli, memory-gc).

Stop when the same failure patterns repeat. Production failures make excellent golden cases. Mined candidates are leads, not verdicts.

Full protocol (the `~/.hermes/state.db` read path, high/low confidence tiering, `--dry-run`, output files, fallbacks): [references/run-setup.md](references/run-setup.md).

---

## step 2: build the eval suite

Every check must be binary: pass or fail, no scales. 3-6 evals is the sweet spot. Make each one specific enough to be consistent but not so narrow the skill games it.

Add refusal evals when the skill handles real data and a confident wrong answer is worse than a refusal. Add trajectory evals when correct output from a wrong process would be a false positive.

Eval format, the rules, and the max-score math: [references/eval-suite-setup.md](references/eval-suite-setup.md). Good vs bad examples, refusal and trajectory templates, golden cases: [references/eval-guide.md](references/eval-guide.md).

---

## step 3: check for existing checkpoint (resume support)

Before creating anything new, check whether `autoresearch-[skill-name]/` already exists with a `checkpoint.json`. If it does, restore the split membership, results history, rejected-edit buffer, slow-update history, candidate pool, score matrix, and traces, then ask the user whether to resume or start fresh. Never re-split on resume.

If no checkpoint, proceed to step 4. Resume procedure in full, including pre-Pareto and pre-Meta-Harness backfill: [references/run-setup.md](references/run-setup.md).

---

## step 4: generate the live dashboard

Create the working directory `autoresearch-[skill-name]/` if it does not exist, then write a live HTML dashboard at `autoresearch-[skill-name]/dashboard.html` and open it. It auto-refreshes from `results.json` and shows train/validation score curves, per-experiment keep/discard bars, per-eval breakdown, rejected-edit buffer, diagnostics frequency, and golden case status.

Dashboard requirements plus the `results.json` and `results.tsv` schemas: [references/dashboard-and-data-formats.md](references/dashboard-and-data-formats.md).

**Critical:** the held-out test set is NEVER scored during the run. `results.json` carries only train and validation scores throughout; `final_test_score` is added once, at the very end (step 8).

---

## step 5: establish baseline

Run the skill AS-IS before changing anything. This is experiment #0.

Ask the user what to name the new version, copy the original SKILL.md into `autoresearch-[skill-name]/` as `[user-chosen-name].md`, and save `SKILL.md.baseline` as the revert target. Mutate only the copy. NEVER edit the original SKILL.md.

Run train + validation with the target model, capture full traces to `traces/cand_0/run_*.md`, record `train_score` and `val_score` independently, then snapshot `[user-chosen-name].md.best`, seed `pool.json` with `cand_0`, write `score_matrix.json`, and create `checkpoint.json`.

**IMPORTANT:** After establishing baseline, confirm the score with the user before proceeding. If baseline is already 90%+, the skill may not need optimization. See [references/pitfalls.md](references/pitfalls.md) for why high baselines can be misleading.

All nine numbered baseline steps and the `results.tsv` header row: [references/run-setup.md](references/run-setup.md).

---

## step 6: run the experiment loop

This is the core optimization loop. Once started, run autonomously until stopped. Every sub-step is spelled out in [references/experiment-loop.md](references/experiment-loop.md).

- **6.0 Pareto parent selection.** Sample from the frontier, never greedily from the single best ([references/pareto-selection.md](references/pareto-selection.md)).
- **6a Failure pattern clustering.** The optimizer browses full traces with file-read tools and cites the exact divergence step ([references/meta-harness-proposer.md](references/meta-harness-proposer.md)).
- **6a.5 Post-failure self-diagnosis.** Replay failures to the target model; treat its answers as clues, not truth.
- **6b Success pattern analysis.** Lower priority than failure-derived edits.
- **6c Structured edits.** Typed JSON ops with protected-region rules ([references/structured-edits.md](references/structured-edits.md)).
- **6c-merge System Aware Merge.** Section-wise crossover of two frontier parents ([references/system-aware-merge.md](references/system-aware-merge.md)).
- **6d Apply and run training set.** Capture every run's verbatim trace to `traces/cand_<id>/`.
- **6d.5 Self-diagnostics capture.** The `DIAGNOSTIC:` categories and how to read them ([references/self-diagnostics.md](references/self-diagnostics.md)).
- **6e Regression guard.** Any golden-case regression on any eval is an instant discard.
- **6f PACE validation gate.** `scripts/pace_accept.py` decides keep vs discard ([references/pace-acceptance.md](references/pace-acceptance.md)). Running this as a long-lived background lane: [references/hill-climber-lane-runbook.md](references/hill-climber-lane-runbook.md).
- **6g Rejected-edit buffer.** Cap at 10 entries; inject into the 6a prompt.
- **6h Log and checkpoint.** After every experiment, kept or discarded.
- **6i Slow update.** Every 5th experiment, run the longitudinal baseline-vs-current check and gate its guidance like any other mutation.
- **6j Stopping criteria.** NEVER stop to ask the user whether to continue.

---

## step 7: write the changelog

After each experiment, kept or discarded, append a record to `changelog.md`: scores, edit ops, apply report, hypothesis, result, failure patterns, and rejected-edit buffer state.

This changelog is the most valuable artifact. Any future agent can pick it up and continue. Template: [references/delivery-and-changelog.md](references/delivery-and-changelog.md).

---

## step 8: final evaluation and delivery

Score the sealed test inputs once, through both `SKILL.md.baseline` and the best optimized skill, using the target model. The delta is the honest improvement number. Degraded splits (5-7 inputs, or 4 or fewer) have no test set; report that no honest test score exists rather than inventing one.

Deliver the score summary, experiment count, keep rate, top changes, remaining failure patterns, and artifact locations. Include only the items that carry information for this run.

**The original SKILL.md is NEVER modified.** Do NOT offer to overwrite it. The user decides what to do with the improved version. Full delivery checklist and the overfitting warning: [references/delivery-and-changelog.md](references/delivery-and-changelog.md).

---

## operational tips (in-repo loops and fleet sweeps)

When the target repo already has its own eval-driven mutation runner, use it. Do not reimplement the loop here. Read its `main()` and acceptance gate first, and read WHAT THE EVAL GATE SCORES before patching anything, because cost is set by the smallest artifact the gate reads.

**DEFAULT TO MANUAL-EXECUTOR MODE FOR FLEET SWEEPS, measure the regenerate cost ONCE before fanning out the harness loop.** If a per-skill cycle costs tens of minutes, switch to manual-executor mode ([references/manual-executor-mode.md](references/manual-executor-mode.md)): you are the target model, score the repo's committed fixture artifacts directly, edit, re-execute, re-score.

Two traps that give wrong deltas when validating an e2e-regen hill-climb: [references/e2e-regen-validation-traps.md](references/e2e-regen-validation-traps.md). Multi-hour unattended sweeps, timeouts, resumable batch runners, and orphan cleanup: [references/in-repo-loop-fleet-ops.md](references/in-repo-loop-fleet-ops.md). Known failure modes: [references/pitfalls.md](references/pitfalls.md).

The full text of these tips, verbatim: [references/in-repo-and-fleet-tips.md](references/in-repo-and-fleet-tips.md).

---

## reference material

- **Mutation principles** (subtract before adding, structural rules over phrase bans): [references/mutation-principles.md](references/mutation-principles.md)
- **Output file tree** (what the run produces): [references/dashboard-and-data-formats.md](references/dashboard-and-data-formats.md)
- **Worked example** (full diagram-generator run walkthrough), operational tips (cross-model setup, timeout handling, idea recovery), and how this connects to other skills: [references/worked-example.md](references/worked-example.md)
- **SkillOpt architecture comparison and roadmap** (mechanisms not yet implemented): [references/skillopt-architecture.md](references/skillopt-architecture.md)
- **Benchmarking this loop vs DSPy MIPRO/Bootstrap** (bake-off, OpenRouter+DSPy wiring, persona-judge metric, teaching-to-the-test caveat): [references/method-bakeoff-vs-dspy-mipro.md](references/method-bakeoff-vs-dspy-mipro.md)
- **Arize ruleset mode** (frozen-base/dynamic-ruleset plus the Opus 4.8/DSPy/MIPRO benchmark lessons): [references/arize-ruleset-mode-benchmark.md](references/arize-ruleset-mode-benchmark.md)
- **Ad creative ideation case study** (a run on a creative-generation skill): [references/ad-creative-ideation-case-study.md](references/ad-creative-ideation-case-study.md)

---

## the test

A good optimization run:

1. **Started with a baseline** -- never changed anything before measuring the starting point
2. **Used binary evals only** -- no scales, no vibes, no "rate this 1-10"
3. **Split the data** -- training, validation, and (ideally) test sets are separate
4. **Used structured edits** -- every mutation is a typed operation with a target, not freeform rewriting
5. **Selected parents by Pareto frontier** -- branched from per-task winners sampled by tasks won (GEPA), so the search didn't collapse into one lineage
6. **Proposed edits from full traces** -- the optimizer read each failing run's verbatim execution trace and cited the exact step it diverged (Meta-Harness)
7. **Tracked rejections** -- the rejected-edit buffer prevented repeating failed approaches
8. **Checked for regressions** -- both per-experiment (regression guard) and longitudinally (slow update)
9. **Kept a complete log** -- every experiment recorded, kept or discarded, with edit ops and apply reports
10. **Improved the honest score** -- test set score improved, not just training or validation
11. **Ran autonomously** -- didn't stop to ask permission between experiments

If the skill "passes" all evals but the actual output quality hasn't improved, the evals are bad, not the skill. Go back to step 2 and write better evals.
