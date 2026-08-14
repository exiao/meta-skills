# PACE acceptance gate (the hill-climber commit rule)

> **Source:** PACE — Anytime-Valid Acceptance Tests for Self-Evolving Agents.
> Code: `scripts/pace_accept.py` (this skill). Unit test:
> `scripts/test_pace_accept.py`. (Cite-check the upstream paper's arxiv id before
> publishing this reference externally.)

## Why this replaces "keep it if the score went up"

skill-improver step 8 currently keeps a candidate when it "improves held-out
validation." Across hundreds of iterations that greedy rule is **uncontrolled
adaptive multiple testing**: the loop effectively p-hacks itself, accumulating
false commits that make the candidate churn and drift rather than improve. PACE's
own measurements: greedy made 13–21 spurious self-mods/run (72–100% false) in the
no-real-gain scenario and degraded the most fragile agent by −4.9 pts; PACE held at
baseline and cut false commits to "only the real one," with ~18% lower eval cost.

The hill-climber lane uses PACE as its **accept gate**, in place of the greedy
"val went up by epsilon" check. This is the single mechanism that makes the lane
more trustworthy than a plain goal-mode card looping on a number.

## The mechanism (paired, anytime-valid, testing-by-betting)

1. **Paired.** Compare the candidate against the **incumbent on identical held-out
   instances**. Pairing both controls variance and avoids re-drawing fresh samples
   each round (cache incumbent per-instance scores; each round only re-runs what
   changed). Work on the per-instance differences `d_i = cand(i) − inc(i)`.
2. **Testing-by-betting e-process.** Bet a fraction `lam` of current wealth that
   the next normalized difference is positive. Wealth multiplies by
   `(1 + lam · g_i)` where `g_i = d_i / scale`. Under H0 ("candidate no better",
   E[d_i | past] ≤ 0) this is a non-negative supermartingale **provided `scale` is
   predictable** (a function of data strictly before instance i).
3. **Predictable normalizer (this is what keeps the guarantee honest).** `scale` is a
   fixed **a-priori reward range** supplied by the caller
   (`pace_accept(..., reward_range=R)`, e.g. the harness's known max−min score span) —
   constant, so trivially predictable. We do **NOT** normalize by `max |d|` over the
   whole sequence: that peeks at future data, so the bet factors are not predictable
   and Ville's optional-stopping guarantee no longer holds. With an a-priori
   `reward_range` the normalized `g_i = d_i/R` lies in `[−1, 1]` by construction, so
   the bet factor stays positive for `lam ∈ [0,1)` with **no clipping**, and the
   rescaling is **linear** — so `E[1 + lam·g_i | past] = 1 + lam·E[g_i|past] ≤ 1`
   follows directly from `E[d_i|past] ≤ 0`. That is a genuine test supermartingale.
   `reward_range` is **required**: pass the harness's known score span. Because the
   linearity above carries real weight, an observed `|d_i| > reward_range` is a contract
   violation and the gate **raises** rather than clipping it: clipping would bend the
   transform nonlinear and could accumulate wealth under H0, so a too-small declared
   range fails fast instead of silently certifying.
4. **Anytime-valid commit.** By Ville's inequality, P(wealth ever ≥ 1/alpha) ≤ alpha
   **even under optional stopping** — so we may peek after every instance and stop
   early the moment the evidence is decisive, without inflating the false-commit
   rate. **COMMIT when wealth ≥ 1/alpha** (alpha≈0.05 → threshold 20). Stop
   measuring as soon as it crosses (the ~18% eval-cost saving).
5. **Alpha spending across candidates (multi-candidate control).** Ville bounds ONE
   e-process. Every `pace_accept` call starts a fresh wealth process, so a
   hill-climber testing K candidates at a flat alpha has a run-level false-commit
   probability up to `K·alpha` — the adaptive multiple testing PACE exists to close.
   Create **one `AlphaLedger` per run** and pass it to every call: the k-th tested
   candidate draws `alpha_k = alpha_total·6/(π²k²)`, whose infinite sum is exactly
   `alpha_total`, so a union bound puts the **family-wise** false-commit probability
   for the whole run at ≤ `alpha_total` no matter how many candidates are tried (the
   budget shrinks, never runs out). Deterministic fast-path and underpowered
   `continue` decisions spend nothing. Without a ledger the guarantee is
   per-candidate only — log `decision.alpha_used` so each accept says what it spent.
6. **Reject** when the e-process never crosses over the full held-out set: the gain
   could not be certified at level alpha → discard, log the reject. Note this is
   **not** the same as "mean ≤ 0": a true-but-small positive gain that fails to
   accumulate decisive wealth is also rejected — the gate discards gains it cannot
   distinguish from noise, which is the point.

Core is the `_wealth_process` helper (fixed a-priori-range normalizer) plus the
crossing loop in `pace_accept`. The unit test includes a measured 4000-trial null
that empirically holds the false-commit rate ≤ alpha under H0 (the anytime-valid
guarantee, measured rather than merely asserted).

## When PACE is ON vs OFF

- **ON** for *noisy* rewards: eval pass-rate, sampled metrics, judge scores —
  anything with run-to-run variance. This is the default (reward shape 2).
- **OFF** for *binary/deterministic* rewards: exit-code 0/1, `pytest` pass/fail with
  no sampling variance (reward shape 1, the ralph case). There is no variance to
  control; PACE collapses to a plain check. `pace_accept(..., reward_kind="exit_code")`
  takes a deterministic fast-path: commit iff the candidate improved on **every**
  paired instance (any per-instance regression rejects — golden-case discipline).
  Use `should_use_pace(reward_kind, variance_observed)` to route; if a harness
  declared "score" but ran identically across repeats, force it off.

## Three-way split discipline (the contract the gate assumes)

- Mutate using **train**; run the PACE accept on **val** (paired cand-vs-incumbent on
  identical val instances); seal **test** for a single final run at the very end.
- The proposer (Meta-Harness full-trace access) sees train/val traces only, never test.
- Golden cases live in train and are a **hard reject on any regression** regardless of
  net score.
- **Underpowered guard (plan open-Q 4).** A paired sequential test needs enough val
  instances to be powered. `pace_accept(min_instances=N, ...)` (default 8) returns
  `"continue"` when fewer than N paired instances are available — the lane treats
  that as "the eval set is too small to commit honestly" and **BLOCKs for a bigger
  held-out set** rather than committing on too-few samples. Current skills ship 8–12
  inputs; a three-way split can leave val below 8, so check this before trusting a
  commit.

## How the loop calls it

```python
from scripts.pace_accept import pace_accept, should_use_pace, AlphaLedger

# ONE ledger per hill-climber run -> family-wise control across candidates.
ledger = AlphaLedger(alpha_total=0.05)

# candidate_scores / incumbent_scores: per-instance rewards on the SAME val
# instances, same order (the paired contract).
dec = pace_accept(candidate_scores, incumbent_scores,
                  reward_kind="score",
                  reward_range=R,   # a-priori reward span (max-min) -> strict guarantee
                  min_instances=8,
                  ledger=ledger)    # omit for single-candidate use (alpha=0.05 flat)

if dec.verdict == "commit":
    ...   # accept the mutation into the pool; the incumbent becomes the candidate
elif dec.verdict == "reject":
    ...   # discard; log the reject; keep the incumbent
else:  # "continue"
    ...   # underpowered/inconclusive -> gather more instances or BLOCK for a bigger set
```

`PaceDecision` also carries `wealth`, `threshold`, `n_used`/`n_total` (cost saved by
early stopping), `mean_diff`, `pace_active`, and a `trace` of wealth per instance —
log these so every accept/reject is auditable.

## Failure modes the gate does NOT cover (still the SOUL's job)

- **Goodhart.** The gate proves the *metric* moved, not that the candidate is
  genuinely better. If the reward climbs but the candidate is visibly gaming the
  eval, stop and flag for Eric — don't report a hollow win.
- **Harness non-stationarity / flakiness.** PACE controls false commits under
  *stationary* noise. If the **incumbent's** own re-scored value drifts across rounds,
  the paired assumption is broken — detect incumbent-score drift and BLOCK
  ("harness appears flaky/non-stationary") rather than chase it. **Before you blame the
  judge, rule out the transport.** Apparent judge non-stationarity is often an artifact of
  how the judge is *called*, not real variance in the judge. Routing an LLM judge through a
  full agent (`create_agent → run_conversation`) has hung indefinitely and mangled the raw
  context fed to the grader, flipping a PASS/FAIL gate round-to-round on an unchanged
  artifact; the same prompt sent directly via `config.anthropic_client()` answered in ~1.5s
  and the gate went rock-stable. Two concrete fixes that removed the "noise": call the model
  client directly instead of through the agent, and run the grader with `env -u PYTHONPATH`
  (a stale `__pycache__/_bisect.pyc` shadowing stdlib `bisect` threw spurious
  `No module named piccolo/asyncpg` only when `PYTHONPATH` was set). Check both before
  blocking non-stationary.
- **Contamination.** The gate trusts that val ≠ test and the proposer never saw test.
  Enforce that in the split, not the gate.
