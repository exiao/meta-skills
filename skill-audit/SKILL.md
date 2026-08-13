---
name: skill-audit
preloaded: true
description: "Score a skill against best practices and output a scorecard with fixes. Use for audit this skill, review this skill, skill health check, check for drift."
---

# Skill Audit

Score a skill's structure and design. Not its output quality (that's skill-improver) and not
building one (that's skill-creator).

Read [references/checklist.md](references/checklist.md) first. It defines every item and which
ones apply. Then read the Traps section below before flagging any M1, C4, or broken-link
finding. Those calls look obvious in a grep and are backwards in practice.

## Process

1. Read the whole skill directory, every file.
2. Score the checklist: S1-S4, C1-C6, D1-D2, B1-B2, E1, P1-P3, M1-M4. One point each, as a
   fraction of the items that apply.
3. Write the scorecard. Rank fixes by impact.
4. Ask before changing anything.

Three items need a command, not a read:

- **E1**: dry-run the entrypoint (`python -m scripts.<x> --help`) before scoring it.
- **C5**: `grep -nE "NEVER|DO NOT|don't" SKILL.md references/*.md` for bans with no reason.
- **Reference health**: `python3 ~/.hermes/skills/skills-meta/skill-audit/scripts/check_reference_health.py <skill-dir>`.
  Add `--orphans` for the whole tree. Exits 1 on a dangling pointer, so it can gate a commit.

For codebase drift, prompt-budget weight, usage, upstream forks, and gap audits, see
[references/drift-and-budget.md](references/drift-and-budget.md).

## Traps

Five judgment calls that come from audits that got them wrong.

**Never strip a reality check while hunting M1.** This is the most damaging mistake here.
"Re-read your own answer" and "run the app and watch it work" look alike in a grep and are
opposites in effect. The first is a redundant self-check on a model that already self-verifies.
The second is the evidence-gathering that stops an agent claiming success it never observed,
and it is the house rule in SOUL.md. Read every M1 hit in context. If the instruction points at
the real system (run it, hit the endpoint, `gh pr checks`, read the row back, screenshot it,
`git fetch` then read origin), it passes. Only self-directed re-reading fails. Getting this
backwards makes a skill worse while the scorecard says it improved.

**A terminal constraint checklist is not C4 duplication.** A skill that states a rule in its
body and restates it as a one-liner in a closing "Rules" or "Anti-Patterns" list is doing the
right thing, co-locating the ban where the model acts. C4 targets the same *explanation* twice
as full prose, like a walkthrough orphaned mid-skill and repeated in its own section. Ask which
one you're looking at before flagging.

**A stated rule can still be unreachable.** A skill can ban something in a mid-file
Anti-Patterns list and still violate it, because the model generates from the `## Output Format`
block and never re-consults distant rules. When a skill has an output template, check its hard
constraints sit with the template. A sample output that breaks a stated rule proves the
constraint is misplaced. Confirmed: a research lens banning verdicts, severity, and pre-mortems
emitted all three until the bans moved into the Output Format block, fixing 4 of 6 evals.

**Cross-skill pointers are legitimate, not broken links.** A SKILL.md routinely points at a
reference owned by a sibling (`cpe-research` to render-cli's `build-failure-diagnostics.md`). A
naive "does this exist in my own references/?" check calls these broken. In one audit 184 of 218
resolved to a sibling, only 34 were dangling. The script above already resolves against the
whole tree.

**Repointing a dead link: match content, not filename.** Don't substitute the nearest-named or
nearest-dated sibling. Grep the surviving references for the topic the pointer promised
(`grep -l '10b5-1' references/*.md`) and point at the file that has it. A proximity guess sends
the agent to unrelated content, which is worse than a dead link because it looks like it worked.

## Scorecard

```
# Skill Audit: [skill-name]
## Type: [Library & API Reference | Product Verification | Data Fetching & Analysis |
##        Business Process & Team Automation | Code Scaffolding & Templates]
## Score: [X]/[applicable]

### Passing
- [item]: [what's good]

### Warnings
- [item]: [what's borderline and why]
- [unscored model-fit shapes: missing scope ceiling, stale capability workaround]

### Failing
- [item]: [what's wrong + the specific fix]

### Recommended Actions
1. [highest impact first]
```

Quote the offending line for every failing item. A finding without a line is not actionable.

One line per item. No preamble, no summary paragraph. Skip any section with nothing in it
rather than writing "none." A clean skill's scorecard is three lines, and that's the right
length.

## Scoring

- Be honest. A typical first draft scores 4-6/10.
- Report every issue, then rank. Don't filter while reading, don't cap the count.
- When in doubt, fail. A false flag costs less than a missed defect.
- D2 passes if the skill doesn't need those patterns. Fail only if it needs them and skips them.
- Don't penalize a small skill for being short. A 20-line SKILL.md for a small job is correct.
- The description is what people get wrong most. It's a routing instruction, not a summary.

## Fixing what you find

When two skills overlap, fold the smaller into the larger as a section, then delete it and
confirm the survivor's description covers both trigger sets.

When one skill has grown past 500 lines or 20KB with duplicate-topic references, that's
accretion. Score it as one root cause, not as separate S2, B2, and C4 failures. Symptom checks
and the split procedure are in [references/mega-file-split.md](references/mega-file-split.md).
