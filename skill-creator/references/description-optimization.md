# Description Optimization

The trigger-eval loop that tunes a skill's description for reliable invocation.

The description field in SKILL.md frontmatter is the primary mechanism that determines whether Claude invokes a skill. After creating or improving a skill, offer to optimize the description for better triggering accuracy.

> **Pitfall, trigger eval reads 0.00 across the board?** Before blaming the description, see `references/trigger-eval-harness-pitfalls.md`. The harness can give uniform false negatives two ways: writing the probe to `.claude/commands/` (slash command, never auto-invoked) instead of `.claude/skills/<name>/SKILL.md`, and a `--timeout` too short for an agentic `claude -p` run (now defaulted to 60). Run a known-good skill like `simplify` as a control; if it also scores 0, the harness is broken, not your skill. For ground truth on one query, instrument a single direct `claude -p` run.

### Step 1: Generate trigger eval queries

Create 20 eval queries, a mix of should-trigger and should-not-trigger. Save as JSON:

```json
[
  {"query": "the user prompt", "should_trigger": true},
  {"query": "another prompt", "should_trigger": false}
]
```

The queries must be realistic and something a Claude Code or Claude.ai user would actually type. Not abstract requests, but requests that are concrete and specific and have a good amount of detail. For instance, file paths, personal context about the user's job or situation, column names and values, company names, URLs. A little bit of backstory. Some might be in lowercase or contain abbreviations or typos or casual speech. Use a mix of different lengths, and focus on edge cases rather than making them clear-cut (the user will get a chance to sign off on them).

Bad: `"Format this data"`, `"Extract text from PDF"`, `"Create a chart"`

Good: `"ok so my boss just sent me this xlsx file (its in my downloads, called something like 'Q4 sales final FINAL v2.xlsx') and she wants me to add a column that shows the profit margin as a percentage. The revenue is in column C and costs are in column D i think"`

For the **should-trigger** queries (8-10), think about coverage. You want different phrasings of the same intent, some formal, some casual. Include cases where the user doesn't explicitly name the skill or file type but clearly needs it. Throw in some uncommon use cases and cases where this skill competes with another but should win.

For the **should-not-trigger** queries (8-10), the most valuable ones are the near-misses, queries that share keywords or concepts with the skill but actually need something different. Think adjacent domains, ambiguous phrasing where a naive keyword match would trigger but shouldn't, and cases where the query touches on something the skill does but in a context where another tool is more appropriate.

The key thing to avoid: don't make should-not-trigger queries obviously irrelevant. "Write a fibonacci function" as a negative test for a PDF skill is too easy, it doesn't test anything. The negative cases should be genuinely tricky.

### Step 2: Review with user

Present the eval set to the user for review using the HTML template:

1. Read the template from `assets/eval_review.html`
2. Replace the placeholders:
   - `__EVAL_DATA_PLACEHOLDER__` → the JSON array of eval items (no quotes around it, it's a JS variable assignment)
   - `__SKILL_NAME_PLACEHOLDER__` → the skill's name
   - `__SKILL_DESCRIPTION_PLACEHOLDER__` → the skill's current description
3. Write to a temp file (e.g., `/tmp/eval_review_<skill-name>.html`) and open it: `open /tmp/eval_review_<skill-name>.html`
4. The user can edit queries, toggle should-trigger, add/remove entries, then click "Export Eval Set"
5. The file downloads to `~/Downloads/eval_set.json`, check the Downloads folder for the most recent version in case there are multiple (e.g., `eval_set (1).json`)

This step matters, bad eval queries lead to bad descriptions.

### Step 3: Run the optimization loop

> **Before trusting any score:** if you launch this loop from inside another agent session (the Hermes gateway, or any nested context), the trigger detector can give a flat **0.00 on every query**, a harness false negative, not a bad description. Run a quick control against a known-good skill first; if `simplify` also scores 0 on "run /simplify", the harness is blind here. See `references/trigger-eval-nested-false-negatives.md`. Run trigger evals from a top-level Claude Code session.

Tell the user: "This will take some time, I'll run the optimization loop in the background and check on it periodically."

Save the eval set to the workspace, then run in the background:

```bash
python -m scripts.run_loop \
  --eval-set <path-to-trigger-eval.json> \
  --skill-path <path-to-skill> \
  --model <model-id-powering-this-session> \
  --max-iterations 5 \
  --verbose
```

Use the model ID from your system prompt (the one powering the current session) so the triggering test matches what the user actually experiences.

While it runs, periodically tail the output to give the user updates on which iteration it's on and what the scores look like.

This handles the full optimization loop automatically. It splits the eval set into 60% train and 40% held-out test, evaluates the current description (running each query 3 times to get a reliable trigger rate), then calls Claude to propose improvements based on what failed. It re-evaluates each new description on both train and test, iterating up to 5 times. When it's done, it opens an HTML report in the browser showing the results per iteration and returns JSON with `best_description`, selected by test score rather than train score to avoid overfitting.

### How skill triggering works

Understanding the triggering mechanism helps design better eval queries. Skills appear in Claude's `available_skills` list with their name + description, and Claude decides whether to consult a skill based on that description. The important thing to know is that Claude only consults skills for tasks it can't easily handle on its own, simple, one-step queries like "read this PDF" may not trigger a skill even if the description matches perfectly, because Claude can handle them directly with basic tools. Complex, multi-step, or specialized queries reliably trigger skills when the description matches.

This means your eval queries should be substantive enough that Claude would actually benefit from consulting a skill. Simple queries like "read file X" are poor test cases, they won't trigger skills regardless of description quality.

### Trigger-harness pitfalls (run_eval.py / run_loop.py): read before trusting a 0% score

The trigger harness spawns nested `claude -p` subprocesses and watches the stream for a `Skill`/`Read` tool_use matching a temporary probe it registers. Two failure modes make it report a uniform 0% (everything "not triggered") even when the description is fine. **Before concluding a description fails, run a control: point the harness at a known-good installed skill (e.g. `simplify`) with an obviously-triggering query. If the control also reads 0, the harness is broken, not your skill.**

1. **Skills vs slash commands are different registries (Claude Code split them).** An auto-invokable skill must live in `.claude/skills/<name>/SKILL.md` and shows up in the init event's `skills[]` array. A file in `.claude/commands/<name>.md` registers as a *slash command* (`slash_commands[]`) that only fires when a user literally types `/name`, the model never auto-invokes it, so the probe is unreachable and every query reads false. The harness was fixed to write to `.claude/skills/` (June 2026); if you see it writing to `.claude/commands/`, that's the bug.
2. **Default timeout was too short.** Agentic `claude -p` runs need ~15-30s just to reach the first tool decision, and far longer under parallel load (10 workers = ~20 concurrent processes contending for CPU + the rate limiter). The old 30s default killed runs before the `Skill` event streamed. Default is now 60s; for slow/contended runs pass `--timeout 75` and drop `--num-workers` to 2-3. A run that completes in time detects correctly (verified: isolated runs hit 1.00 where the same query in a 10-worker batch read 0.00).

**Structural limit that remains:** the detector waits for a *live agentic run* to emit a real tool_use, not just the routing decision, so a correct-but-slow trigger can still time out under load. A low aggregate batch score with passing isolated/low-concurrency runs means the harness is throughput-limited, NOT that the description is bad. Trust a clean single instrumented run over a contended batch.

### Step 4: Apply the result

Take `best_description` from the JSON output and update the skill's SKILL.md frontmatter. Show the user before/after and report the scores.
