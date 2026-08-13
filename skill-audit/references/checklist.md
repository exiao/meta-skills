# Skill Audit Checklist

## Structure (4 points)

### S1: Frontmatter Quality
- Has YAML frontmatter with `name` and `description`
- Description includes BOTH what the skill does AND when to trigger it (specific phrases, scenarios)
- No extra frontmatter fields beyond name/description
- **Pass:** Description reads like a routing instruction, not a summary
- **Fail:** Description only says what the skill does, not when to use it

### S2: Progressive Disclosure
- SKILL.md is under 500 lines
- Detailed docs live in `references/`, not inline
- Deterministic/repeated code lives in `scripts/`
- Output resources (templates, images) live in `assets/`
- References are one level deep from SKILL.md (no chains)
- Long reference files (100+ lines) have a table of contents
- **Pass:** SKILL.md is lean; details are discoverable but not loaded by default
- **Fail:** SKILL.md is a wall of text, or references chain 3+ levels deep

### S3: No Extraneous Files
- No README.md, CHANGELOG.md, INSTALLATION_GUIDE.md, QUICK_REFERENCE.md
- No user-facing docs (the skill IS the documentation for the agent)
- **Pass:** Every file serves the agent directly
- **Fail:** Contains files meant for humans, not agents

### S4: Clean Organization
- Skill directory named in lowercase-hyphen format
- Only uses scripts/, references/, assets/ subdirectories (plus SKILL.md at root)
- No empty directories
- **Pass:** Clean tree with no surprises
- **Fail:** Random files at root, empty dirs, mixed naming

## Content Quality (6 points)

### C1: Gotchas Section
- Has an explicit "Gotchas" or equivalent section documenting known failure patterns
- Gotchas are specific (not "be careful with X" but "X fails when Y because Z")
- **Pass:** Reader learns from past failures without hitting them
- **Fail:** No gotchas, or gotchas are vague warnings

### C2: Signal-to-Noise Ratio
- Only includes info the model doesn't already know
- No explanations of common libraries/APIs the model is trained on
- Prefers concise examples over verbose explanations
- Uses imperative/infinitive form
- **Pass:** Every paragraph justifies its token cost
- **Fail:** Explains things like "OAuth is an authorization framework..." or pads with filler

### C3: Degrees of Freedom
- High freedom for tasks where multiple approaches are valid
- Low freedom (specific scripts, exact sequences) for fragile operations
- Not over-railroading (too specific for variable tasks)
- Not too vague (no guidance for fragile operations)
- **Pass:** Specificity matches the task's fragility
- **Fail:** Either micromanages flexible tasks or hand-waves critical steps

### C4: No Duplication
- Information lives in ONE place (SKILL.md or references, not both)
- No repeated instructions across sections
- **Pass:** Single source of truth for each piece of info
- **Fail:** Same guidance appears in SKILL.md and a reference file

### C5: Instruction Line Lints
Per-line checks on the imperative content of SKILL.md and its references. These sharpen C2/C3 with concrete, greppable thresholds (adapted from ccmd's CLAUDE.md analyzer). A skill is prose instructions to an agent; the same shapes that make a CLAUDE.md rule get ignored make a skill step get ignored.

- **Missing-why prohibitions:** every `NEVER` / `DO NOT` / `don't` line has its reason within ~2 lines (`because`, `Reason:`, a named past incident). This is the SOUL "every rule carries its reason" convention applied to skills. A bare ban gets followed until an edge case, then the agent guesses. **Fail:** a hard prohibition with no stated why.
- **Over-long instruction lines:** a single directive line over ~28 words gets treated as one signal and its back half is skimmed past. **Fail:** a fragile step buries its critical clause in a 30+ word run-on. Fix = split into 2-3 short directives, don't just shorten.
- **Vague terms:** flag untestable words in operational steps: appropriate(ly), properly, carefully, thoughtfully, cleanly, as needed, where applicable, when possible, good, best. The agent can't tell when it succeeded. **Fail:** a step says "handle errors appropriately" instead of naming the condition/tool. (High-freedom prose is fine; this targets steps meant to be precise.)
- **Unescaped absolutes:** `always` / `never` / `must` on a precise operational step with no escape clause (`unless`, `except`, `when X then`). Real workflows have exceptions; a naked absolute gets rounded off. **Fail:** an absolute the skill's own body later contradicts or that obviously needs an "unless." (A genuinely inviolable safety ban WITH a why is correct, not a fail: keep it.)

Score C5 as pass if the imperative content is clean on all four. This is one point. Don't double-penalize: a vague line already flagged under C3, or a duplicate already under C4, doesn't also cost C5. C5 targets the missing-why / long-line / untestable-word / bare-absolute shapes specifically.

### C6: Comprehensibility
Can a competent reader understand each section on a single read, or do they have to reverse-engineer the intent? C5 lints individual lines; C6 judges whether a whole section *reads clearly*. A skill can pass every line-level check and still be confusing: dense, assumes context it never states, or buries the point in qualifiers. This is the `evaluate-content` **Sweep 1 (Clarity)** pass applied to a SKILL.md, plus the `writer` read-aloud test. Run those two lenses over the skill's prose, not marketing-copy standards.

Apply these attributes from `evaluate-content`'s Clarity sweep and Quick-Pass checks:
- **Confusing sentence structure / sentences saying too much:** a directive that packs 3+ ideas into one sentence forces re-reads. One idea per sentence. (Distinct from C5's word-count lint: C5 counts words, C6 judges whether the meaning is followable.)
- **Unclear pronoun references / ambiguous statements:** "it," "this," "that" with no clear antecedent, or a step whose subject is guessable but not stated.
- **Jargon or insider language:** domain terms, acronyms, and internal names (tool names, file names, project codenames) are defined or self-evident on first use. Undefined shorthand only the author understands = fail.
- **Missing context / assuming reader knowledge:** a section that only makes sense if you already know something it never states.
- **Buried point / abstract instead of concrete:** the takeaway is smothered under qualifications, or the section stays abstract where a concrete example would land it. Front-load the point.
- **Rule of One:** each major section (H2/H3) carries one main idea and says it up front. A reader shouldn't finish a section unsure what it was for.

Then apply the `writer` **read-aloud test**: read the section aloud. Where you stumble or lose the thread, that passage is broken.

- **Pass:** every section is understandable on one read; a competent agent or human knows what to do without decoding it.
- **Fail:** a section is dense/ambiguous enough that the reader must re-read to grasp basic intent, leans on undefined jargon, or buries its point under qualifiers.

C6 is one point. Don't double-penalize: a wall-of-text already failing S2, filler already failing C2, a duplicated explanation already failing C4, or a 28+ word run-on already failing C5 doesn't also cost C6. C6 targets *comprehension-blocking* writing specifically: unclear intent, undefined jargon, missing context, buried points. When flagging, quote the confusing passage and say what's missing (a definition, a lead sentence, a split, a concrete example).

## Design Patterns (2 points)

### D1: Skill Type Clarity
Does the skill fall cleanly into one of these types?
- **Library & API Reference:** How to use a specific lib/CLI/SDK. Includes code snippets + gotchas.
- **Product Verification:** Test/verify code works. Paired with playwright, tmux, etc. Includes assertion scripts.
- **Data Fetching & Analysis:** Connect to data/monitoring. Includes credentials, dashboard IDs, query workflows.
- **Business Process & Team Automation:** Automate repetitive workflows (standups, tickets, recaps). Saves logs for consistency.
- **Code Scaffolding & Templates:** Generate framework boilerplate. Composable scripts.
- **Pass:** Clearly one type, or intentionally combines two with good reason
- **Fail:** Tries to do everything, unclear purpose

### D2: Advanced Patterns (where applicable)
- **Config pattern:** If skill needs user-specific config, uses config.json (not hardcoded values)
- **Memory/state:** If skill tracks state across runs, uses stable paths (not skill dir which gets wiped on upgrade)
- **Composability:** Scripts are helper libraries the agent composes, not monolithic
- **Skill references:** References other skills by name where dependencies exist
- **Pass:** Uses appropriate patterns for its needs
- **Fail:** Hardcodes config, loses state on upgrade, or has monolithic scripts

## Executability (1 point)

### E1: Shipped commands are proven, not paraphrased
Applies only to skills that ship runnable artifacts: a `scripts/` driver, a command sequence, or code blocks presented as "run this." Skills that are pure prose/reference (no commands to run) auto-pass E1.

The failure this catches is invisible to S1-D2: a skill can be perfectly structured while shipping a driver that crashes or a command block someone pasted from a README and never ran. The agent trusts it, runs it, it breaks on step one. That skill is worse than no skill.

- The obvious entrypoint dry-runs clean: `python -m scripts.<x> --help`, `bash scripts/<x>.sh --help`, or equivalent returns without import/syntax/path errors.
- Command blocks reference real files, flags, and module paths (cross-check against the drift audit).
- No command block is presented as proven ("run this") when the skill itself contains no evidence it was ever executed.
- **Pass:** Entrypoint dry-runs clean and commands match real artifacts.
- **Fail:** The driver errors on `--help`, a command references a flag/module that doesn't exist, or the skill ships an unverified command sequence as if proven. Borrow `run-skill-generator`'s test: a skill that just restates the README without a proven command is the README with extra steps.

The audit is static, so E1 is lighter than skill-creator's author-side gate (you can't re-run the whole workflow). Dry-run the entrypoint, cross-check command blocks against real files, and flag anything unproven rather than vouching for it.

## Prompt-Attention Hygiene (3 points, conditional)

Applies to skills whose body is behavioral instructions to an agent: SOUL/system-prompt files, skills with an `## Output Format` template, persona/lens skills, review rubrics, any skill that tells the model *how to behave* rather than *how to call a tool*. A pure data-fetch or CLI-reference skill (no behavioral-instruction body) auto-passes P1-P3, the way a pure-prose skill auto-passes E1.

This dimension exists because the rest of the checklist scores structure and never asks whether the prompt is written the way attention research says it must be. The findings behind each item live in [references/prompt-attention-research.md](prompt-attention-research.md); cite the paper when you flag the item.

### P1: Positional placement of non-negotiables
- Hard constraints (safety bans, "never without approval," irreversible-action gates) appear in the top ~15% of the body AND are restated near the very end.
- They are not buried only in a mid-file section, which is the lowest-attention zone.
- **Why:** models show a U-shaped attention bias (highest at start and end, degraded in the middle), and the effect is strongest when input fills up to ~50% of the window (2307.03172, 2508.07479). A rule that lives only in the middle of a long body is the rule most likely to be skipped.
- **Pass:** critical constraints are front-loaded and echoed at the end.
- **Fail:** a hard constraint sits only mid-file, or a long body states its bans once and never restates them at the close.

### P2: No diluted restatement of the same instruction
- The same behavioral rule is not re-expressed 3+ times in near-synonyms across sections (e.g. "be direct" / "don't coddle" / "clarity first" / "useful beats agreeable" as four separate passes at one idea).
- Distinct from C4: C4 targets a duplicated *explanation* (the same walkthrough appearing twice); P2 targets one *instruction* smeared across many restatements, which inflates the body and pushes higher-priority rules out of the high-attention zone.
- **Why:** models routinely fail to reconcile overlapping or conflicting demands inside a single system prompt, and longer prompts raise derailment probability (2502.12197, 2602.17046). Restating one idea five ways spends attention budget without adding a constraint.
- **Pass:** each behavioral rule is stated once, in one place, with its reason.
- **Fail:** one idea is re-said 3+ times in different words across the body. Fix = merge into a single canonical statement.

### P3: Enforceable instructions only
- Every hard rule is testable and has a mechanism to act on it.
- Aspirational directives the model has no way to execute ("make me notice," "track my loop-closing rate across sessions," "create motion") are flagged unless backed by a concrete tool, file, or tracked state the skill points to.
- **Why:** models struggle to enforce instruction hierarchies even on simple conflicts, and system/user role labels are weaker levers than assumed; unenforceable rules train the model to treat the whole doc as vibes rather than binding constraints (2502.15851, 2404.13208). An instruction with no mechanism is decoration.
- **Pass:** every directive is either testable behavior or wired to a real mechanism.
- **Fail:** the skill carries aspirational rules with no backing tool/file/state. Fix = give the mechanism or cut the line.

Score P as one point per item (3 total) for applicable skills. Don't double-penalize: a redundant *explanation* already flagged under C4 doesn't also cost P2, and a vague untestable term already flagged under C5 doesn't also cost P3. P targets the positional / diluted-instruction / unenforceable shapes specifically.

## Model Fit (up to 4 points, conditional: expect 1-2 to apply on a typical skill)

Does the skill's guidance match the model that reads it? The rest of the checklist scores
structure and never asks this. Instructions tuned for a weaker model become active harm on a
stronger one: they suppress behavior the model would otherwise produce. Full reasoning, the
keep/cut table, and grep recipes are in [references/opus5-model-fit.md](opus5-model-fit.md).

**Scope.** These items describe Claude Opus 5 class models (guide dated 2026-07). They are
model-conditional, not universal. A cut made under M1 assumes the consuming profile runs a model
that self-verifies; the same skill loaded under a weaker fallback model is now missing a check it
needed. When a skill is known to run on a cheaper lane or fallback chain, say so in the finding
and prefer rewriting the instruction over deleting it.

### M1: No redundant self-verification
Opus 5 verifies its own work unprompted. Explicit re-check instructions compound with that and
burn a second pass for nothing.

- **Fail:** the skill says "double-check your answer," "re-verify before responding," "re-read
  your output," "loop back and re-check earlier steps," or "include a final verification step."
- **Critical exception, do NOT flag:** instructions to check REALITY (run the app, hit the
  endpoint, `gh pr checks`, read the row back from the database, screenshot the UI, `git fetch`
  then read `origin/<default>`). That is evidence-gathering, and it is the discipline that stops
  an agent claiming success it never observed. Cutting it is a regression, not a fix.
- **Process gates and completion checklists are a third category, not a fail by default.** KEEP a
  gate whose items assert on an third-party artifact (a command that ran, a file that exists, a test
  that is red, a reproduced symptom). CUT or rewrite only the items that ask the model to affirm
  it thought hard enough ("root cause understood," "hypothesis formed"). A phase gate is workflow
  control, not output re-reading.
- The test: does the instruction ask the model to think about its own thinking (cut), to go look
  at the world (keep), or to confirm it went and looked (gate: keep if the items name artifacts)?
- **Pass:** no self-re-check loops; reality checks and artifact-based gates intact.

### M2: Delegation is gated and capped
Opus 5 delegates readily, and delegation multiplies cost on small work.

- **Fail:** the skill tells the agent to spawn a subagent to verify or double-check its own work
  (named in the docs as an anti-pattern), or makes parallel fan-out the default path with no size
  gate and no ceiling on agent count.
- **Pass:** delegation is reserved for genuinely independent, sizeable tracks, with a named
  threshold and a "do it yourself below this" fallback.
- Applies only to skills that mention subagents, delegation, or parallel agents.

### M3: No suppression in review skills
Opus 5 has high precision AND recall, and it follows conservative instructions literally,
reporting less. Defensive phrasing now costs real findings.

- **Fail:** "only report high-severity issues," "be conservative," "avoid false positives,"
  "don't nitpick," "skip false positives," or a hard numeric cap like "identify the top 3 issues."
  A numeric cap is the worst form: the model discards findings instead of ranking them.
- **Critical exception, do NOT flag: a numeric limit on METHOD is not suppression.** "Form a
  single hypothesis," "change one variable at a time," "bisect one commit," "fix one thing then
  re-run" constrain how the work is done, not what gets reported. Cutting those destroys the
  discipline the skill exists to enforce. M3 fires only on limits applied to the FINDINGS the
  skill reports out.
- **Pass:** collect everything, then rank or filter in a separate pass, dropping only what the
  evidence disproves.
- Applies only to review, audit, critique, and evaluation skills. A data-fetch or CLI skill has
  nothing to suppress and auto-passes.

### M4: Output length is calibrated
Opus 5 writes longer responses and longer files than prior models, and effort settings control
thinking rather than output length. Length must be prompted for directly.

- **Fail (explicit floor):** "at least N questions/words," "comprehensive," "exhaustive," or a
  mandatory section list that forces boilerplate onto small tasks. A floor is padding by
  construction because it fires even when the task is trivial. This half of M4 is the one that
  finds real defects.
- **Fail (missing ceiling), narrow trigger:** only when the skill ships an `## Output Format`
  template or a mandatory section list, where absent length guidance actually changes what gets
  generated. Do NOT fail a skill merely for producing text without a length sentence: that fires
  on nearly everything and tells you nothing.
- **Pass:** length is matched to the task, with no filler sections, redundant summaries, or
  boilerplate. Floors are expressed as ranges or ceilings.

Score M as one point per applicable item. Don't double-penalize: a vague word already flagged
under C5 ("complex," "as needed") or an under-specified step already flagged under C3 doesn't also
cost M2, and a padded section already failing C2 doesn't also cost M4. M targets the
model-mismatch shapes specifically: redundant self-verification, uncapped delegation, findings
suppression, and length floors.

**Two unscored model-fit shapes. Report these in the Warnings section of the scorecard, not as
point items:**
- **Missing scope ceiling** on a narrow-task skill (one fix, one lookup, one deploy). Opus 5
  expands scope unprompted. Do not flag a skill that already has a ceiling in any wording (a
  "no while-I'm-here improvements" rule counts).
- **Stale capability workaround**: an instruction written around a weaker model's limits, most
  often vision ("do not read the image back," "describe the screenshot because the model cannot
  see it"). Also note hardcoded effort or reasoning settings carried from an older model, for a
  re-sweep rather than a change.

## Scoring

Point items: S1-S4 (structure), C1-C6 (content), D1-D2 (design), E1 (executability), B1-B2
(budget), P1-P3 (prompt-attention hygiene, conditional), M1-M4 (model fit, conditional). A
pure-prose skill that ships no runnable commands auto-passes E1; a skill with no
behavioral-instruction body auto-passes P1-P3; M items apply only where the skill delegates,
reviews, or writes a deliverable. C6 (comprehensibility) applies to every skill. Score as a
fraction of applicable points, then map to the rating band below.

| Score | Rating |
|-------|--------|
| 9-10  | Excellent: production quality, could go in a marketplace |
| 7-8   | Good: works well, minor improvements possible |
| 5-6   | Average: typical first draft, needs iteration |
| 3-4   | Below average: missing key patterns, needs rework |
| 1-2   | Poor: fundamentally misstructured |
