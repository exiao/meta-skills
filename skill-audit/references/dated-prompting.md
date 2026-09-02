# Dated Prompting Patterns

Source: the `/claude-api prompt-audit` skill bundled with Claude Code (2.1.258,
`shared/prompt-audit.md`). This file adapts it to skills. Run `/claude-api prompt-audit` in
Claude Code for the full original, including the API-request-code checks a skill audit skips.

The premise: prompts accumulate instructions tuned to older models. Emphasis added because an
old model under-triggered, step-by-step scripts added because an old model planned poorly,
format scaffolds written before the API had structured outputs. Current models follow
instructions more literally, so leftover text is not merely wasted tokens. Specific outdated
instructions actively degrade behavior: over-triggering, over-planning, rigid answers in gray
areas.

**The frame is fit, not length.** Merely irrelevant text is comparatively harmless. Hunt
specific dated instructions. Never justify a cut by character count.

## Contents

- [Two questions to ask first](#two-questions-to-ask-first)
- [DP1: Pressure language](#dp1-pressure-language)
- [DP2: Superseded scaffolds](#dp2-superseded-scaffolds)
- [DP3: Fossils](#dp3-fossils)
- [DP4: Choreography and examples](#dp4-choreography-and-examples)
- [DP5: Skill-file rot](#dp5-skill-file-rot)
- [The trigger/behavior split](#the-triggerbehavior-split)
- [What not to flag](#what-not-to-flag)
- [Confidence and the flag-versus-fix threshold](#confidence-and-the-flag-versus-fix-threshold)
- [Verifying a removal](#verifying-a-removal)

## Two questions to ask first

These come before the pattern tables, and they decide most findings on their own.

**1. Could the model already know this?**

- **Keep what only the author knows**: audience and product, environment facts, the quality bar,
  tool contracts and mechanics, genuinely hard judgment calls, and the *reasons* behind
  constraints. This is context, and context is never cruft.
- **Removal candidates**: restatements of trained defaults ("be accurate and helpful"), behavior
  the model already does unprompted (thoroughness, planning, tool use), and workarounds for
  failures the target model no longer has.

A sharper form of the same question: is the line a **constraint on behavior** (removal candidate,
test it) or **context the model cannot get elsewhere** (usually keep)? This is what stops the
audit becoming a length contest, because a naive shortening pass deletes exactly the
highest-value words.

**2. Which failure, on which model, did this line prevent, and does that failure still
reproduce?**

Where git history exists, `git blame` the skill. A line added as a mitigation for a model no
longer in use is a presumptive removal candidate. A line nobody can justify is suspect by
default.

Without history, idioms still date a file. `<scratchpad>` and `<brainstorm>` tags, "think step by
step", assistant-turn prefills, quotes-first extraction scaffolds, and ROLE / CONTEXT / RULES /
EXAMPLES boilerplate all mark text written for much earlier generations, using techniques that
are now natively trained or superseded by API features. **Idiom-dating alone is low confidence.**
It earns medium or high only when paired with a reason grounded in the target model's documented
behavior, and a blame line tying the text to a retired model's era is the strongest form of that
pairing.

## DP1: Pressure language

Older models needed forcefulness. Current models are highly responsive to the system prompt, so
the same text over-applies. This cuts both ways: inflated emphasis causes over-triggering and
rigid behavior, while leftover hedges are now read literally as permission to under-deliver.

| Written for older models | Current models |
|---|---|
| `CRITICAL: You MUST use this tool when...` | `Use this tool when...` |
| `IMPORTANT: NEVER do X` several times over | State the one or two real constraints plainly, with the reason |
| `If in doubt, use [tool]` / `Default to [tool]` | Delete, or `Use [tool] when it would improve X` |
| `Be thorough. Do not be lazy. Do not stop early.` | Delete. Current models are proactive by default |
| `Try to include a summary if possible` when it is required | `Include a summary.` |
| `You have a tendency to over-X, so...` | State the wanted behavior: `Keep responses to the length the question needs.` |

When several instructions are each marked critical, the markers stop carrying information. The
prompt's register also becomes the output's register: an anxious prompt produces a cautious,
hedging model. Emphasis is not banned. It is a tested, scoped fix for one demonstrably
underweighted instruction, not a first-draft voice.

**Overlap with C5.** C5 fails a bare absolute with no stated reason. DP1 fails the *density and
volume* of emphasis even where each instance has a reason. Score one or the other, not both.

## DP2: Superseded scaffolds

These are not toned down, they are swapped for the feature that replaced them.

| Scaffold | Replacement |
|---|---|
| "Think step by step", `<scratchpad>` / `<thinking>` tag instructions | Adaptive thinking plus an effort setting. On a thinking model the incantation is redundant at best |
| "Use the think tool to plan", "plan before acting" | Delete. Current models plan unprompted, and these cause over-planning. If behavior is still too aggressive, lower effort rather than adding prose |
| "Show your thinking", required reasoning sections in the output | Read thinking blocks from the API. On Fable 5.1 this can trigger a refusal |
| Assistant-turn prefill and the JSON-forcing stack around it: stop sequences, regex extraction, retry-on-parse loops, "output ONLY valid JSON" | Structured outputs. Prefill 400s on Fable 5.1 and 4.6-and-later Opus/Sonnet tiers |
| "Summarize progress every N tool calls"; hard word caps | Delete and re-baseline. Current models narrate appropriately, and output caps starve reasoning on hard problems |
| Inline lookup tables, point systems, arithmetic rubrics the model must compute | Data in files or tool results, arithmetic in code. Leave the model the judgment layer |
| `budget_tokens`, non-default `temperature`/`top_p`/`top_k`, stale beta headers | Per-model migration lists. Where these error, the retry code around them is removable too |
| Forced tool use (`tool_choice: any` or a named tool) and JSON-via-forced-tool | A prompt instruction naming the tool under `tool_choice: auto`, or structured outputs. Returns 400 on Fable 5.1 and Mythos 5.1 |

Most skills only hit the first three rows. The request-config rows apply to skills that ship
API-calling scripts.

## DP3: Fossils

Text that outlived the model it was written for.

| Pattern | Why it is cruft now | Fix |
|---|---|---|
| Model-version workarounds: formatting fixes, over-refusal softeners, "known issue with [model]" comments, date-conditional guidance | Nobody owns the removal, so the skill accumulates the union of every generation's mitigations | Each mitigation names the model it patched. If that model is retired, remove and re-test |
| Migration-relative phrasing: "X now works differently", "also counts", "no longer" | The text is a diff against a previous version the model never saw, implying phantom alternatives | Write as if the current rules are the only rules that ever existed |
| Patch accretion: many narrow conditionals, each traceable to one incident | The model navigates a maze of special cases instead of a principle, and fails unpredictably between them | Generalize the principle. Test removals, not just additions |
| Unenforced instructions: rules no code path, eval, or reviewer checks | If nothing checks it and nobody noticed, it carries no signal | Enforce in code what can be enforced in code. Delete what nothing enforces |
| Identity stubs standing in for context ("You are a helpful assistant") | A one-line role statement is fine. The defect is identity text substituting for audience, product, and quality bar | Flag only when it is the sole context the skill gives |
| **Update suppressors**: "hold all findings for the final response", "don't narrate", "no interim updates" | Tuned against models that over-narrated. Current models, Fable 5.1 especially, under-narrate with these present | Remove first and re-test. If more narration is wanted, say *when* user-facing text is wanted |
| **Anti-formatting rules**: "never use bullets", "no headers", "no bold" | Written against models that over-formatted. Fable 5.1 already under-formats, so the rule strips formatting the reader wanted | Remove, or replace with a rule saying when formatting is appropriate |
| Instruction re-insertion on a cadence ("reminder: ..." repeated every few turns) | A retention crutch for models that lost instructions over long sessions. Current models retain a once-stated instruction | Remove and re-test. A genuinely per-turn reminder should be turn-scoped, not duplicated |

The two bolded rows are the highest-yield finds in a personal skill library, because both were
reasonable advice two model generations ago.

**Overlap with P3.** P3 fails an aspirational instruction with no mechanism. DP3's unenforced row
fails a rule that *has* a mechanism nobody runs. Score one.

## DP4: Choreography and examples

| Pattern | Why it is cruft now | Fix |
|---|---|---|
| Step-by-step choreography for judgment tasks (`STEP 1: ... STEP 2: ...`) | Skills written for prior models are often too prescriptive for current ones and degrade output. The model's own plan usually beats a hand-written script | State outcomes, constraints, and how to verify. Keep numbered steps only where order truly matters |
| Prohibition lists ("do not X, never Y, avoid Z") | Describing success beats enumerating failure. A prohibition against a failure the model was not going to make can anchor it toward that failure | Keep prohibitions whose failure reproduces on the target model. Rewrite the rest as positive statements |
| Example over-indexing: the single gold output, stale few-shot blocks | Concrete examples are the strongest signal in a prompt. The model matches their length, tone, and structure, so an example written for an older model freezes that model's behavior into the new one | Several deliberately varied examples labeled illustrative. Keep examples that pin a genuinely format-sensitive shape |
| Bullet walls for behavioral guidance | Bullets flatten priority and sever rules from reasons, and prompt format bleeds into output format | Structure for reference data, prose for behavior, carrying the "because" |
| Padding: generic virtues, repetition as reinforcement, kitchen-sink edge cases | The model treats everything as actionable signal. Duplicated rules make it spend effort reconciling wordings, and bulk inflates thinking spend | Say it once, in the right place. Cover the hard judgment calls instead of the easy parts |
| Grader vocabulary ("you will be graded on", "hidden tests") | Describes the scoring apparatus instead of the requirement, and pushes effort toward being-watched | State every requirement the grader checks. Never describe the grader |
| Strategy coaching beside task rules ("it's usually best to...") | The author's heuristics are wrong in some situations and the model's plan is usually better | If removing the sentence would not change what is legal or how success is measured, it is strategy. Delete it |

**Prohibition clusters are judged by provenance, one line at a time.** For a run of unconditional
"never / don't / must not" lines, ask of each: does it carry a stated reason or encode a real
business or policy constraint? Do not ask whether the model still needs the guardrail, because
that question keeps everything (nothing is *harmful* to say). Prohibitions encoding observable
constraints stay: refund caps, data rules, compliance language, promises the business must not
make. Prohibitions that merely describe undesirable output style with no provenance are cruft:
banned-phrase lists, tic lists, "don't start with Certainly" written against an older model's
habits. A surrounding cluster of legitimate reasoned prohibitions does not launder the
no-provenance ones mixed into it.

**Output-shaping choreography is one pattern, so remove every limb.** Fixed interim-update
cadences ("after every third tool call, post a progress note"), numeric output ceilings ("under
120 words", "at most five bullets"), and cut-the-detail instructions are the same over-constraint
written for models that rambled. A stated operational reason does not convert a numeric clamp
into a keeper: re-express the goal as audience and outcome without the number. Removing the
cadence while keeping the ceilings leaves the pattern in place.

**Overlap with M4.** M4 fails length *floors* ("at least N", "comprehensive") and a missing
ceiling where an output template exists. DP4 fails numeric *clamps* as over-constraint. A single
number costs one point, not two.

## DP5: Skill-file rot

Skill files inherit everything above, plus failure modes of their own. **Skill size is a tax paid
on every trigger**, which is why this group hits hardest on a preloaded skill.

| Pattern | Why it is cruft now | Fix |
|---|---|---|
| Verbose SKILL.md explaining what the model already knows | Every paragraph must justify its token cost, and general programming knowledge does not | Apply "could the model already know this?" paragraph by paragraph |
| Wrong degrees of freedom | Exact scripts over-constrain judgment calls; vague prose under-constrains fragile operations | Match specificity to fragility: prose heuristics for open fields, exact commands only for narrow bridges |
| **The recency trap**: one session's stumble encoded as a permanent rule | The next session steps around a pothole that is not there | Before keeping a rule, ask whether it would have helped most recent sessions or just the one that wrote it |
| **Volatile specifics**: hardcoded paths, flags, version numbers, API claims with no verification date | Skills rot factually as code ships, and nothing re-checks them | Encode architecture, data models, and workflows. Verify surviving factual claims against current code as part of the audit |
| Time-sensitive content ("if before [date]"), option menus, info duplicated across SKILL.md and its references | Dates rot, menus of alternatives dilute, duplicates drift apart | An "old patterns" section instead of dates; one default plus an escape hatch; information in exactly one place |
| **History narratives**: past tense, incident IDs, PR numbers, pinned model names | A rule's authority is the behavior it prescribes, not the incident that motivated it. Pinned model names silently degrade after the next release | State the current rule and drop the archaeology |
| **Trigger-case enumeration**: descriptions listing near-synonymous example queries, growing one phrase per missed trigger | Descriptions ride in every request, so enumeration taxes every token budget and generalizes worse than intent categories | Name generalized categories of intent |

**Signals:** a SKILL.md not readable in one sitting; hardcoded paths and version pins; past tense
in an instruction file; a description that only ever grows in git history.

The last row is the one real limit on the trigger-text exemption below. Routing text may carry
urgency, but it may not become an ever-growing phrase list.

**Overlap.** A wall-of-text SKILL.md already fails S2, and a hardcoded path already shows up in
the drift audit. Score DP5 for the *dating* shapes specifically: recency trap, history narrative,
trigger enumeration, and unverified volatile claims.

## The trigger/behavior split

One deliberate exception, and it protects the thing DP1 would otherwise eat.

**Text whose job is routing may carry calibrated urgency.** A skill's frontmatter `description`,
a trigger block, a "Use when:" list. Skills currently under-trigger, so emphasis there is doing
real work, ideally tuned against a trigger eval. **Text whose job is behavior should explain
rather than shout.**

These look identical to a grep. Classify by function before flagging. Never trim a description
under DP1.

The same split governs tool descriptions, which are audited for precision and contract accuracy,
not brevity. The common failure there is *under*-description: a vague one-liner, parameters with
no descriptions, no when-not-to-use. The fix is more text, three or four sentences minimum. What
changed on current models is which content belongs there: contract and mechanics in, behavioral
steering and worked examples out.

## What not to flag

An audit that only says delete hurts the people who follow it most diligently. These stay even
when a grep matches.

1. **Context is never cruft.** Audience, product, environment facts, quality bar, constraints,
   and the reasons for them. What only the author knows. Too-short prompts produce generic output
   because the model fills gaps with safe defaults.
2. **Cruft is not length.** The harm comes from specific outdated instructions, not volume.
3. **Fragile operations keep exact scripts.** Prescriptive text is correct where exactly one
   sequence is safe: destructive commands, auth flows, compliance steps.
4. **Tool contract detail stays and often grows.** Parameter semantics, limits, failure modes,
   what the tool does not return.
5. **Prohibitions against current demonstrated failures stay.** The test is whether the failure
   reproduces on the target model, not whether the sentence pattern-matches a prohibition.
6. **Routing text may carry calibrated urgency.**
7. **Format-pinning examples stay** on genuinely format-sensitive outputs, labeled illustrative.
8. **Working redundancy is not cruft.** Duplicated content that is functioning, the same contract
   stated in two files, is a refactoring preference. Propose deduplication only when the copies
   actually disagree.
9. **A one-line role statement is fine.**
10. **Deliberate recap is not padding.** A single end-of-prompt restatement of the key constraints
    is a known good pattern. The anti-pattern is scattered duplication.
11. **Re-baselining adds text too.** Matching a skill to a new model sometimes means adding
    guidance for the new model's failure modes. The job is fit, in both directions.

**An audit that finds nothing should change nothing.** A clean surface is a valid outcome, and an
empty diff beats a manufactured one.

## Confidence and the flag-versus-fix threshold

Tag every DP finding:

- **High**: documented in current model docs, or it errors on the target model.
- **Medium**: consistent, widely observed behavior, such as example over-indexing.
- **Low**: heuristic or idiom-dating. Flag, do not edit.

Idiom-dating alone is low confidence. It earns medium or high only when paired with a reason
grounded in the target model's documented behavior. A `git blame` line tying the text to a
retired model's era is the strongest form of that pairing: ask which failure, on which model,
this line prevented, and whether that failure still reproduces.

A finding matching a documented pattern above gets a concrete proposed action. Reserve `flag` for
low-confidence idiom-dating and out-of-scope items. Do not downgrade a documented match to `flag`
because it seems minor or reads as a soft nudge. Those are reasons the user may decline the fix,
not reasons to withhold it.

## Verifying a removal

Removal is a hypothesis, not a conclusion.

- **Probe behavior, not self-report.** Run a small behavioral check before and after on a scratch
  copy. Asking the model whether it needs an instruction is not a measurement.
- **One change at a time** where stakes are high, so regressions attribute to their cause.
- **If a cut regresses, re-add simply.** Re-express the instruction in its minimal form and
  re-probe. Do not restore the verbose original.
- **Check out-of-band dependencies before deleting.** Grep the wider system for the exact text
  first. Evals, tests, and cron prompts sometimes match on skill strings.
- **Re-audit at every model release.** Skills are per-model artifacts. A line that is load-bearing
  on one generation is cruft on the next.
