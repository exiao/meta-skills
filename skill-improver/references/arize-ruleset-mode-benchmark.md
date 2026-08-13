# Arize ruleset-mode benchmark notes

## What changed

Arize Prompt Learning has a coding-agent mode that keeps the human/static prompt frozen and optimizes only a dynamic ruleset appended at runtime. In their source this is handled by a separate ruleset argument and a meta-prompt that says: do not modify static rules, revise only the dynamic ruleset, keep rules general, do not ask for user input, return only a bullet list.

This is different from the default skill-improver loop, which mutates a working copy of the whole skill and protects only the slow-update section. Ruleset-mode flips the boundary: the human-authored body is protected, and the learned appendix is the only churn surface.

## When to use ruleset-mode

Use it when the base prompt or SKILL.md should stay byte-for-byte untouched: published/shared skills, human-owned prose, or cases where the goal is to harden behavior without changing the author's intent.

Do not use it when the base prompt is wrong. Append-only learned rules can only countermand bad instructions, which creates bloat and contradictions. If the body is buggy, use structured replace/delete edits against the working copy instead.

## Prototype benchmark result

A local prototype compared four methods on an investing/macro-analysis task with fixed persona judges: Druck-style macro investor, portfolio manager, and economics professor. The same static evals scored every method.

Weak-model first pass:
- Baseline: 0.796 test composite
- DSPy BootstrapFewShot: 0.741
- DSPy MIPROv2: 0.815
- Arize-style ruleset-mode: 1.000

Opus 4.8 reasoning-high partial/full local pass:
- Baseline: 0.870
- Arize-style ruleset-mode: 0.981
- DSPy Bootstrap/MIPRO needed careful pacing because Opus 4.8 with 8k thinking budget saturated the single local proxy account. The lesson is not that DSPy is broken; it is that high-thinking Opus optimizer benchmarks must be paced.

## Durable implementation lessons

1. Keep the evals static. Do not revise the judge prompts mid-run. The optimizer can see failure feedback, but the metric itself must not move.
2. For ruleset-mode, write only a separate `learned-rules.md` or equivalent dynamic ruleset. Inject it at runtime after the frozen base prompt.
3. Keep the normal skill-improver gates: baseline, train/validation split, val-gated keep/discard, rejected edit buffer, and sealed test set.
4. Add an early stop when validation reaches the maximum possible score. Continuing val=1.000 rounds is guaranteed discard and wastes calls.
5. For single-account local Opus 4.8 runs with high thinking, add a cross-process file-lock pacer before every model call. DSPy/LiteLLM needs pacing too, not just direct SDK calls.
6. Pace by real provider capacity, not vibes. For 8k thinking-budget Opus calls, 6s and 45s spacing were still too aggressive on the shared local proxy; the safe fallback was 180s spacing.
7. Reduce `max_tokens` reservation when possible while preserving the thinking budget. Example: thinking budget 8000, max_tokens 9500 instead of 12000.
8. Retry transient provider errors at the per-item level, not the whole eval. Restarting a 6-item eval after one 429 re-burns completed calls and can create a self-sustaining rate-limit loop.
9. For the DSPy/LiteLLM path specifically, retry IN-PLACE inside the `litellm.completion` wrapper, not just in the eval loop. DSPy's BootstrapFewShot catches a 429 raised from `completion`, marks that training example as failed, and silently drops it (you end with 0 demos and don't know why). The fix is to wrap `litellm.completion` so a transient error sleeps with exponential backoff and re-fires the SAME request, so the rate limit never bubbles up to DSPy. Per-item retry in `eval_program` covers the eval phase; the wrapper retry covers the compile phase. You need both.
10. The agent session and the benchmark share the SAME account, so your own polling is part of the rate-limit problem. When the live agent runs on the same Anthropic account the benchmark uses (single sticky proxy account), every tool call you fire to check on the run spends the same per-minute quota the run needs. Symptom: backoff keeps climbing (17s, 33s, 65s) even though nothing else is running and pacing is already high. This is session-vs-benchmark contention, not the benchmark being broken. The fix is NOT more pacing or more code, it is to STOP POLLING and let the run own the quota: launch it with `notify_on_complete=True` and go quiet, then report when it notifies. If the user wants it faster, the only real unblock is a SECOND dedicated credential for the benchmark (route only the benchmark there, never touch proxy sticky config). Do not keep checking the log every minute, that is the thing keeping it pinned.

## Suggested ruleset-mode addition to skill-improver

Add an optional mode:

- `mode=ruleset`: frozen base prompt/skill, optimize only `learned-rules.md`.
- Proposal format: concise bullet-list rules, max 8-10 bullets, general not case-specific.
- Acceptance: same validation gate as structured edits.
- Deliverable: original file unchanged plus `learned-rules.md`, results log, and test scores.

Use this mode for hardening already-good prompts. Use normal structured edits for root-cause fixes.