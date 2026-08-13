# Benchmarking prompt-opt methods against DSPy (MIPRO / BootstrapFewShot)

When the user asks "does this hill-climb flow actually beat MIPRO/DSPy?", build a
fair bake-off, not a demo. Proven setup (prompt-opt-bench, ~/projects/prompt-opt-bench/).

## Apples-to-apples invariants (only the optimizer varies)
- ONE task, ONE thin base prompt (leave headroom), ONE seeded train/val/test split,
  ONE target model, ONE STATIC metric. Every method optimizes against AND is scored
  by the identical metric.
- "Keep the evals static" = the judge prompts never change during optimization.
- Score every method on the SEALED test set ONCE at the end. Baseline (no-opt) is a
  required floor.

## Wiring
- All models via OpenRouter, one key (`OPENROUTER_API_KEY` from ~/.hermes/.env),
  base_url `https://openrouter.ai/api/v1`, model ids like `openai/gpt-4o-mini`.
- DSPy ≥3.2: `dspy.LM(f"openrouter/{model}", api_key=..., api_base=...)`.
  Metric signature `metric(example, pred, trace=None) -> float in [0,1]`; reuse the
  SAME judge composite the other methods use, so it's the same target.
- MIPROv2 needs optuna: `pip install optuna` (or `dspy[optuna]`) or it crashes at
  `_optimize_prompt_parameters`. Pass `requires_permission_to_run=False`, `auto="light"`.
- BootstrapFewShot: `max_bootstrapped_demos=2, max_labeled_demos=0`.
- Background runs: the gateway's bg shell may use a different python than the
  interactive one. Use the venv's absolute python
  (`~/.hermes/hermes-agent/venv/bin/python3`) that has openai+dspy. And `mkdir -p
  results` BEFORE redirecting a log into it (Python creating the dir later is too late
  for the shell `>` redirect).

## Persona-judge metric pattern
3 persona judges (e.g. Druckenmiller / portfolio manager / economics professor),
each 3 binary checks, temp 0, JSON `{"results":[bool,...]}`. Composite = mean of all
bits in [0,1]. Per-judge breakdown surfaces WHERE a method gained/lost. Keep judge
prompts in a frozen dict; do not let any optimizer edit them.

## Arize ruleset-mode (the method under test)
Frozen base prompt + append-only learned bullet ruleset, injected at runtime
(`base + "\n\nAdditional rules:\n" + ruleset`). Each round: run train, judge, feed
per-judge FAIL labels + criteria into a meta-prompt (cross-model: stronger optimizer,
weaker target), get a candidate ruleset, KEEP only if held-out val composite strictly
improves. This is the static-vs-dynamic split from Arize's coding-agent template
(constants.py `CODING_AGENT_META_PROMPT_TEMPLATE`); their SDK injects via Claude
Code's `--append-system-prompt`. Note: their open SDK `optimize()` loop has NO
in-loop acceptance gate (overwrites the prompt every batch); the val-gate is your
addition.

## Result + the caveat that matters (observed)
On a thin base, ruleset-mode 0.796→1.000, MIPRO 0.796→0.815, Bootstrap 0.796→0.741
(few-shot demos can HURT by pulling answers toward generic completeness, away from
rubric specifics). Ruleset-mode wins BECAUSE its optimizer sees the judges' criteria
and writes bullets that map ~1:1 onto them. That is partly teaching-to-the-test, and
the judges + meta-prompt sharing a model family inflates the ceiling. Report the
number honestly AND discount it: "very good at hitting an explicit rubric," not
"objectively better analysis." The fair follow-up: a split-judge design — optimize
against a subset of judges, score on a HELD-OUT judge the optimizer never saw — and
a stronger target model so baseline isn't already near ceiling on easy judges.

## Takeaway for choosing a method
Ruleset-mode (append-only, val-gated) wins when criteria are explicit and you want to
harden toward them. MIPRO wins when the metric is opaque/black-box and you want
robustness over rubric-fitting. BootstrapFewShot can regress on rubric-graded tasks.
