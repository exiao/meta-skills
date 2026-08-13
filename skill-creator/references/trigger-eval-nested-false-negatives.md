# Trigger-eval false negatives when nested inside another agent session

## Symptom

Every query in the Description Optimization trigger eval (`scripts/run_eval.py`,
`scripts/run_loop.py`) scores `trigger_rate = 0.00`, including strong should-trigger prompts.
Positives look like total failure while negatives all "pass" at 0.00, so accuracy pins at exactly
the negative count.

A uniform 0.00 across all positives is the tell. A genuinely weak description still triggers on
the most obvious phrasings, so you'd see a spread like 0.33 / 0.67, not a wall of zeros. When a
verbatim trigger phrase scores 0, suspect the harness.

## Root cause

The harness writes the skill into `.claude/commands/` and watches `claude -p`'s partial-message
stream for a skill read. When `claude -p` runs nested inside a parent agent session (the Hermes
gateway, or any nesting), the child's skill reads never reach the detector. The subprocess runs
fine (description echoed, queries dispatched, exit 0) but the signal never arrives.

This is a measurement-validity bug in the environment, not a description failure.

## Mandatory control before trusting a 0/N result

Point the same harness at a known-good, long-established skill with a dead-certain prompt.

```bash
# simplify is mature; "run /simplify on my changes" MUST trigger
python -m scripts.run_eval \
  --eval-set <(echo '[{"query":"run /simplify on my recent changes and fix duplication","should_trigger":true},{"query":"what is the capital of France","should_trigger":false}]') \
  --skill-path ~/.hermes/skills/coding/simplify \
  --runs-per-query 2 --num-workers 4 --verbose
```

If the control also scores 0/2, the detector is blind here. Your eval is inconclusive, not failed.
Say that plainly. Don't claim it passed (negatives are meaningless when everything reads 0) or
failed (positives are false negatives).

## Where to run it

From a top-level Claude Code session, not nested in a gateway or parent agent, so skill reads
reach the detector. Absent that, fall back to judgement: a description reads well if its
should-trigger phrasings are explicit and its should-not cases are carved out in the text.

## Fix direction when the signal is valid

If you get a real signal showing weak positives, make the description pushier (per the CSO note,
Claude tends to undertrigger): add explicit trigger phrases and an "even if they never say X"
clause. Keep the disambiguation clauses ("for Y use other-skill instead") that earn clean
negatives. Pushiness raises positives, carve-outs protect negatives. Tune both.

## Don't over-learn this

An environment and nesting artifact, not "the trigger eval is broken." From a normal Claude Code
session the harness works. The takeaway is the fix (run it top-level) plus the diagnostic (the
control), not a standing rule to skip trigger evals.
