# Inline Patch Safety: Verify Every Skill Edit With a Readback

When patching skill SKILL.md / reference files inline (the fast "incorporate third-party research" path), the patch tool can silently damage content adjacent to your intended edit. This is distinct from the subagent-timeout pitfalls already documented in the main SKILL.md — it happens in the main context, on a single clean patch, and produces a file that looks fine unless you read it back.

## Failure modes observed (multi-skill update session, June 2026)

Three sequential single-file patches into one skill; two of three misfired:

1. **Adjacent-line deletion.** A `replace` patch whose `old_string` was just a heading (`## Step 2b: ...`) plus a sentinel that did not exist in the file removed a real body line that followed the heading ("Recreate before you recruit..."). The patch reported success. The clipped line was only noticed on readback.
2. **Pointer overwrite.** Inserting a new section immediately above an existing `> **Load on-demand:** ...` pointer consumed the pointer line, which then had to be manually restored with a second patch.

Both edits returned `success: true`. Neither error surfaced in the diff preview alone — the diff showed what was *added*, not what was *quietly dropped* around the anchor.

## The rule

After every skill patch, do a targeted readback before moving on:

1. **Anchor on a unique string, never a generic heading.** `## Step 2b` or `### Reddit Playbook` repeat or sit next to content lines. Use a full, unique sentence fragment from the exact spot as `old_string`. Never include a sentinel/placeholder line in `old_string` that isn't verbatim in the file — a non-matching multi-line `old_string` is how the tool grabs the wrong span.
2. **Grep the file for the lines that should still be there**, not just the line you added. After inserting section X above pointer Y, `search_files` for Y and confirm it survived. After replacing a heading block, confirm the body lines under that heading are intact.
3. **Read the surrounding 3-5 lines** (`search_files` with context) of every edit site. The diff tells you what changed; the readback tells you what *else* changed.
4. **Prefer the smallest possible `old_string`** — one unique sentence — and let the surrounding text stay untouched, rather than a large multi-paragraph span that's easy to mis-anchor.

## Why this matters more for skills than code

Skill files have no tests and no CI. A clipped line in a SKILL.md degrades every future invocation silently — there's no compiler, no failing assertion, no red. The readback IS the test. Budget one grep/read per edit site; it's cheap insurance against shipping a half-deleted procedure.
