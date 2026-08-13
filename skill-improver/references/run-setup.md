# Run Setup (context gathering, audit, saturation, resume, baseline)

Everything skill-improver does before the experiment loop starts. SKILL.md steps "before starting", 1, 1.5, 3, and 5 point here.

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

**PACE needs a powered validation set.** The accept/reject gate (step 6f) routes
through `pace_accept(..., min_instances=8)`: it returns `continue` (never `commit`)
until at least 8 paired validation instances are available. With the 25% validation
share that means **≈32+ total inputs** before PACE can auto-commit a candidate. Below
that, the gate is working as designed, it `continue`s and the lane **BLOCKs for a
bigger held-out set** rather than committing on too-few samples; the smaller "8–12
input" setups are fine for the train/analysis loop but will not produce a PACE
`commit` on their own. Supply enough inputs (or explicitly accept that small runs
gather-and-block instead of auto-accepting). Do **not** lower `min_instances` to fit a
tiny split, that reintroduces the underpowered false-commits PACE exists to prevent.

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

Do NOT skip this. The audit pre-pass finds low-hanging structural problems, but it does not replace the eval loop. Do not edit the original SKILL.md; audit fixes are applied only to the working copy and still pass through the baseline/validation gate.

---

## step 1.5: saturation pass (optional)

Before writing evals, review real executions of the skill to understand its actual failure modes. This step is **optional** for new or low-usage skills, but **mandatory** for high-value skills with production history (e.g. meta-ads-cli, memory-gc).

1. **Mine real executions first (deterministic).** Run `python scripts/mine_sessions.py --skill <skill-name>` to extract every session turn where the skill was actually invoked, paired with the assistant's real response. It reads `~/.hermes/state.db` (the indexed SQLite trace store that agentsview reads: a `messages` table + FTS5 full-text index), falling back to raw `~/.hermes/sessions/*.jsonl` only if no db exists. The strongest signal is Hermes's own skill-invocation stamp (`[SYSTEM: The user has invoked the "<skill>"...]`), from which it extracts the real user instruction. It strips secrets and system-injected boilerplate (cron wrappers, compaction handoffs, background-process notices, other skills' bodies), and tiers each hit:
   - **high** = an explicit invocation of the skill, or the user named it in an ordinary ask. Trust these; they are real invocations.
   - **low** = keyword overlap only (JSONL fallback path). Skim, mostly noise.
   Use `--dry-run` for counts + samples, or omit it to write `mined-<skill>.jsonl` (candidates) and `mined-<skill>.episodes.jsonl` (episode references). Solves the cold-start problem: your test inputs come from production usage, not a vacuum. A `0` result usually means the skill only ran via cron (no genuine user ask to mine), not that data is missing. Inspired by NousResearch/hermes-agent-self-evolution's session-mining and kenn-io/agentsview's Hermes parser (both reference maps for the trace format).
2. If the miner finds too little (new/low-usage skill), fall back to `recall` or manual `grep` through `~/.hermes/episodes/` and `~/.hermes/sessions/`.
3. For each mined execution, note:
   - Did it succeed or fail?
   - What was the failure mode? (wrong output, wrong process, silent failure, confabulation, tool error)
   - Did the user correct or work around anything?
   - Were there any surprising successes?
4. Stop when you hit **saturation**: the same failure patterns start repeating.
5. Use these patterns to inform both your test inputs (step 2's scenarios) and eval criteria (step 2's binary checks). Production failures make excellent golden cases (see item 7 in context gathering), the miner's high-confidence hits where the user complained ("this BLOWS", "why is this wrong") are prime golden-case material.

The mined candidates are **leads, not verdicts**: you still score relevance, write the `expected_behavior` rubric, and decide which become golden cases. The goal is to avoid designing evals in a vacuum. Real usage reveals failure modes that synthetic test inputs miss.

---

## step 3: check for existing checkpoint (resume support)

Before creating anything new, check if `autoresearch-[skill-name]/` already exists with a `checkpoint.json` file.

**If checkpoint exists:**
0. If it has no `best_skill_hash` or the `[name].md.best` snapshot is missing, it's a half-written pre-baseline run, start fresh (step 4).
1. Read `checkpoint.json`: last experiment, best score/experiment, slow update count, and the split membership (which inputs are train/val/test). Reuse that exact membership; never re-split.
2. Read `results.json` for full experiment history
3. Read `rejected_edits.json` for the rejected-edit buffer
4. Read `slow_updates.json` for longitudinal comparison history
4b. Read `pool.json` and `score_matrix.json` to restore the candidate pool and per-task scores, and confirm `traces/` holds the per-candidate execution traces the proposer reads. If pool/matrix are missing on an otherwise-valid checkpoint (a pre-Pareto run), rebuild a single-member pool from `[name].md.best` and backfill its matrix from the baseline experiment's per-eval results before continuing; if `traces/` is absent (a pre-Meta-Harness run), the first post-resume round captures fresh traces and the proposer falls back to the compressed summary until traces exist.
5. Restore `[name].md` from `[name].md.best` if it no longer matches `best_skill_hash` (a prior run was interrupted mid-mutation). Resume only from the last accepted state.
6. Tell the user: "Found existing run at experiment [N] with best val_score [X]%. Resume or start fresh?"
7. If resume: skip baseline, load all state, continue from experiment N+1
8. If fresh: move the old directory to `autoresearch-[skill-name]-backup-[timestamp]/` and start over

**If no checkpoint:** proceed to step 4 (baseline).

---

## step 5: establish baseline

Run the skill AS-IS before changing anything. This is experiment #0.

1. **Ask the user what to name the new version.** Example: "What should I call the optimized version? (e.g., anti-slop-v2, anti-slop-optimized)" The user picks the name.
2. Create a working directory: `autoresearch-[skill-name]/` inside the skill's folder
3. **Copy the original SKILL.md into the working directory as `[user-chosen-name].md`** -- this is the copy you will mutate. NEVER edit the original SKILL.md. All mutations happen on this copy only.
4. Also save `SKILL.md.baseline` in the working directory (identical to the original -- this is your revert target and slow-update comparison anchor)
5. Create `results.tsv`, `results.json`, `rejected_edits.json` (empty array), `slow_updates.json` (empty array), and `dashboard.html`. Open the dashboard. Don't create `checkpoint.json` yet (step 9).
6. Run the skill using **only the train + validation sets** with the **target model**. Score every output against every eval. Capture the full execution trace of every training run to `traces/cand_0/run_*.md` (same format as step 6d), the baseline traces are what the first proposer round reads. Leave the test set sealed until final evaluation (step 8).
7. Record the baseline: `train_score` and `val_score` independently. The test set is scored once, at step 8.
8. **Snapshot the baseline as the initial accepted best AND seed the candidate pool:** copy `[user-chosen-name].md` to `[user-chosen-name].md.best` and record its hash. Create `pool.json` containing this one baseline candidate (`id: "cand_0"`, `parent_id: null`) and write its per-task training pass-rates into `score_matrix.json`. This is the accepted state and the single-member pool until the first KEEP.
9. Create `checkpoint.json` now (after the `.best` snapshot), with `best_skill_hash`, the split membership, and `pool_ids: ["cand_0"]` (schema in [references/dashboard-and-data-formats.md](references/dashboard-and-data-formats.md)).

**IMPORTANT:** After establishing baseline, confirm the score with the user before proceeding. If baseline is already 90%+, the skill may not need optimization. See [references/pitfalls.md](references/pitfalls.md) for why high baselines can be misleading.
