# Hill-climber lane runbook

The reward contract, the iteration loop, and the accept gate for the `hill-climber`
lane. Split out of the lane's SOUL.md so identity stays short.

## 1. The reward block (parse it FIRST)

Every card MUST carry a fenced `reward:` block. If it's missing or unparseable, block
("no defined reward") and stop. **Never invent one.**

```yaml
reward:
  shape: exit_code | score | judge  # 1 binary, 2 noisy numeric, 3 rubric judge
  cmd: <command the harness runs>   # e.g. ./run_evals.sh --split val --skill X
  score_path: results.json          # shape 2/3: file the cmd/judge writes
  score_key: val_pass_rate          # shape 2/3: JSON key to read
  judge:                            # shape 3 only: the qualitative scorer
    runner: <command that grades a candidate and writes score_path>
    rubric: <path/name of the rubric>
    scale: 0-100 | 1-5
  target: 0.95                      # stop when score >= target
  plateau: 5                        # stop after K non-improving accepts
  budget:
    max_iterations: 30              # per-card iteration cap (hard)
    max_runtime: 60m                # wall-clock (hard)
  split:                            # train != val != test, enforced
    train: ...
    val: ...
    test: ...                       # sealed; run once at the end
```

## 2. One iteration

1. **Mutate.** Propose ONE edit to the candidate (GEPA mutation plus Meta-Harness
   full-trace proposing). Mutate on `train` only; the proposer never sees `test`.
2. **Regenerate.** Re-run ONLY the changed stage in the candidate workspace via
   `regenerate_stage(skill, workspace, ticker)`. Never re-run the whole pipeline to score
   one mutation.
3. **Measure.** Score on held-out `val`. For a self-contained `cmd:` harness, run it. For
   a candidate whose output needs grading (CPE memo skills), spawn a `memo-evaluator`
   card on BOTH the incumbent and the candidate artifact in the same round, and read the
   rubric scores back. **The grade happens in the evaluator's context, never yours.**
4. **Accept or reject.**
   - **Numeric (shape 2):** load `skills-meta/skill-improver/references/pace-acceptance.md`,
     call `scripts/pace_accept.py`, compare candidate vs incumbent on identical val
     instances, commit when e-process wealth crosses 1/alpha (≈0.05). A "continue"
     verdict (too few paired instances, min 8) means block for a bigger held-out set.
   - **Judge (shape 3):** accept only when the candidate beats the same-round re-graded
     incumbent by a clear margin AND no golden or hard-constraint criterion regressed.
   - Log every reject with its wealth / mean-diff or per-criterion deltas.
5. **Stop?** Target hit, plateau (K non-improving accepts), or budget exhausted → run the
   sealed `test` set ONCE, then block for review. Otherwise loop.

## 3. Pitfalls

- **Grading your own output.** Producer ≠ grader is the #1 failure. Route generation to
  the agent profile and scoring to the evaluator profile, even though it costs a card
  round-trip per iteration.
- **Greedy accept on noise.** "Val went up by epsilon" on one read is not an improvement.
  Only the accept gate decides.
- **Training on test.** Mutate on train, accept on val, seal test for a single final run.
  Golden cases live in train and hard-reject on any regression.
- **Goodhart.** The gate proves the metric moved, not that the candidate is better. If it
  climbs while visibly gaming the eval, STOP and flag Eric.
- **Chasing a flaky harness or judge.** If the incumbent's own re-scored value drifts
  round to round, the paired assumption is broken: block
  ("harness/judge non-stationary").
- **Unbounded loops.** They burn the proxy pool dry. Defaults are hard, not advice:
  `goal_max_turns` 25, `max_runtime` 60m, iteration cap 30, accept-rate below ~50% → stop
  and report. Wanting to exceed a cap to "finish the win" IS the stop signal: block with
  the partial delta.
- **Hung shell commands.** A headless worker blocks the whole run on a hang. Never `find`
  unscoped from `$HOME` (Drive mounts under `~/Documents` deadlock). Cap anything that
  can hang with a `subprocess(..., timeout=N)` wrapper. Run the harness in the worktree.

## 4. References

- `skills-meta/skill-improver/` — the optimizer you run.
  `references/pace-acceptance.md` (the accept gate) plus `scripts/pace_accept.py`;
  `regenerate_stage` (per-stage regen callable).
- **memo-evaluator** profile — the grader for CPE memo candidates (shape-3 judge).
- **agent profiles** (equity-analyst, the dev lanes) — generate the artifact you optimize.
- `~/.hermes/constitution.md` — authoritative lane scopes and routing.
