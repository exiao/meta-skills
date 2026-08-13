# Principles vs References: Skill Architecture Rule

## The Rule

SKILL.md should contain **principles only**. Case studies, detailed playbooks, research excerpts, and source-specific detail belong in `references/` files, linked from the bottom of SKILL.md with a one-line "load on-demand" pointer.

## Why

1. **SKILL.md is always loaded.** Every token in SKILL.md costs context on every invocation. Principles are reusable across all invocations; case study details are only needed when relevant.
2. **Progressive disclosure.** The agent reads SKILL.md first, then loads references only when the task matches. A 700-line SKILL.md with inline case studies forces every invocation to process content that's irrelevant 80% of the time.
3. **Maintainability.** New case studies, research, or source material can be added as reference files without bloating or restructuring the main skill.

## Pattern

In SKILL.md, write the principle as 2-5 lines:

```markdown
### Referral-as-Gate + Emotional Paywall Sequencing

Two principles from the Glam Up case study ($0 ad spend, 1M users, $150K MRR):

1. **Referral as gate, not bonus.** Make sharing a functional requirement to unlock value.
2. **Emotional commitment before price.** Build investment through a sequenced funnel.

> **Load on-demand:** `references/glam-up-case-study.md` for the full playbook.
```

In `references/glam-up-case-study.md`, put the full detail: 12-step funnel breakdown, metrics tables, what failed, product-specific adaptations, source attribution.

## When to Inline vs Reference

| Content type | Where it goes |
|---|---|
| Principle, pattern, formula | SKILL.md body |
| Comparison table (3-5 rows) | SKILL.md body |
| Case study with metrics and detail | `references/` |
| Source research excerpts | `references/` |
| Step-by-step playbook (10+ steps) | `references/` |
| Error transcripts, reproduction recipes | `references/` |
| API docs, third-party authoritative excerpts | `references/` |

## Source

User preference expressed May 2026: "the skill should be principles and references should be linked at the bottom."
