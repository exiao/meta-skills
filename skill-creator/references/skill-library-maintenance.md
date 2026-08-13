# Skill Library Maintenance

How to fold third-party research and session learnings back into the skill library.

## Incorporating External Research Into Existing Skills

When the user shares a link, thread, article, video, or pasted notes and says "incorporate this skill" or "update the skill library," treat it as a skill-maintenance task, not a summarization task.

1. Fetch the source with the domain-appropriate reader (`bird read` for X/Twitter, web search/fetch for web, video tools for video).
2. Extract durable, reusable operating principles. Ignore biographical fluff, engagement bait, and one-off anecdotes unless they encode a repeatable workflow.
3. Distribute each principle to the existing class-level skill that owns that concern. Do not dump everything into one convenient skill. Operational API/campaign mechanics go in operational skills; creative strategy goes in creative/copy/content skills; hooks go in hook skills; measurement rules go in analytics/paid-ads skills.
4. Prefer patching currently loaded skills first, then existing umbrellas. Add `references/` only when the detail is too bulky for SKILL.md or is source-like documentation future agents may need.
5. Tag source and date compactly, e.g. `(Source: @handle, May 2026)`, so later agents can distinguish observed advice from local convention.
6. The final reply should say exactly what changed and where, not re-summarize the whole source.
7. After patching, check the updated skill's description byte count (`echo -n "description text" | wc -c`). If it grew past 200 bytes, tighten it. Budget awareness matters for preloaded skills.

This fast incorporation path is for small-to-medium updates to existing skills. Use the full RED → GREEN → REFACTOR eval loop for creating new skills, large rewrites, or changes where quality can be meaningfully benchmarked.

**Pitfall, "consolidate" does not mean "delete to cut a count."** When a plan says "collapse N skills into 1" or "remove duplicates," that's a hypothesis, not a mandate. Before deleting or relocating any skill, check two things: (a) is it a vendored upstream copy (look for a `## Updating from upstream` / "vendored copy" section with a `cp`-into-this-exact-path refresh command)? and (b) are the apparent duplicates actually divergent on purpose (e.g. one transcription path forces `tiny.en --language en` for speed, another is the multilingual asset path, a third is a raw model card)? If either is true, deleting the file breaks upstream sync or destroys an intentional variant, the over-engineering trap of chasing a tidy number. The real problem is almost always **routing** (multiple skills competing to trigger, agent unsure which to load), not the files existing. Fix routing non-destructively: write ONE router/decision reference under the umbrella (a table of "reach for X when…") and a one-line cross-pointer from each divergent skill to the canonical one. Keep the files. State plainly in your reply that you chose non-destructive consolidation and why, and flag it if the original plan asked for deletion so the user can override. Physical deletion is a last resort reserved for true dead duplicates with no upstream link and no behavioral divergence.

**Pitfall, subagent partial completion:** When delegating multi-file skill patches to a subagent, it may timeout after applying some changes but not others (or applying the same change twice). Always diff the current state of every target file before applying your own changes. Look for: duplicated sections, half-applied patches, and files the subagent never reached. A 600s timeout on 4+ file patches is common.

**Pitfall, don't delegate multi-skill patches to a subagent.** When distributing principles across 3+ skills (each needing FilePatch + verification), subagents routinely timeout at 600s. Do the patches inline in the main context. The per-file grep/read/patch cycle is fast enough that delegation overhead exceeds the work itself.

**Pitfall, editing a SKILL.md that is inlined verbatim into a runtime prompt.** Some skills are not just read by an agent on demand; their SKILL.md text is concatenated verbatim into a system/user prompt by the harness (e.g. a CI eval shard whose system message is `evaluator_skill = load_skill("evaluator")` then embedded, or a compile prompt that inlines `compiler` + `analyst` SKILL.md). For these, the prose is exact code: paraphrasing a check, merging two rules, or "tightening" a sentence silently changes runtime behavior. Before restructuring such a file:
1. Grep the consuming codebase for how the skill is loaded (`load_*_skill`, `_load_skill_reference`, `build_*_system`, `build_*_prompt`) to learn (a) that it is inlined and (b) whether its `references/` are auto-inlined too. Many loaders inline ONLY SKILL.md and a hand-picked reference, NOT the whole `references/` dir, so "move detail to references/ to shrink SKILL.md" silently drops that detail from the model's context. Confirm the loader pulls a reference before relying on it as the new home; if it doesn't, defer the size fix to a separate PR that also fixes the loader rather than quietly regressing the prompt to win a line-count metric.
2. When you DO restructure (regroup sections, drop accretion markers like "(NEW)"), preserve every rule verbatim and PROVE it: diff distinctive phrases old-vs-new (`comm -23 <(grep -v '^#' OLD | sort -u) <(grep -v '^#' NEW | sort -u)` should show only intended changes) and count H2 sections old vs new. A regroup that changes wording is a behavior change masquerading as hygiene.

**Pitfall, oversized SKILL.md patch limits.** Some legacy umbrella skills exceed the skill manager's SKILL.md patch size limit. If `skill_manage(action='patch')` refuses because SKILL.md is over the limit, still capture the learning in that skill's `references/` directory with `write_file`, then patch a smaller active umbrella if one owns the operational procedure. Mention the missing SKILL.md pointer in the final reply so a later consolidation pass can shrink or index the large skill.

## Post-Session Skill Library Review

When the user asks to review the conversation and update the skill library, treat it as an active maintenance pass. Save a learning when the session produced a correction, a workaround, or a reusable technique. "Nothing to save" is a valid outcome; say it in one line and stop.

Pressure scenarios to check before deciding:
1. Did the user correct style, tone, format, verbosity, workflow order, or tool choice? Patch the skill that governs that task so the preference is embedded in the procedure, not only memory.
2. Did a new technique, workaround, source-analysis method, diagnostic sequence, or tool pattern emerge? Add it to the owning class-level skill.
3. Did a consulted skill prove incomplete, stale, too narrow, or missing a pointer to a useful reference? Patch that skill before replying.

Update order:
1. Patch a skill loaded or used in the session if it covers the learning.
2. Otherwise patch an existing class-level umbrella skill.
3. Add `references/`, `templates/`, or `scripts/` under an umbrella when the detail is too bulky or source-like for SKILL.md, and add a one-line pointer from SKILL.md.
4. Create a new skill only when no existing umbrella covers the class. New skills should be class-level, not tied to a PR, error string, link, feature codename, or one-off session artifact. In this environment, put new skills in category `internal` unless they clearly belong to an existing library category.

Favor the target library shape: rich class-level SKILL.md files with support directories for detail, not a long flat list of narrow session skills. Preserve YAML frontmatter integrity and source attribution. Final replies should state exactly what changed and where.

## Session Review Skill Maintenance

When the user asks to review the current conversation and update the skill library, be active by default. Scan for workflow corrections, style preferences, non-trivial fixes, tool quirks, and any skill that was loaded but proved incomplete. Patch the currently loaded skill first when it owns the lesson; otherwise patch an existing class-level umbrella. Prefer a concise SKILL.md pitfall or step for reusable guidance, and put session-specific transcripts, commands, or curation details in `references/` with a one-line pointer from SKILL.md. Avoid one-session-one-skill sprawl: create a new skill only when no existing umbrella covers the class, and make the new name class-level rather than tied to a PR, error string, or today's feature.

For repository cleanup sessions, capture the reusable operating rule, not the raw session log. Example: "runtime checkout stash apply left conflicts, generated state, and public/private skill split" belongs as a stash-curation pitfall under a git/skills-cleanup umbrella, while the exact file list belongs in a reference file if future agents need it.
