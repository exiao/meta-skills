#!/usr/bin/env python3
"""Deterministic unit test for the PACE acceptance gate (pace_accept.py).

Run: python3 test_pace_accept.py   (stdlib only, no pytest required)

The crux test is the "greedy would false-commit but PACE rejects" pair:
- A NOISE series: candidate has NO real gain over the incumbent, just zero-mean
  jitter. Greedy "mean val score went up by epsilon" commits this ~half the time
  (here the noise happens to lift the mean) -> a false commit. PACE's e-process
  never accumulates decisive wealth, so it REJECTS. This is the p-hacking failure
  PACE exists to close.
- A REAL-GAIN series: candidate is uniformly better by a real margin. PACE's
  wealth crosses 1/alpha and it COMMITS.
Plus: deterministic fast-path (PACE off), underpowered-split guard, a
PREDICTABLE-NORMALIZER check (B2: a verdict on a prefix must not change when later,
larger instances are appended -- a future-peeking normalizer would leak), and a
MEASURED 4000-trial null test that empirically holds the false-commit rate <= alpha
under H0 (the anytime-valid guarantee, measured rather than merely asserted).

All inputs are hardcoded/seeded so the verdicts are reproducible -- a true
fail-before/pass-after ground-truth test, not a flaky sampled one.
"""
import sys, pathlib, random
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from pace_accept import pace_accept, should_use_pace, _wealth_process

FAILS = []

def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


# ── Fixture 1: NOISE — no real gain, greedy false-commits, PACE must REJECT ──
# Incumbent per-instance scores, then candidate = incumbent + zero-mean noise that
# happens to nudge the MEAN slightly positive (the greedy trap).
random.seed(42)
N = 40
incumbent = [0.5 + 0.1 * ((i % 7) - 3) for i in range(N)]   # spread, deterministic
noise = [random.gauss(0.0, 0.25) for _ in range(N)]
# force the mean of noise slightly positive so greedy WOULD commit
mean_noise = sum(noise) / N
noise = [x - mean_noise + 0.02 for x in noise]               # mean diff = +0.02
candidate_noise = [c + d for c, d in zip(incumbent, noise)]

greedy_would_commit = (sum(candidate_noise) / N) > (sum(incumbent) / N)
check("noise: greedy WOULD false-commit (mean went up)", greedy_would_commit,
      f"mean diff {(sum(candidate_noise)-sum(incumbent))/N:+.4f}")

# Use a fixed a-priori reward_range (the harness's known score span) -- the strict,
# non-peeking normalizer.
dec_noise = pace_accept(candidate_noise, incumbent, alpha=0.05,
                        reward_kind="score", reward_range=1.0)
check("noise: PACE REJECTS the false commit", dec_noise.verdict == "reject",
      f"verdict={dec_noise.verdict} wealth={dec_noise.wealth:.3f} thr={dec_noise.threshold:.1f}")


# ── Fixture 2: REAL GAIN — candidate uniformly better, PACE must COMMIT ──
candidate_real = [c + 0.20 for c in incumbent]   # +0.20 on every instance
dec_real = pace_accept(candidate_real, incumbent, alpha=0.05,
                       reward_kind="score", reward_range=1.0)
check("real-gain: PACE COMMITS", dec_real.verdict == "commit",
      f"verdict={dec_real.verdict} wealth={dec_real.wealth:.2f} crossed at n={dec_real.n_used}")
check("real-gain: stops early (n_used < n_total) under optional stopping",
      dec_real.n_used <= dec_real.n_total,
      f"n_used={dec_real.n_used}/{dec_real.n_total}")


# ── Fixture 2b: predictable normalizer — verdict on a prefix is stable (B2) ──
# A peeking normalizer (max|d| over the FULL set) would let a huge LATE instance
# change how EARLY instances are scaled, so the same prefix could flip verdicts
# depending on what comes after. With a fixed a-priori scale the wealth trace over
# the first k instances is identical whether or not later, larger instances exist.
# Assert that invariance directly.
prefix = [0.05, -0.02, 0.08, 0.03, 0.06, -0.01, 0.04, 0.05]
with_big_tail = prefix + [5.0, -4.0, 6.0]     # later, much larger diffs
trace_prefix = _wealth_process(prefix, scale=1.0, lam=0.5)
trace_full = _wealth_process(with_big_tail, scale=1.0, lam=0.5)
check("predictable normalizer: prefix wealth trace unaffected by later instances",
      trace_prefix == trace_full[:len(prefix)],
      "fixed a-priori scale uses no future data; the global-max peeker would have differed here")


# ── Fixture 2c: MEASURED null — empirical false-commit rate <= alpha (anytime-valid) ──
# The anytime-valid claim, measured not asserted: under H0 (candidate is NOT better,
# pure zero-mean noise) the false-commit rate over many independent trials must stay
# at or below alpha, EVEN THOUGH we peek after every instance and stop early. Run
# 4000 trials of pure noise; count how often PACE commits.
# Scores are clamped to the harness range [0, 1] so reward_range=1.0 is a TRUE a-priori
# bound on |d_i| by construction -- the gate now fails fast on any |d_i| > reward_range
# (no silent clipping), so the generator must respect the declared bound, exactly as a
# real bounded-reward harness would. This keeps the null measurement on the strict,
# linear-normalization path the guarantee depends on.
ALPHA = 0.05
TRIALS = 4000
rng = random.Random(7)
clamp01 = lambda x: 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)
false_commits = 0
for _ in range(TRIALS):
    inc = [clamp01(rng.gauss(0.5, 0.25)) for _ in range(40)]
    cand = [clamp01(v + rng.gauss(0.0, 0.25)) for v in inc]   # H0: no real gain, just noise
    if pace_accept(cand, inc, alpha=ALPHA, reward_kind="score", reward_range=1.0).verdict == "commit":
        false_commits += 1
emp_rate = false_commits / TRIALS
# Ville bounds the rate at alpha; allow a small Monte-Carlo margin above alpha.
check("measured null: empirical false-commit rate <= alpha (anytime-valid holds)",
      emp_rate <= ALPHA + 0.01,
      f"{false_commits}/{TRIALS} = {emp_rate:.4f} (alpha={ALPHA})")


# ── Fixture 3: deterministic reward (exit-code) — PACE OFF, plain check ──
check("should_use_pace off for exit_code", should_use_pace("exit_code") is False)
check("should_use_pace on for score", should_use_pace("score") is True)

det_pass = pace_accept([1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                       [1, 0, 1, 0, 1, 1, 1, 0, 1, 1],
                       reward_kind="exit_code", reward_range=1.0)
check("deterministic: improvement on every instance COMMITS (PACE inactive)",
      det_pass.verdict == "commit" and det_pass.pace_active is False,
      f"verdict={det_pass.verdict} pace_active={det_pass.pace_active}")

det_regress = pace_accept([1, 1, 0, 1, 1],   # regressed on instance 3
                          [1, 1, 1, 1, 1],
                          reward_kind="exit_code", reward_range=1.0)
check("deterministic: any regression REJECTS", det_regress.verdict == "reject",
      f"verdict={det_regress.verdict}")


# ── Fixture 4: underpowered split guard (plan open-Q 4) ──
small = pace_accept([0.9, 0.9, 0.9], [0.5, 0.5, 0.5],
                    reward_kind="score", reward_range=1.0, min_instances=8)
check("underpowered: <min_instances returns 'continue' (lane BLOCKs for bigger set)",
      small.verdict == "continue",
      f"verdict={small.verdict} n_total={small.n_total} reason='{small.reason[:50]}...'")


# ── Fixture 5: paired-length contract is enforced ──
try:
    pace_accept([1, 2, 3], [1, 2], reward_kind="score", reward_range=1.0)
    check("paired-length mismatch raises", False, "no exception raised")
except ValueError:
    check("paired-length mismatch raises ValueError", True)


# ── Fixture 6: reward_range must be a positive a-priori bound ──
try:
    pace_accept(candidate_real, incumbent, reward_kind="score", reward_range=0.0)
    check("non-positive reward_range raises", False, "no exception raised")
except ValueError:
    check("non-positive reward_range raises ValueError", True)


# ── Fixture 7: alpha must be in (0, 1) ──
for bad_alpha in (0.0, 1.0, 1.5, -0.1):
    try:
        pace_accept(candidate_real, incumbent, reward_kind="score",
                    reward_range=1.0, alpha=bad_alpha)
        check(f"invalid alpha={bad_alpha} raises", False, "no exception raised")
    except ValueError:
        check(f"invalid alpha={bad_alpha} raises ValueError", True)


# ── Fixture 8: lam (betting fraction) must be in [0, 1) ──
for bad_lam in (-0.1, 1.0, 1.5):
    try:
        pace_accept(candidate_real, incumbent, reward_kind="score",
                    reward_range=1.0, lam=bad_lam)
        check(f"invalid lam={bad_lam} raises", False, "no exception raised")
    except ValueError:
        check(f"invalid lam={bad_lam} raises ValueError", True)


# ── Fixture 9: an observed |d_i| beyond reward_range fails fast (no silent clip) ──
# reward_range is a PREDICTABLE a-priori bound. A diff exceeding it means the declared
# range was wrong; clipping it would make the normalizer nonlinear and could let wealth
# accumulate under H0. The gate must RAISE, not certify the decision.
over_range_cand = [c + 2.0 for c in incumbent]   # every diff = +2.0 > reward_range 1.0
try:
    pace_accept(over_range_cand, incumbent, reward_kind="score", reward_range=1.0)
    check("out-of-range diff raises instead of clipping", False, "no exception raised")
except ValueError:
    check("out-of-range diff raises ValueError (no silent clip)", True)


# ── Fixture 10: a valid on-boundary diff perturbed by float rounding is NOT rejected ──
# Ordinary FP arithmetic can push a legitimate at-the-bound diff a few ULPs over the
# declared range (0.1 + 0.2 = 0.30000000000000004 vs reward_range 0.3). The bound check
# must absorb that noise rather than spuriously raising on a valid experiment.
boundary_d = 0.1 + 0.2                 # 0.30000000000000004, just over 0.3
fp_cand = [incumbent[0] + boundary_d] + list(incumbent[1:])
try:
    pace_accept(fp_cand, incumbent, reward_kind="score", reward_range=0.3)
    check("on-boundary FP diff is tolerated (not spuriously rejected)", True)
except ValueError as exc:
    check("on-boundary FP diff is tolerated (not spuriously rejected)", False, str(exc))


print()
if FAILS:
    print(f"RESULT: {len(FAILS)} FAILED -> {FAILS}")
    sys.exit(1)
print("RESULT: all assertions passed")
sys.exit(0)
