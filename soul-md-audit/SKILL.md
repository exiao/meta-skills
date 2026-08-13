---
name: soul-md-audit
preloaded: true
description: "Score a SOUL.md, agent persona, or system prompt against how Hermes loads it. Use when someone shares a persona file to review or grade. Not for skills."
---

# SOUL.md Audit

Score a SOUL.md or agent persona file on two things: how Hermes loads and truncates it, and how the model reads and follows it.

A file can read well to a human and still fail. Half its rules may sit in the truncated middle, it may say "be direct" five different ways, or it may carry instructions the model has no way to obey.

Read [references/checklist.md](references/checklist.md) first. The research behind the attention
items is in [references/attention-basis.md](references/attention-basis.md), cite the paper when
you flag one. When recommending a rewrite, point at
[references/template.md](references/template.md) so the fix has a concrete target shape.

## What this audits (and what it doesn't)

Use this for **identity, voice, and operator-behavior** files: `~/.hermes/SOUL.md`, a persona template, a profile or lane's SOUL, an "autonomous operator" constitution, a system-prompt draft.

**Classify the archetype first. It changes what counts as a fail:**
- **Persona/voice SOUL** (a general assistant whose job is *who it is*): voice is the spine. Commands, paths, and project detail are drift that belongs in AGENTS.md.
- **Task-operator SOUL** (a profile or lane with one main job, like research-lead): the operational spine is the identity. Primary objective, skill inventory, delegation workflow, command sequences, and folder map all belong in SOUL, unless a loaded AGENTS.md already owns them.

  Order runs: who you are, primary objective, how to behave and write, skills, workflows, memory, folders. Don't flag this content as drift. Judge whether it's ordered right and whether it has a better home that actually loads.

If you're auditing a *skill*, use skill-audit instead. This skill borrows skill-audit's P-dimension research and applies it to persona and operator files, where truncation and identity-slot mechanics also matter.

## Process

1. **Get the file.** Read the whole thing. Note its length in chars (`wc -c`), since truncation behavior depends on it.
2. **Run the checklist.** Score M1-M3 (Hermes mechanics), V1-V2 (voice quality), P1-P3 (attention hygiene), and R1 (readable, understandable, and no longer than the job needs). Each item is 1 point, binary. Short files (well under the truncation limit, a dozen lines) auto-pass M2 and P1. Positional placement only bites once a file is long enough to have a middle.
3. **Generate the scorecard** (format below).
4. **Offer to fix.** List fixes in priority order. For a rewrite, keep the user's voice; the audit finds problems, it doesn't sand off personality. Ask before editing their actual `~/.hermes/SOUL.md`. When R1 fails, or the user asks to simplify, run the **Simplify pass** below rather than hand-editing.

## Simplify pass (the R1 fix)

When R1 fails or the user asks to make a SOUL clearer or shorter, run the file through the
`writer` skill under tight guardrails. The goal is meaning-preserving, not
meaning-improving: tighten language and cut padding without loosening a single constraint.

1. **Load the `writer` skill** and its WRITING-STYLE.md for the kill-phrase list and
   plain-language rules. For clarity and leanness, pull `evaluate-content` (Sweep 1) and
   writer's `references/remove-chaff.md`. Those define the bar, don't invent a parallel one.
2. **Inventory the constraints FIRST, before rewriting.** Extract every hard rule, gate, and never-do into a checklist. Grep for `never`, `only`, `always`, `must`, `block`, `don't`, `NOT`. This list is the ground truth the rewrite must preserve.
3. **Rewrite prose, not structure.** Tighten language, unstack parentheticals, split run-ons,
   cut filler. For a comprehension miss (unexplained jargon, an ambiguous "this", assumed
   context), add the missing gloss or fact rather than cutting. Never reorder sections, drop
   one, merge two distinct rules, or soften a constraint. "never" stays "never".
4. **Verify against the inventory.** Re-extract the constraint list from the rewrite and diff it against step 2. Every rule present before must be present after. A drop rejects that edit, not the whole pass.

   Check greppable invariants rather than eyeballing. Count the tokens that must survive (item anchors, citation IDs, Pass/Fail lines, scoring numbers) with `grep -c` before and after, and confirm the counts match. A rewrite that silently drops a citation is what this step exists to catch. Report before/after char count and the constraint-count match.
5. **Diff for review, don't overwrite blind.** Show the user a diff, or write to a `.simplified` sibling, and ask before replacing their real SOUL.md. Never edit `~/.hermes/SOUL.md` (or a profile's) without approval.

## How Hermes loads SOUL.md (the mechanics the audit checks)

These are the facts M1-M3 test against. Source: Hermes docs (context-files, use-soul-with-hermes, personality), verified 2026-07.

- **Slot #1, injected verbatim.** SOUL.md is the agent's primary identity. It goes first in the system prompt and replaces the built-in default, with no wrapper text added. The content IS the identity, so sloppy content is the identity being sloppy.
- **Loaded ONLY from `HERMES_HOME/SOUL.md`** (`~/.hermes/SOUL.md`). Hermes never checks the working directory for it, so a repo-local `SOUL.md` does nothing. When someone says "I edited it and nothing changed," they usually edited the wrong file or didn't restart the session.
- **Truncation is head/tail, not tail-drop.** Files over `context_file_max_chars` (default 20,000, ~7k tokens) keep 70% head and 20% tail, with a marker replacing the middle 10%. The middle of a long SOUL is the first thing dropped, so front-load identity and hard constraints.

  Check the local override before scoring: `grep context_file_max_chars ~/.hermes/config.yaml`. One instance sets 80,000, which loads a 22KB SOUL whole. Score against the configured cap, and cite the 20K default only for portability.
- **Injection-scanned before inclusion.** If the file contains patterns like "ignore previous instructions", "do not tell the user", `cat .env`, hidden HTML comments, or invisible/bidi characters, the WHOLE file is blocked and Hermes falls back to the default identity. A SOUL that trips the scanner silently disables itself.
- **Empty = default.** An empty or whitespace-only SOUL.md means Hermes uses its built-in identity. The same happens under `skip_context_files` (subagents).
- **SOUL vs AGENTS vs /personality.** SOUL is durable voice and identity that follows you everywhere. AGENTS.md holds per-project conventions, paths, and commands. `/personality` is a temporary session overlay. Mixing project detail into SOUL is the single most common mistake the docs call out.

## Scorecard Format

```
# SOUL.md Audit
## Length: [N] chars ([under / over] the 20k truncation limit)
## Score: [X]/9

### ✅ Passing
- [item]: [what's good]

### ⚠️ Warnings (passes but fragile)
- [item]: [what's borderline]

### ❌ Failing
- [item]: [what's wrong + specific fix]

### Recommended Actions (priority order)
1. [highest-impact fix]
2. ...
```

## Scoring rules

- Be honest. A polished-but-unexamined operator template (the common case) usually scores 4-7/9: strong on stated values, weak on truncation-safety, redundancy, enforceability, and leanness.
- Don't inflate to be nice. An audit where everything passes is useless.
- Voice items (V1-V2) are judgment calls. A genuinely distinctive terse voice can pass V2 without worked examples when the terseness itself is the voice on display. Use judgment. Don't force examples onto a file whose whole point is brevity.
- When in doubt, fail and explain. Better to flag a non-issue than miss a rule stranded in the truncated middle.

## Gotchas

- **"It reads well" is not a pass.** The failure modes here (truncated middle, diluted restatement, unenforceable aspiration) are invisible to a human skim, because a human reads the whole file top to bottom and fills the gaps charitably. The model doesn't. Score against the mechanics, not the vibe.
- **Aspirational fiction is the signature SOUL.md failure.** Operator templates love lines like "make me notice," "create motion," "track my loop-closing rate across sessions." The model has no memory of your loop-closing rate and no way to make you notice. Flag these under P3: either wire them to a real tool, file, or tracked state, or cut them. Unenforceable rules train the model to treat the whole doc as vibes.
- **Redundancy hides as thoroughness.** Four sections that each say "be sharp, be direct, don't coddle, useful beats agreeable" feel rigorous, but they are one instruction spending four times the attention budget and pushing real constraints toward the truncated middle. That's a P2 fail, not diligence.
- **A closing restatement is optional, never required.** Repeating the 2-3 hard constraints at the very end is *allowed* (recency is real), but P1 does NOT score a file down for lacking one, and never demand the author add one. What P2 still fails is one idea smeared across the *body* in near-synonyms. Front-loading the hard rules at the top is the scored requirement; the end echo is a nicety, not an obligation.
- **A true research finding is not automatically a scored rule.** P1 rests on the U-shaped attention curve, where both the start and the end get high attention. The tempting inference is "so restate the bans at the end," scoring files down for skipping it.

  That inference was rejected. A SOUL loaded once per session gains little from a mechanical end-echo, and requiring one manufactures the body-smear P2 exists to catch. Cite recency as real, front-load the hard rules, leave the closing echo optional. Before turning any attention finding into a checklist item, ask whether it earns a requirement or only a permission.
- **Project detail in SOUL is an M1 fail even when well-written.** "Use pytest not unittest" is a great instruction in the wrong file. The fix is to move it to AGENTS.md, not delete it.
- **A file can pass every M/V/P item and still be unreadable.** Correct scope, safe truncation, clean scan, distinctive voice, no redundancy, all enforceable, and still a wall of nested parens and shouted caps twice as long as the job needs. R1 catches that.

  A section that's hard to understand is a bad section however correct its rule, because the model can't follow what it has to guess at. Fix a failing R1 with the Simplify pass: add the missing context for a comprehension miss, cut for a density miss. Never by dropping constraints.
- **Editing this skill's own rubric files needs the same discipline.** When you patch checklist.md or SKILL.md, preserve invariants exactly as the Simplify pass demands. After a rescale (/8 to /9), grep for stray old values and confirm the item-anchor count, arXiv IDs, and Pass/Fail line counts are unchanged.

  If a patch returns a "modified by sibling subagent" warning, re-read the file and confirm only your own edit landed before continuing. Those warnings have been false alarms, but re-reading is the only way to know.

## Skill source

Built 2026-07. Loading mechanics come from three Hermes doc pages:
`/docs/user-guide/features/context-files`, `/docs/guides/use-soul-with-hermes`, and
`/docs/user-guide/features/personality`.

P1-P3 come from skill-audit's `references/prompt-attention-research.md`, restated compactly in
`references/attention-basis.md`. R1 was added later from the same research, since shorter and
cleaner prompts derail less.

`references/template.md` is the target shape, adapted from a community "Anatomy of a SOUL.md"
infographic and corrected against the mechanics: Boundaries moved to top and end, a Defaults
block added per the docs' Identity/Style/Avoid/Defaults structure, and Memory reframed as
privacy policy rather than mechanism.

To refresh, re-read those three doc pages for changes to truncation ratios, the
HERMES_HOME-only rule, or the injection scanner, then re-check the arXiv findings.
