# Trigger-eval harness gives false negatives when nested inside the gateway

## Symptom
You run the Description Optimization trigger eval (`scripts/run_eval.py` or
`scripts/run_loop.py`, which shell out to `claude -p`) from inside the Hermes
gateway/agent session, and EVERY query scores `trigger_rate = 0.00` — including
strong should-trigger prompts. Positives look like a total failure (0/N) while
negatives all "pass" (also 0.00), so accuracy pins at exactly the negative count.

## Root cause
The harness detects triggering by writing the skill into `.claude/commands/` and
watching `claude -p`'s partial-message stream for a skill read. When `claude -p`
is launched as a subprocess *nested inside* this gateway session, those skill
reads are not surfaced to the detector, so it records zero triggers for
everything. This is a measurement-validity bug in the environment, NOT a real
description failure. The uniform `0.00` across obviously-different prompts is the
tell.

## Mandatory control before trusting a 0/N result
Do not conclude "my description undertriggers" from a nested run. Run a control:
point the SAME harness at a known-good, long-established skill with a
dead-certain trigger prompt.

```bash
# control: simplify is a mature skill; "run /simplify on my changes" MUST trigger
python -m scripts.run_eval \
  --eval-set <(echo '[{"query":"run /simplify on my recent changes and fix duplication","should_trigger":true},{"query":"what is the capital of France","should_trigger":false}]') \
  --skill-path ~/.hermes/skills/coding/simplify \
  --runs-per-query 2 --num-workers 4 --verbose
```

If the control's should-trigger query also scores `0/2`, the harness is blind in
this environment — your eval is INCONCLUSIVE, not failed. Say so plainly; do not
claim the description "passed" (negatives are meaningless when everything reads 0)
or "failed" (positives are false negatives).

## Where to actually run it
Run the trigger eval from a normal Claude Code session (not nested in the
gateway), where `claude -p`'s skill reads reach the detector. Absent that, fall
back to qualitative judgement: a description reads well if its should-trigger
phrasings are explicit and its should-NOT cases are carved out in the text.

## Independent lesson: undertrigger fix direction
If you DO get a valid signal showing weak positives, the fix is a *pushier*
description (per the CSO note's "Claude tends to undertrigger"): add explicit
trigger phrases and an "even if they never say the word X" clause, while KEEPING
the disambiguation clauses ("for Y use other-skill instead") that earn clean
negatives. Pushiness raises positives; the carve-outs protect negatives. Tune
both, not one.
