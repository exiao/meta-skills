#!/usr/bin/env python3
"""PACE acceptance gate — Paired Anytime-valid Commit Evaluation.

The keep/discard decision for a hill-climber iteration. Replaces skill-improver's
greedy "candidate val score > incumbent val score by epsilon" check, which is
uncontrolled adaptive multiple testing (the loop p-hacks itself across hundreds of
iterations, accumulating false commits -> churn/drift instead of improvement).

Mechanism (PACE — anytime-valid acceptance tests for self-evolving agents): recast
committing as a SEQUENTIAL hypothesis test. Compare the candidate against the
incumbent on IDENTICAL held-out instances (paired). Run a testing-by-betting
e-process on the paired per-instance reward differences d_i = score_candidate(i) -
score_incumbent(i). Under H0 ("candidate is no better", E[d_i | past] <= 0) the
wealth process is a non-negative supermartingale, so by Ville's inequality
P(ever cross 1/alpha) <= alpha EVEN UNDER OPTIONAL STOPPING. COMMIT when wealth
>= 1/alpha. This controls each candidate's false-commit probability at alpha
regardless of how many instances we peek at or how many candidates we try.

Predictable normalizer (why the anytime-valid claim holds): the supermartingale
property requires each bet factor be PREDICTABLE — a function of data strictly
before instance i only. We normalize each difference by a fixed a-priori
`reward_range` supplied by the caller (the harness's known max-min score span). A
constant is trivially predictable, so g_i = d_i / reward_range lies in [-1, 1] by
construction, the bet factor (1 + lam * g_i) stays positive for lam in [0, 1)
WITHOUT any clipping, and the rescaling is LINEAR, so E[1 + lam*g_i | past] =
1 + lam*E[g_i|past] <= 1 follows directly from E[d_i|past] <= 0. This is a genuine
test supermartingale and Ville's optional-stopping guarantee holds rigorously. We do
NOT normalize by max |d| over the whole sequence — that peeks at future data and
breaks the guarantee.

When PACE does NOT apply: a binary/deterministic reward (exit code 0/1, pytest
pass/fail with no sampling variance) has no variance to control -- PACE collapses
to a plain check. Use should_use_pace() to gate; for deterministic rewards take the
greedy exact-improvement decision instead.

No third-party deps (pure stdlib) so the lane can run it anywhere.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Sequence, Literal


@dataclass
class PaceDecision:
    verdict: Literal["commit", "reject", "continue"]
    wealth: float                 # final e-process wealth
    threshold: float              # 1/alpha; commit when wealth crosses this
    n_used: int                   # instances consumed before stopping
    n_total: int                  # instances available
    mean_diff: float              # mean paired reward difference (diagnostic)
    reason: str
    pace_active: bool = True      # False => deterministic fast-path was used
    trace: list[float] = field(default_factory=list)  # wealth after each instance


def should_use_pace(reward_kind: str, variance_observed: bool | None = None) -> bool:
    """PACE ON for noisy rewards (eval pass-rate, sampled metrics, judge scores).
    PACE OFF for binary/deterministic rewards (exit-code 0/1) -- no variance to control.

    reward_kind: "exit_code" / "deterministic" => off; "score" / "passrate" / "noisy" => on.
    variance_observed (optional): if the harness was run >1x and produced identical
    scores every time, force off regardless of declared kind.
    """
    if variance_observed is False:
        return False
    return reward_kind not in ("exit_code", "deterministic", "binary")


def _wealth_process(diffs: Sequence[float], scale: float, lam: float) -> list[float]:
    """Testing-by-betting e-process with a FIXED a-priori scale (predictable: constant).

    Bet a fraction `lam` (in [0,1)) of current wealth that the next normalized
    difference is positive. Wealth multiplies by (1 + lam * g_i) where g_i =
    d_i / scale. With scale a true a-priori bound on |d_i|, g_i lies in [-1, 1] by
    construction so the factor stays positive WITHOUT clipping, and the normalization
    is linear -> under H0 (E[d_i|past] <= 0) this is a non-negative test
    supermartingale and Ville gives anytime-valid type-I control.
    """
    wealth = 1.0
    out: list[float] = []
    for d in diffs:
        g = d / scale
        # Caller-side fail-fast (pace_accept) guarantees |d| <= scale, so g is in
        # [-1, 1] and the normalization stays LINEAR (the supermartingale proof
        # relies on this). The clamp is then a pure float-rounding guard: it keeps
        # 1 + lam*g > 0 against tiny FP overshoot, and is NOT a substitute for the
        # bound check -- clipping a genuinely out-of-range d would make the transform
        # nonlinear and could accumulate wealth under H0.
        g = max(-1.0, min(1.0, g))
        wealth *= (1.0 + lam * g)
        if wealth <= 0:             # numerical floor; cannot recover, treat as dead
            wealth = 1e-12
        out.append(wealth)
    return out


def pace_accept(
    candidate_scores: Sequence[float],
    incumbent_scores: Sequence[float],
    *,
    reward_range: float,
    alpha: float = 0.05,
    reward_kind: str = "score",
    lam: float = 0.5,
    min_instances: int = 8,
) -> PaceDecision:
    """Decide whether to COMMIT the candidate over the incumbent.

    candidate_scores / incumbent_scores: per-instance rewards on IDENTICAL held-out
        instances (must be the same length and same ordering -- this is the paired
        contract that both controls variance and saves eval cost).
    reward_range: a-priori bound on a single paired difference |d_i| (e.g. the
        harness reward's max-min span). REQUIRED and PREDICTABLE (set before seeing
        data), so the e-process is a strict test supermartingale and the anytime-valid
        guarantee holds rigorously. We deliberately do NOT normalize by max |d| over
        the full set -- that peeks at future data and voids Ville's guarantee. If an
        observed |d_i| exceeds this bound the call RAISES (the declared range was
        wrong) rather than silently clipping into a nonlinear regime.
    alpha: target false-commit probability (commit when wealth >= 1/alpha).
    reward_kind: routes the deterministic fast-path (see should_use_pace).
    lam: betting fraction in [0,1). 0.5 is a robust default.
    min_instances: do not COMMIT before this many paired instances even if wealth
        crosses early -- guards a powered split (plan open-Q 4). Below this many
        AVAILABLE instances, the gate returns "continue" with a reason so the lane
        BLOCKS for a bigger eval set rather than committing on too-few samples.

    Returns a PaceDecision:
      "commit"   = the e-process crossed 1/alpha: decisive, statistically-real gain.
      "reject"   = the e-process ran the full held-out set without crossing: the gain
                   (if any) is not distinguishable from noise at level alpha, so it is
                   discarded. NOTE: a true-but-small positive mean can land here -- the
                   gate rejects gains it cannot certify, not only gains with mean<=0.
      "continue" = underpowered (fewer than min_instances available): gather more
                   instances / BLOCK for a bigger held-out set before deciding.
    """
    if len(candidate_scores) != len(incumbent_scores):
        raise ValueError("paired test requires equal-length candidate/incumbent score arrays")
    n = len(candidate_scores)
    if n == 0:
        raise ValueError("no instances to compare")
    if reward_range <= 0:
        raise ValueError("reward_range must be a positive a-priori bound on |d_i|")
    if not (0 < alpha < 1):
        raise ValueError("alpha must be in the interval (0, 1)")
    if not (0 <= lam < 1):
        raise ValueError("lam (betting fraction) must be in the interval [0, 1)")

    diffs = [c - i for c, i in zip(candidate_scores, incumbent_scores)]
    # Contract: reward_range is a PREDICTABLE a-priori bound on |d_i|. If an observed
    # difference exceeds it, the declared range was wrong -- fail fast rather than
    # silently clip (clipping makes the normalization nonlinear and voids the strict
    # supermartingale / anytime-valid guarantee; see _wealth_process).
    worst = max((abs(d) for d in diffs), default=0.0)
    # Tolerance absorbs ordinary float rounding (e.g. 0.1+0.2 = 0.30000000000000004
    # vs reward_range 0.3) so a valid on-boundary diff is not spuriously rejected,
    # while a real bound violation still fails fast. Scaled to reward_range's
    # magnitude; the subsequent clamp keeps the wealth factor positive regardless.
    tol = 1e-9 * max(1.0, reward_range)
    if worst > reward_range + tol:
        raise ValueError(
            f"observed |d_i|={worst:.6g} exceeds declared reward_range={reward_range:.6g}; "
            "reward_range must be a true a-priori bound on the paired difference -- "
            "widen it to the harness's real max-min span (do not clip)"
        )
    mean_diff = sum(diffs) / n
    threshold = 1.0 / alpha

    # --- Deterministic fast-path: no variance to control, PACE collapses to a check.
    if not should_use_pace(reward_kind):
        improved = mean_diff > 0 and all(d >= 0 for d in diffs)
        return PaceDecision(
            verdict="commit" if improved else "reject",
            wealth=float("inf") if improved else 0.0,
            threshold=threshold, n_used=n, n_total=n, mean_diff=mean_diff,
            reason=("deterministic reward improved on every paired instance"
                    if improved else
                    "deterministic reward did not strictly improve (a regression on any instance rejects)"),
            pace_active=False,
        )

    # --- Underpowered split guard (plan open-Q 4): too few instances for a paired test.
    if n < min_instances:
        return PaceDecision(
            verdict="continue", wealth=1.0, threshold=threshold,
            n_used=0, n_total=n, mean_diff=mean_diff,
            reason=(f"underpowered: {n} paired instances < min_instances={min_instances}; "
                    "BLOCK for a larger held-out set rather than commit on noise"),
        )

    # --- Predictable (fixed a-priori) normalizer -> strict test supermartingale.
    wealth_trace = _wealth_process(diffs, scale=reward_range, lam=lam)

    # Anytime-valid optional stopping: commit the first time wealth crosses 1/alpha,
    # but never before min_instances peeks.
    for idx, w in enumerate(wealth_trace, start=1):
        if idx >= min_instances and w >= threshold:
            return PaceDecision(
                verdict="commit", wealth=w, threshold=threshold,
                n_used=idx, n_total=n, mean_diff=mean_diff,
                reason=f"e-process wealth {w:.2f} >= 1/alpha {threshold:.2f} at instance {idx} (decisive gain)",
                trace=wealth_trace[:idx],
            )

    final_w = wealth_trace[-1]
    return PaceDecision(
        verdict="reject", wealth=final_w, threshold=threshold,
        n_used=n, n_total=n, mean_diff=mean_diff,
        reason=(f"e-process wealth {final_w:.2f} never crossed 1/alpha {threshold:.2f} "
                f"over {n} instances (mean diff {mean_diff:+.4f}); gain not distinguishable from noise"),
        trace=wealth_trace,
    )


if __name__ == "__main__":
    # tiny manual demo
    import random
    random.seed(0)
    inc = [random.random() for _ in range(40)]
    noise = [v + random.gauss(0, 0.3) for v in inc]   # no real gain, just noise
    real = [v + 0.25 for v in inc]                     # real +0.25 gain
    print("noise:", pace_accept(noise, inc, reward_range=1.0).verdict)
    print("real :", pace_accept(real, inc, reward_range=1.0).verdict)
