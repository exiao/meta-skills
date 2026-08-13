# Model-fit: writing skills for Claude Opus 5

Source: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5

The rest of the checklist scores a skill's structure and never asks whether its instructions
match the model that will read them. Guidance tuned for a weaker model becomes active harm on a
stronger one: it does not just waste tokens, it suppresses behavior the model would otherwise
produce. This dimension catches that.

Four behaviors changed with Opus 5, and each one turns a former best practice into an anti-pattern.

## 1. It verifies its own work already

Opus 5 checks its output before returning it, unprompted. An explicit instruction to re-check
compounds with that native behavior: the model runs the loop twice and the second pass finds
nothing. The docs are blunt about it. If your prompt says "include a final verification step for
any non-trivial task" or "use a subagent to verify," remove it. Removing reduces wasted tokens
with no loss in quality.

The same applies to self-correction. "Double-check your answer" and "re-verify before responding"
add cost and improve nothing.

**The distinction that matters.** Checking REALITY is not self-re-checking, and it must survive
the audit untouched:

| Cut it | Keep it |
| --- | --- |
| re-read your own answer | run the app and watch it work |
| double-check your reasoning | hit the endpoint, read the status code |
| verify your work with a subagent | `gh pr checks` on the current head |
| re-verify before responding | read the row back out of the database |
| add a final verification step | screenshot the rendered UI |
| confirm your output is correct | `git fetch` then read `origin/<default>` |
| "root cause understood?" as a gate item | "issue reproduced consistently?" as a gate item |

The left column asks the model to think about its thinking. The right column asks it to go look at
the world. Only the left column is the finding. Getting this backwards is the most damaging
mistake you can make in this audit, because the right column is exactly the evidence-gathering
discipline that stops an agent from claiming success it never observed.

**The third case: process gates.** A phase-completion checklist ("do not proceed to Phase 2
until...") is neither column. It asks the model to confirm it went and looked. Judge it item by
item: a gate item that names an artifact (a command that ran, a file that exists, a reproduced
symptom, a red test) is workflow control and stays. A gate item that asks the model to affirm an
internal state ("root cause understood," "hypothesis formed," "fully understood") is the M1 shape
and should be rewritten to name its artifact, not deleted wholesale. Killing a whole phase gate
because it looks like a re-check will gut the skill.

## 2. It delegates readily, and delegation is expensive

Opus 5 coordinates subagents well, which is why it reaches for them too often. Delegation pays on
genuinely independent, sizeable tracks. On small work it multiplies cost and latency for nothing.

Two shapes to flag:
- **Subagent-as-verifier.** Named explicitly in the docs as something not to build. A same-model
  child re-reading the parent's work has the same blind spots as the parent.
- **Uncapped fan-out.** A skill that says "launch agents in parallel" as its default path, with no
  size gate and no ceiling on how many.

A good gate names a threshold and a fallback: "for a large diff (roughly 500+ changed lines or 5+
files), fan out to at most 4 reviewers. Below that, do the passes yourself in this context."

## 3. It obeys "be conservative" literally

Opus 5 finds real bugs at a high rate, and its extra findings are mostly real rather than noise.
Precision and recall are both high, so the old defensive instructions now cost you findings.

If a review or audit prompt says "only report high-severity issues," "be conservative," "avoid
false positives," "don't nitpick," or caps output at "the top 3 issues," the model complies and
reports less. Real defects go unsaid.

The fix is always the same shape: collect everything, then filter in a SEPARATE pass. Report
everything found, rank by severity afterward, and drop only what the evidence disproves. A hard
numeric cap ("top 3") is the worst version, because the model discards findings rather than
ranking them.

This item is scored on review, audit, critique, and evaluation skills. A skill that fetches data
or wraps a CLI has nothing to suppress.

## 4. It writes long

Both conversational responses and files written to disk run longer than on prior models. Effort
settings control how much the model THINKS, not how much it SAYS, so length has to be prompted
for directly.

Flag two opposite shapes:
- **Missing ceiling.** A skill that produces a written deliverable (report, plan, memo, audit,
  PR description, doc) with no length guidance. Add: "match length to what the task needs, no
  filler sections, redundant summaries, or boilerplate."
- **Explicit floor.** "At least 10 questions," "at least 500 words," "comprehensive," "exhaustive,"
  or a mandatory section list that forces boilerplate on small tasks. A floor is padding by
  construction: it fires even when the task is trivial. Convert floors to ranges or ceilings.

## Also worth flagging

**Scope ceilings.** Opus 5 expands scope, adding steps that were not requested. A narrow-task
skill (one fix, one lookup, one deploy) benefits from an explicit ceiling: deliver what was asked,
say so in a sentence if a better approach exists, then do the task as asked, and stop short of
work clearly beyond the request. Do not add a second ceiling to a skill that already has one.

**Stale capability workarounds.** Instructions written around a weaker model's limits that are now
counterproductive. The common case is vision: Opus 5 reads charts, diagrams, screenshots, and UI
well, and is strongest when it has tools to crop and iterate. A skill that says "do not read the
image back" or "describe the screenshot in text because the model cannot see it" is throwing away
a capability. Also flag hardcoded effort or reasoning settings carried over from an older model;
note them for a re-sweep rather than changing the numbers yourself.

**Anti-thinking rules.** A rule telling the model not to think or not to reason increases internal
tag leakage into visible output. Remove it. Instructions that name `<thinking>` tags specifically
are less effective than a general "do not include internal or system XML tags."

## Auditing this dimension

**Every grep hit needs a read in context before you flag it. This governs all four recipes below,
not just M1.** The words these patterns match appear descriptively all the time: "comprehensive"
in "a comprehensive test suite exists," "verify" in "verify against the live endpoint," "single"
in "form a single hypothesis." A grep hit is a candidate, never a finding.

```bash
grep -nEi "double[- ]check|re-?verify|re-?read your|loop back to check|final verification step" SKILL.md
grep -nEi "(subagent|spawn|delegate).{0,50}(verify|double[- ]check|confirm)" SKILL.md
grep -nEi "only report (high|critical)|be conservative|skip false positives|top [0-9]+ issues" SKILL.md
grep -nEi "at least [0-9]+ (questions|words|issues)|comprehensive|exhaustive|feel free to go longer" SKILL.md
```

Then apply the exception that belongs to each item: M1 spares reality checks and artifact-based
process gates, M3 spares numeric limits on method (one hypothesis, one variable at a time), M4's
missing-ceiling half fires only on skills shipping an output template.

Quote the offending clause in the finding, name which of the four behaviors it fights, and give
the replacement text rather than just "remove this."
