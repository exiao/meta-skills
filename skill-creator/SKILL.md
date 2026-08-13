---
name: skill-creator
preloaded: true
description: "Create a skill or modify an existing one. Write a failing test before touching SKILL.md. Also runs evals and benchmarks skill performance."
---

> **Source:** Anthropic internal skill, local copy, do not modify without checking upstream.

# Skill Creator

A skill for creating new skills and iteratively improving them.

At a high level, the process of creating a skill goes like this:

- Decide what you want the skill to do and roughly how it should do it
- Write a draft of the skill
- Create a few test prompts and run claude-with-access-to-the-skill on them
- Help the user evaluate the results both qualitatively and quantitatively
  - While the runs happen in the background, draft some quantitative evals if there aren't any. If some already exist, use them as is or modify them. Then explain them to the user.
  - Use the `eval-viewer/generate_review.py` script to show the user the results, and let them look at the quantitative metrics
- Rewrite the skill based on the user's evaluation and on any glaring flaws in the benchmarks
- Repeat until you're satisfied
- Expand the test set and try again at larger scale

Your job when using this skill is to figure out where the user is in this process, then jump in and help them progress. Maybe they say "I want to make a skill for X". Help narrow down what they mean, write a draft, write the test cases, figure out how they want to evaluate, run all the prompts, and repeat.

If they already have a draft, go straight to the eval/iterate part of the loop.

Always be flexible. If the user says "I don't need to run a bunch of evaluations, just vibe with me", do that instead.

Then after the skill is done (again, the order is flexible), run the skill description improver, which has its own script, to optimize triggering.

Cool? Cool.

## Communicating with the user

The skill creator gets used by people across a wide range of familiarity with coding jargon. Plumbers are opening terminals; parents and grandparents are googling "how to install npm". Most users are still fairly computer-literate.

Pay attention to context cues to understand how to phrase your communication. In the default case:

- "evaluation" and "benchmark" are borderline, but OK
- for "JSON" and "assertion" you want serious cues that the user knows those terms before using them unexplained

It's OK to briefly explain terms if you're in doubt.

---

## TDD Pre-flight

**Iron Law: NO SKILL WITHOUT A FAILING TEST FIRST.** Applies to new skills AND edits. No exceptions.

### RED Phase (mandatory before drafting SKILL.md)

Before writing a single line of SKILL.md, run the RED phase:

1. Write 3+ **pressure scenarios**, realistic prompts that would genuinely benefit from the skill.
2. Run them **WITHOUT the skill** (no SKILL.md, no skill path). Use subagents if available.
3. **Document the baseline behavior verbatim**, what did Claude actually do? Where did it fall short?

This matches Anthropic's "baseline run" concept, except it is **mandatory up front** rather than optional later. The baseline run IS the failing test. If Claude already handles the prompts well without the skill, you don't need the skill.

Only proceed to "Creating a skill" below after baseline results are documented.

### Reference Files

Detailed guidance for each phase lives in `references/`:
- `the-iron-law-same-as-tdd.md`, why this is non-negotiable
- `red-green-refactor-for-skills.md`, the full RED → GREEN → REFACTOR cycle
- `anti-patterns.md`, what failure looks like
- `bulletproofing-skills-against-rationalization.md`, how to resist skipping tests
- `common-rationalizations-for-skipping-testing.md`, excuses to reject
- `red-flags-stop-and-start-over.md`, when to bail
- `skill-creation-checklist-tdd-adapted.md`, step-by-step checklist
- `claude-search-optimization-cso.md`, CSO techniques for description optimization
- `public-skills-repo-hygiene.md`, what stays public and what moves to private storage
- `installing-third-party-skills.md`, installing via `npx skills add`, importing a vendor ZIP, and integrating into the Hermes library
- `principles-vs-references.md`, what belongs in SKILL.md vs a reference
- `inline-patch-safety.md`, editing a skill without breaking it
- `red-phase-cold-subagent-for-tool-skills.md`, baselining a tool skill with a cold subagent
- `trigger-eval-nested-false-negatives.md`, why a nested run scores 0.00 on everything
- `trigger-eval-harness-pitfalls.md`, run_eval / run_loop gotchas
- `manual-only-and-bypass-skills.md`, skills that shouldn't auto-trigger
- `skill-writing-guide.md`, anatomy, progressive disclosure, and writing patterns
- `running-and-evaluating-test-cases.md`, the full spawn/grade/review sequence
- `skill-library-maintenance.md`, folding research and session learnings back in
- `improving-the-skill.md`, turning feedback into changes, plus blind comparison
- `description-optimization.md`, the trigger eval loop
- `platform-specific-instructions.md`, Claude.ai and Cowork differences
- `schemas.md`, JSON structures for evals.json, grading.json, etc.

---

## Creating a skill

### Capture Intent

Start by understanding the user's intent. The current conversation might already contain a workflow the user wants to capture (e.g., they say "turn this into a skill").

If so, extract answers from the conversation history first: the tools used, the sequence of steps, corrections the user made, input/output formats observed. The user may need to fill the gaps, and should confirm before proceeding.

1. What should this skill enable Claude to do?
2. When should this skill trigger? (what user phrases/contexts)
3. What's the expected output format?
4. Should we set up test cases to verify the skill works? Skills with objectively verifiable outputs (file transforms, data extraction, code generation, fixed workflow steps) benefit from test cases.

Skills with subjective outputs (writing style, art) often don't need them. Suggest the appropriate default based on the skill type, but let the user decide.

### Interview and Research

Proactively ask questions about edge cases, input/output formats, example files, success criteria, and dependencies. Wait to write test prompts until you've got this part ironed out.

Check available MCPs - if useful for research (searching docs, finding similar skills, looking up best practices), research in parallel via subagents if available, otherwise inline. Come prepared with context to reduce burden on the user.

### Definition of Done: proven commands, not paraphrased docs

Borrowed from Anthropic's `run-skill-generator` leak, which is built on one ruthless idea: **a markdown file by itself cannot click a button.** If a skill ships runnable artifacts (a `scripts/` driver, a command sequence, code blocks presented as "run this"), the skill is not done until you've proven those artifacts work.

The gate, applied to any skill that contains commands or scripts:

1. **Every command block in SKILL.md is one you ran this session and it worked.** Not copied from a README, not inferred from the tool's docs, not "this should work." If you wrote `python -m scripts.foo --bar`, you ran exactly that and saw it succeed. If you can't run it (missing creds, wrong host), say so in the skill rather than shipping an unverified command.
2. **If the skill bundles a driver/script, you launched it and interacted with the real thing**, not its test suite, the actual entrypoint. For a script that produces a file, the file is on disk. For something with a UI, a screenshot is on disk.
3. **Treat every claim in the source docs as disprovable.** "Requires macOS", "needs a GPU", "run `npm start` (human path)" are hypotheses, not facts. Find the programmatic path, try the workaround, and document what actually worked.

The stop rule: **if you're about to write the skill and you have not run its commands, STOP. You are about to paraphrase docs that already exist.** That document is called the README; a skill that just restates it is the README with extra steps. RED proves the skill is needed; this proves the skill actually works.

### Write the SKILL.md

Based on the user interview, fill in these components:

- **name**: Skill identifier
- **description**: When to trigger, what it does. This is the primary triggering mechanism. Include both what the skill does AND specific contexts for when to use it. All "when to use" info goes here, not in the body.

 Descriptions consume ~ceil(bytes/4) tokens in the system prompt for preloaded skills, on every message in every session. Keep under 200 bytes when possible; every byte has a permanent cost.

 Claude currently has a tendency to "undertrigger" skills, so make descriptions a little bit "pushy". Instead of "How to build a simple fast dashboard to display internal Anthropic data.", write "How to build a simple fast dashboard to display internal Anthropic data. Make sure to use this skill whenever the user mentions dashboards, data visualization, internal metrics, or wants to display any kind of company data, even if they don't explicitly ask for a 'dashboard.'"

 **Inverse case, manual-only / never-self-trigger skills.** Some skills are high-stakes enough that the user wants them to fire ONLY on explicit invocation by name, such as a skill that bulk-merges PRs to main using a guard bypass.

 For these, do the OPPOSITE of pushy. Write an anti-trigger description like "MANUAL-ONLY. Do NOT load or invoke this skill on your own under any circumstance. Only run it when the user explicitly types the skill name or says 'run <name>'." Set `preloaded: false` so its metadata never enters the system prompt. Put a STOP guard as the first line of the SKILL.md body ("If you're reading this because you inferred it might help, STOP. This skill only runs on the user's explicit command.").

 When such a skill performs an action normally forbidden by a standing rule (e.g. "never merge to main"), loading the skill IS the override. Don't ask for a separate ack, but DO keep an in-skill confirm gate (print a plan/table, get the user's go-ahead) before the irreversible step. See `references/manual-only-and-bypass-skills.md`.
- **compatibility**: Required tools, dependencies (optional, rarely needed)
- **source/update section**: When a skill is created from third-party docs, a copied prompt, an API page, or a product getting-started guide, put a `## Skill source` section at the bottom of SKILL.md. Include the canonical source URLs and a short update procedure so a future agent can refresh the skill without rediscovering where it came from.
- **the rest of the skill :)**

### Public/shared skill repositories

When editing a skills repo that is public or intended to be shared, use a conservative public/private boundary. Default to sanitize and keep skills public when the reusable workflow survives.

Move a skill to ignored internal storage only when it is inherently a private runbook, such as private infra topology, deploy pipelines, local proxy routing, cron/reporting operations, account-specific automations, or private-project eval/prompt loops.

**Validator drift pitfall:** A repo-local skill validator can lag the live skill schema. If a validator rejects an already-existing key such as `preloaded` while the rest of the repo and runtime use it, don't treat that as a new PR blocker by default.

Record the validator failure, then verify with a narrower YAML/frontmatter parse check (required `name` + non-empty `description`, preserving existing accepted keys). Keep the validator drift separate from the behavior fix unless the PR is specifically about schema validation.

Before opening a PR that removes private skills from a public bundle:
- Preserve local copies under an ignored `internal/` directory if the user still needs them.
- Do not add ignored `internal/` paths to public README/INSTALL docs.
- Update generated docs and install lists to remove stale references.
- Search for old paths/names, parse moved internal frontmatter, and review the public diff for leaked secrets, account IDs, app IDs, cron IDs, private domains, private paths, or operational snapshots.


Read `references/public-skills-repo-hygiene.md` for the full decision rule and validation checklist.

### Skill Writing Guide

Skill anatomy, progressive disclosure, the three-level loading system, domain organization, the principle of lack of surprise, and writing patterns for output formats and examples all live in `references/skill-writing-guide.md`. Read it before drafting.

Two rules to keep in mind while you draft: keep SKILL.md under 500 lines, and treat the length counts as ceilings rather than targets. Cut anything that does not change what the reading agent does.

### Writing Style

Explain to the model why things are important in lieu of heavy-handed musty MUSTs. Use theory of mind and make the skill general rather than narrow to specific examples.

### Test Cases

After writing the skill draft, come up with 2-3 realistic test prompts, the kind of thing a real user would actually say. Share them with the user: [you don't have to use this exact language] "Here are a few test cases I'd like to try. Do these look right, or do you want to add more?" Then run them.

Save test cases to `evals/evals.json`. Don't write assertions yet, just the prompts. You'll draft assertions in the next step while the runs are in progress.

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "User's task prompt",
      "expected_output": "Description of expected result",
      "files": []
    }
  ]
}
```

See `references/schemas.md` for the full schema (including the `assertions` field, which you'll add later).

---

## Running and evaluating test cases

Read `references/running-and-evaluating-test-cases.md` and follow it end to end. It is one continuous sequence.

Spawn with-skill and baseline runs in the same turn. Draft assertions while they run. Capture `total_tokens` / `duration_ms` from each completion notification. Grade against `agents/grader.md`, aggregate with `python -m scripts.aggregate_benchmark`, then launch `eval-viewer/generate_review.py`.

Do NOT use `/skill-test` or any other testing skill. Put results in `<skill-name>-workspace/` as a sibling to the skill directory, organized by `iteration-N/eval-<ID>/`.

---

## Skill library maintenance

Read `references/skill-library-maintenance.md` when the user shares a link, thread, article, or notes and says "incorporate this skill", or asks you to review the session and update the skill library.

It covers the fast incorporation path for existing skills, the post-session review pass, and the update order: loaded skill, then class-level umbrella, then references, and a new skill only as a last resort.

Named pitfalls in there: "consolidate" is not "delete to cut a count", subagent partial completion, don't delegate multi-skill patches, editing a SKILL.md that is inlined verbatim into a runtime prompt, and oversized SKILL.md patch limits.

Use the full RED → GREEN → REFACTOR eval loop for new skills, large rewrites, and changes where quality can be benchmarked.

---

## Improving the skill

This is the heart of the loop. You've run the test cases, the user has reviewed the results, and now you make the skill better based on their feedback.

Read `references/improving-the-skill.md` for how to think about improvements (generalize from feedback, keep the prompt lean, explain the why, look for repeated work worth bundling into `scripts/`), the iteration loop, and the optional blind comparison system.

Your thinking time is not the blocker here. Take your time and get into the head of the user.

---

## Description Optimization

The description field in SKILL.md frontmatter is the primary mechanism that determines whether Claude invokes a skill. After creating or improving a skill, offer to optimize the description for better triggering accuracy.

Read `references/description-optimization.md` for the four steps: generate 20 trigger eval queries, review them with the user via `assets/eval_review.html`, run `python -m scripts.run_loop`, and apply `best_description` to the frontmatter. It also explains how skill triggering works.

> **Pitfall, trigger eval reads 0.00 across the board?** Before blaming the description, see `references/trigger-eval-harness-pitfalls.md` and `references/trigger-eval-nested-false-negatives.md`. Run a known-good skill like `simplify` as a control; if it also scores 0, the harness is broken, not your skill.

---

### Package and Present (only if `present_files` tool is available)

Check whether you have access to the `present_files` tool. If you don't, skip this step. If you do, package the skill and present the .skill file to the user:

```bash
python -m scripts.package_skill <path/to/skill-folder>
```

After packaging, direct the user to the resulting `.skill` file path so they can install it.

---

## Platform-specific instructions

On Claude.ai and in Cowork the core workflow is the same (draft → test → review → improve → repeat), but the mechanics change. Read `references/platform-specific-instructions.md`.

Claude.ai has no subagents: run test cases yourself one at a time, skip baselines, benchmarking, description optimization, and blind comparison, and present results inline.

Cowork has subagents but no display: pass `--static <output_path>` to the viewer and proffer a link. GENERATE THE EVAL VIEWER *BEFORE* evaluating outputs yourself.

---

## Reference files

The agents/ directory contains instructions for specialized subagents. Read them when you need to spawn the relevant subagent.

- `agents/grader.md`, How to evaluate assertions against outputs
- `agents/comparator.md`, How to do blind A/B comparison between two outputs
- `agents/analyzer.md`, How to analyze why one version beat another

The references/ directory is indexed above under "Reference Files". Two worth calling out here:
- `references/schemas.md`, JSON structures for evals.json, grading.json, etc.
- `references/manual-only-and-bypass-skills.md`, how to build a skill that must NOT self-trigger (anti-pushy description, `preloaded: false`, STOP banner) and how a skill can perform a guard-blocked action via `HERMES_BACKUP_BYPASS=1` (the committed-script-not-heredoc rule; inline bypass is blocked by the Hermes plugin's process-env substring match).

---

Repeating one more time the core loop here for emphasis:

- Figure out what the skill is about
- Draft or edit the skill
- Run claude-with-access-to-the-skill on test prompts
- With the user, evaluate the outputs:
  - Create benchmark.json and run `eval-viewer/generate_review.py` to help the user review them
  - Run quantitative evals
- Repeat until you and the user are satisfied
- Package the final skill and return it to the user.

Please add steps to your TodoList, if you have such a thing, to make sure you don't forget. If you're in Cowork, please specifically put "Create evals JSON and run `eval-viewer/generate_review.py` so human can review test cases" in your TodoList to make sure it happens.


## Hard rules (restated)

Repeated here because the body is long and these are the rules that get skipped.

- **Iron Law: no skill without a failing test first.** Applies to new skills AND edits, no exceptions. Run the RED phase (3+ pressure scenarios without the skill) before writing a line of SKILL.md, because a skill that never failed without it has no evidence it helps.
- **Generate the eval viewer before judging output yourself.** Run `eval-viewer/generate_review.py` so a human can review the cases.
- **Descriptions are routing instructions, not summaries.** State what it does AND the literal trigger phrases.
- **Keep SKILL.md under 500 lines and 20KB.** Detail goes in `references/`, and every new reference must be added to the index in the same edit or it becomes unreachable.
