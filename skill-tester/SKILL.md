---
name: skill-tester
preloaded: true
description: "Test an interactive lesson or course skill by self-play: one agent plays instructor and student, capturing full transcripts, then publishes to Surge. Use for run lesson transcripts or QA the course end to end. For web-app QA use dogfood."

---

# skill-tester: self-play lesson transcripts to surge

Test an interactive course by RUNNING it, not reviewing it. Each lesson file is
"instructions to an AI on how to teach." A faithful test executes those instructions
against a simulated student and captures the whole conversation. Publish every transcript
raw so a human can read exactly how each lesson plays out and where it snags.

This is different from the QA skills you already have:
- `dogfood` / `adversarial-ux-test`, browser automation against a deployed web app.
- `synthetic-userstudies` + `interactive-lesson-design/references/synthetic-lesson-testing.md`
produce ranked FINDINGS plus a couple of highest-signal transcripts. NOT full raw runs.
- **skill-tester**: full turn-by-turn transcript of EVERY lesson, all published raw.

## When to run
After a lesson rewrite or new lessons, when the owner wants to SEE the lessons run rather
than read a findings memo. Run against the freshest source (pull origin, use a worktree;
local checkouts go stale).

## Step 1: Grab the freshest source
Pull the repo, add a worktree on the default branch, confirm the lesson count matches the
latest merged PR. Read `CLAUDE.md` / `LESSON-FORMAT.md` / the skill spec so the instructor
half follows the real teaching rules (e.g. "one step per message, STOP and wait, DO the
demo live, keep messages short").

## Variant: RAW blank-subagent self-play (no system prompt)
If the user asks that each lesson be run by "a blank/raw subagent with NO system prompt"
(the most faithful test, mirrors a Cursor paste where the model carries no SOUL), do NOT
use `delegate_task` (its subagents inherit the framework system prompt). Drive two direct
proxy model calls per lesson with `system=` OMITTED. Full method + the termination-regex
trap + the run-backgrounded pattern: `references/raw-blank-subagent-selfplay.md`; ready
runner: `scripts/run_selfplay.py`. Otherwise use the parallel delegate dispatch below.

## Step 2: Self-play dispatch (parallel, read-only)
Group lessons (e.g. by capability arc, ~4 each) and dispatch one read-only subagent per
group via `delegate_task`, toolsets `["terminal","file"]`, instructed NOT to edit anything
except its own output files. Each subagent, per lesson, writes a VERBATIM transcript where
it plays both roles:
- **INSTRUCTOR**: follow the lesson file exactly, one step per message, run/narrate the
  demo, use the lesson's actual prompts and ASCII visuals, STOP after each step.
- **STUDENT**: a CALIBRATED persona (see below). Reacts in good faith, sometimes hits a
  snag, asks a clarifier, or pastes a plausible result.

Per-lesson transcript format: a `# Lesson N: title` heading, a one-line claimed magic
moment, the turn-by-turn body with `**INSTRUCTOR:**` / `**STUDENT:**` labels covering the
WHOLE lesson, then a `### Where it snagged` tail (1-3 real friction bullets, or "clean run").
Label every file SYNTHETIC.

### Step 2 variant: RAW blank subagent (no system prompt) per lesson
`delegate_task` subagents carry the full SOUL/persona system prompt, so they do NOT
faithfully reproduce how a lesson runs when pasted into a bare Cursor/Claude chat.
When the owner asks for "a blank raw subagent with no system prompt" per lesson
(Eric did, June 2026, treat it as a HARD requirement), bypass delegate_task and
call the Messages API directly through the local proxy with NO `system` param
(an empty-string system is rejected with a 400). Instructor = blank model fed only
the pasted lesson file; student = separate blank model given its persona as the
FIRST USER message. Working runner: `scripts/run_selfplay.py`. Full why + the
false-stop termination gotcha + backgrounding: `references/raw-blank-subagent-selfplay.md`.

## Step 3: Calibrate the persona (the decision everything hinges on)
The most fragile beginner persona is a FALSE FLOOR, it over-drives fixes and patronizes
the real audience. State the REAL audience explicitly before running (for an AI course it's
typically a ChatGPT/Claude-literate PM: knows what a system prompt is, can install an app
and run a setup command). Assume competence. Keep skill-independent findings (silent-failure
bugs, missing-prerequisite fallbacks, overgeneralizations that lose a skeptic); discount
false-floor-only complaints. Detail: this pattern is shared with
`interactive-lesson-design/references/synthetic-lesson-testing.md`.

## Load this skill BEFORE you build the first page, not after (hard-won)
The dark-mode rule below is the #1 repeat miss: a session builds a surge report from memory,
defaults to dark mode, ships it, and Eric corrects it, the SAME rejection he already made on
the aps-testing-report. The rule lives in this skill precisely so you don't re-learn it by
getting corrected. So: the instant the task is "skill-test / QA a course AND publish to surge,"
read this SKILL.md FIRST, before writing any HTML. The warm-palette rule applies to ANY surge
artifact Eric receives from this work, the raw transcripts page AND a separate findings/
scorecard report, not just the transcripts page. There is no Eric-facing surge deploy that
should be dark mode; if you catch yourself hand-writing a `--bg:#0c0d10`-style dark `:root`,
stop and pull the warm tokens from `references/build-transcripts-page.md`.

## Step 4: Publish raw to surge
Build a page hosting ALL transcripts raw, collapsible per lesson, grouped by arc, with a
SYNTHETIC warning header. **Use Eric's visual identity (`~/.hermes/VISUAL-IDENTITY.md`), NOT
dark mode.** He explicitly rejected the dark aps-testing-report look, default to his warm
editorial palette (parchment `#f5f4ed`, EB Garamond serif headlines weight 500, terracotta
`#c96442` accent, General Sans body, JetBrains Mono code). `references/build-transcripts-page.md`
has the exact tokens; `scripts/build_transcripts.py` already ships with them. Deploy:
```
python3 build_transcripts.py
cp index.html 200.html
surge . <name>-transcripts.surge.sh
```
Verify with a real rendered screenshot (BrowserVision), confirm the parchment/serif look
landed in pixels, not just a DOM grep. Surge can 504 on a cold first hit, retry after a few
seconds.

## If asked to PR this into the PUBLIC skills repo (exiao/skills)
Sanitize first, the public mirror bans personal data. Strip before committing: the name
"Eric", personal surge URLs (`*.surge.sh`), the `VISUAL-IDENTITY.md` reference, specific
PR numbers / commit SHAs, and `/Users/...` paths. Ship a NEUTRAL default theme in the public
build script with a note to swap in your own `:root` tokens (the private copy keeps the warm
palette baked in). Public category names differ: it's `skills-meta` there too, but verify via
`skills_list`. Bump the README skill counts (category + total). Push as `exiao` via
`gh-as exiao`. Grep the whole skill dir for leaks before committing:
`grep -rniE "eric|surge\.sh|VISUAL-IDENTITY|/Users/|<project-names>"`.

## Pitfalls
- Local repo checkout is usually STALE. Always work from origin/<default> in a worktree.
- Read-only subagents get NO edit toolset beyond writing their own transcript files.
- Long URLs / code blocks force horizontal scroll on mobile, the build script sets
  `white-space:pre-wrap; word-break:break-word` and `overflow-wrap:anywhere` so they wrap.
- Don't cherry-pick. The whole point vs the findings-style test is that EVERY lesson ships
  raw, snags and all.
- The build script resolves `test-output/` relative to ITS OWN location, not the cwd. Run it
  from its directory, or put `test-output/` beside the script. Smoke-test artifacts get
  re-staged by `git add` even after `trash`, unstage with `git rm --cached` before commit.
- **Speaker turns must wrap CONSECUTIVE lines, not just the label line.** The renderer keeps a
  `turn_open` flag and `close_turn()` on the next heading/hr/speaker so a multi-line
  INSTRUCTOR/STUDENT block stays inside ONE bubble. The naive "wrap only the `**SPEAKER:**`
  line in a `<p class='turn'>`" version leaks follow-on lines out as top-level paragraphs
  a real fidelity bug gemini-code-assist caught on exiao/skills#158. Don't regress it.
- **read/write with `encoding="utf-8"`.** Transcripts carry smart quotes, emoji, and the
  full-width colon `：`; bare `read_text()`/`write_text()` throws on Windows CP1252.
- **The runtime copy and the public-repo copy of this script DRIFT.** When you fix review
  comments on one, port the identical fix to the other (and to `~/.hermes/skills`). Diff the
  three before declaring done; the public mirror lagged the runtime by two builds this session.

## Drift check: does the published page still match the SOURCE?
The transcripts are a DERIVED artifact (self-play of repo lessons, which were generated from
an upstream source like Notion). "Does the page match the source?" really means "are the repo
lessons still current with the source?" To check after the owner says they updated the source:
- Pull each source page (e.g. Notion via `NOTION_API_KEY`, page IDs often live in a repo
  helper script's `MAP`); dump plain text per lesson. Recursive Notion block fetch is SLOW
  (~2-3 min for 20 pages), run it backgrounded, don't inline-timeout.
- Compare `last_edited_time` per page against the lesson-generation date / merge date. Pages
  edited AFTER the lessons were generated are the drift set.
- Titles/structure usually still align; the drift is in DEMO specifics (example tools, exact
  prompts) and the voice spine. Report the drift set + per-lesson delta; the real fix is
  REGENERATE the changed repo lessons from current source, then re-run transcripts for those,
  then rebuild, not just re-running transcripts off stale lessons.

## Verify with a DETERMINISTIC audit, never the subagents' self-verdict
Self-play subagents reliably self-report "clean run" / "pauses handled silently" even when
you ask them to flag bugs, they graded their own homework every section this session. Their
verdict is NOT proof. After the transcripts land, run an independent programmatic audit:
- Walk every transcript, track the current speaker (`**INSTRUCTOR:**` / `**STUDENT:**`), and
  grep INSTRUCTOR-attributed lines for the failure pattern (e.g. a spoken `stop.`, a leaked
  director's-note phrase). Print line-anchored hits; zero hits across all 20 = verified.
- Filter benign matches (the word "stop" in ordinary English, "stops being a black box"
  or a worktree path that contains the string) so the audit doesn't false-positive.
- Then spot-confirm the POSITIVE change actually landed (e.g. grep the re-threaded voice line
  in the relevant transcripts), not just that the bug is absent.
This "subagent does the run, parent does the deterministic check" split is the whole point of
re-running skill-tester to confirm a fix, without the audit you've just produced 20 more
unverified files.

## Lesson-design smell to flag (interactive "instructions to an AI" courses)
A stage direction like `STOP` (telling the teaching AI to pause/wait) reads as the instructor
SHOUTING it at the student when a model follows the script literally, it leaks into spoken
output. The fix is never "fewer STOPs" (one per step is the correct pacing mechanism); it's
making the direction unmistakably silent. The phrasing that WORKED this session (verified by a
fresh self-play run + grep audit showing zero leaks across 20 lessons): a director's-note
blockquote `> 🎬 **Director's note (never say aloud):** <action>`, plus rewording the
rules-block line to "Pause and wait ... never say them (or the word 'stop') aloud." Apply it
with a deterministic transform script (regex over `^\*\*STOP\.\s*(.+?)\*\*$`) so all lessons
convert identically, then update the format guide (LESSON-FORMAT.md) so generated lessons
inherit the convention, then re-run + audit. Also re-thread any voice/theme SPINE the upstream
source carries (e.g. a recurring "there's no magic" line) into the lessons that dropped it
add it to the Name It / What Just Happened beat in each lesson's own voice; verify it survives
into the fresh transcripts. Don't over-cut: templated closings and the one-per-step pacing are
the scaffold a model needs, not bloat, only fix the genuine leak.

### Cold-open disorientation: lessons must ORIENT before they demo
A lesson that opens straight into "Watch this, I'm going to create real files", no overview,
no "here's what we're covering," no statement of which lesson this is, leaves the learner
lost. Eric pasted aps lesson 2 into Cursor and said "I copied the lesson and I have no idea
what it's doing" (June 2026). Root cause: the format guide's "No setup check, open cold on
the first real step" rule, plus the Magic Moment line living ABOVE "Instructions for Claude"
(it's a guide for the model, never spoken), so the model's literal first utterance is a
file-writing demo with zero framing.

The fix Eric asked for, as an explicit flow: (1) here's what we're covering today (overview),
(2) here's the bite-sized lesson, (3) the magic moment teased, (4) then the demo. Implement as
a **Step 0: Orient** block the instructor says BEFORE any demo, then waits: name the lesson
("Lesson N of M: <title>", with the day/arc), one-sentence "what we're covering," one-sentence
tease of the magic moment coming, then a "sound good?" hand-off. Add a CRITICAL RULES line:
"Open with Step 0 (orientation) BEFORE any demo. Never start by writing files."

Calibrate against the REFERENCE course before going heavier than it: check how
github.com/exiao/claude-code-course lessons actually open (e.g. `lessons/06-brainstorm-features.md`).
That course does NOT use a separate Step 0, but its Step 1 still avoids cold-demo
disorientation two ways the aps lessons missed: (a) it opens with a conversational TRANSITION
+ ORIENTATION ("Now that we've learned to plan, let's go big...") instead of "Watch this";
(b) it opens by ASKING the student something rather than immediately demoing. So there are two
valid fixes, Option A: match the reference (no Step 0; make Step 1 open with a transition and
an ask, not a demo); Option B: the explicit Step 0 overview ramp Eric described. B is more
structure than the reference does; surface the tradeoff and let the owner pick rather than
silently picking B. Whichever is chosen, apply it to ALL lessons and update LESSON-FORMAT.md
(replace the "open cold on the first real step" rule) so generated lessons inherit it, then
re-run + audit.
