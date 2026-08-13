# Building the Eval Suite (step 2)

How to turn the user's stated criteria into binary evals, plus the max-score math. Detailed good/bad eval examples, refusal evals, trajectory evals, and golden cases live in `eval-guide.md`.

## eval format and rules

Convert the user's eval criteria into a structured test. Every check must be binary: pass or fail, no scales.

**Format each eval as:**

```
EVAL [number]: [Short name]
Question: [Yes/no question about the output]
Pass condition: [What "yes" looks like — be specific]
Fail condition: [What triggers a "no"]
```

**Rules for good evals:**
- Binary only. Yes or no. No "rate 1-7" scales. Scales compound variability and give unreliable results.
- Specific enough to be consistent. "Is the text readable?" is too vague. "Are all words spelled correctly with no truncated sentences?" is testable.
- Not so narrow that the skill games the eval. "Contains fewer than 200 words" will make the skill optimize for brevity at the expense of everything else.
- 3-6 evals is the sweet spot. More than that and the skill starts parroting eval criteria back instead of actually improving.

See [references/eval-guide.md](references/eval-guide.md) for detailed examples of good vs bad evals.

---

## refusal and trajectory evals

Both are covered in full (when to use, how to write, inverted scoring, trajectory capture requirements) in [eval-guide.md](eval-guide.md). Add 2-3 refusal inputs when the skill handles real data and a confident wrong answer is worse than a refusal. Add trajectory evals when correct output from a wrong process would be a false positive. Refusal inputs participate in the same data split as normal inputs.

---

## max score calculation

```
max_train = [number of evals] × [runs per experiment] × [number of training inputs]
max_val   = [number of evals] × [runs per experiment] × [number of validation inputs]
```
The test ceiling is computed the same way but only used at final evaluation.
