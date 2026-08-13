# Trigger-eval harness gives false negatives when nested inside another agent session

The Description Optimization loop (`scripts/run_eval.py`, `scripts/run_loop.py`)
measures whether a skill's description causes triggering by spawning `claude -p`
subprocesses and watching their partial-message stream for a skill read. This
detection **silently fails when the eval is launched from inside another agent
session** (e.g. the Hermes gateway, or any place where `claude -p` is nested
under a parent agent). Every query — should-trigger and should-not-trigger alike
— comes back at trigger rate **0.00**. The result is not "the description is bad";
it is "the harness could not observe triggering at all."

## The tell

A uniform `0.00` across ALL positives is the red flag. A genuinely weak
description still triggers on the most obvious phrasings (you'd see a spread like
0.33 / 0.67, not a flat wall of zeros). When even "run /<skill> on my changes" or
a verbatim trigger phrase scores 0, suspect the harness, not the skill.

## The control (do this before tuning the description)

Point the SAME harness at an **established, known-good skill** with an
obviously-triggering prompt:

```bash
python -m scripts.run_eval \
  --eval-set <a 3-line set: 2 dead-certain triggers + 1 obvious negative>.json \
  --skill-path ~/.hermes/skills/coding/simplify \
  --runs-per-query 2 --num-workers 4 --verbose
```

If a skill that has triggered reliably for months (e.g. `simplify` on
"run /simplify on my recent changes") also scores 0/2, the detector is blind in
this environment. Both your real eval's positives AND its "perfect" negatives are
meaningless — everything reads 0 because nothing is being observed.

## What actually happened (root cause)

`run_eval.py` writes the skill into `.claude/commands/` so it appears in the
nested `claude -p`'s `available_skills`, then parses `--include-partial-messages`
output for the skill read. Nested under a parent agent session, that partial
stream doesn't surface the child's skill reads to the detector, so the
`triggered` flag never flips. The subprocess runs (you'll see the description
echoed, queries dispatched, EXIT 0) but the signal it's watching for never
arrives.

## What to do

- **Don't claim the eval passed or failed from a nested run.** Report it as
  inconclusive and say why. A flat 0.00 with a failing control is not a skill
  result.
- **Run the trigger eval from a top-level Claude Code session** (not nested in a
  gateway/parent agent) so `claude -p` can surface skill reads to the detector.
- **Improve the description on first principles anyway** if the run was the only
  signal available: make it pushier on triggers (LLMs undertrigger skills — see
  the CSO reference) while keeping the disambiguation clauses that carve out
  near-miss negatives. That's the right direction regardless of an unmeasurable
  harness, but say plainly you couldn't measure it.

## Don't over-learn this

This is an environment/nesting artifact, NOT "the trigger eval is broken." From a
normal Claude Code session the harness works. Capture is the FIX (run it
top-level) plus the diagnostic (the control), not a standing "skip trigger evals"
rule.
