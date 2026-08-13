# RED phase for tool/CLI skills: the cold-subagent self-drivability test

The standard RED loop (`red-green-refactor-for-skills.md`) is written for
*behavioral-compliance* skills — you watch an agent rationalize under pressure,
then write counters. For a **skill that teaches a tool/CLI/API** the failure mode
is different: the question is not "does the agent comply" but "can the agent
figure out the tool AT ALL without the skill, and where does it stumble." Use a
cold delegated subagent as the failing test.

## The technique

Delegate a subagent with the **bare minimum** and nothing else:
- the exact invocation path (binary path, or import line)
- the minimal config needed to connect (env vars, base URL, key)
- a realistic end-to-end task a real user would ask
- an explicit instruction: "this is ALL the docs you get; figure it out yourself"
- toolset limited to what's needed to run it (e.g. just the terminal toolset)

Then read its report for three things:
1. **The command sequence it ran** — did it discover the intended flow on its own?
2. **The answer quality** — did it reach the right outcome from the tool's output?
3. **The honest "where did I get stuck"** — this is the spec for what the skill
   must add. Ask for it explicitly in the goal.

## Why this is the right RED test for tool skills

- A self-documenting tool can make the baseline **already good**. That is the
  most important RED finding: if a cold agent drives the tool correctly and
  reaches the right answer, the skill's job is NOT "teach the commands" — it is
  narrow (add judgment, ordering, trust-calibration, which-surface-when). Writing
  a command-reference skill on top of a self-documenting tool is wasted bytes.
- The subagent's "where it fell short" doubles as a **bug report on the tool**,
  not just the skill. In practice the cold run surfaces real product gaps the
  skill should not paper over: endpoints that 500 on empty data, `--help` text
  that over-promises vs the actual payload, internal inconsistencies (e.g. an
  eval "PASS" verdict that contradicts a contradiction-count shown elsewhere).
  Fix those in the tool before building the skill — a skill that documents around
  a broken endpoint rots fast.
- It is a genuine integration test of the seam (CLI → auth → server → output)
  that unit mocks cannot give you. A cold agent exercises real arg-parsing, real
  error/empty states, real exit codes, and real breadcrumb-following.

## Pitfall: give the cold subagent the RIGHT toolset name, or the test silently lies

The whole RED/GREEN test depends on the subagent actually invoking the CLI. If you delegate with the wrong toolset name, the subagent can't run shell commands, falls back to whatever it CAN do (reading local repo files, cached corpora, fixtures), and writes a confident report that never touched the live tool. Its command "sequence" is fabricated-by-substitution and the comparison is worthless — you won't notice unless you read the tool_trace and see `read_file`/`search_files` where `terminal` calls should be.

For Hermes `delegate_task`/`TaskDelegate`, the shell toolset is **`terminal`**, not `ShellExec` (the function name) and not `shell`/`bash`. Pass `toolsets=["terminal","file"]` (add `web`/`browser` only if the task needs them). After the runs land, sanity-check each subagent's tool_trace: if a "ran the CLI live" task shows zero `terminal` calls, the toolset was wrong — rerun, don't trust the output. Also remind the subagent that env vars don't persist across separate terminal calls, so it must prefix `export KEY=... &&` on every command (or the live calls fail auth and it again falls back to disk).

## Setup notes

- Stand up the real backend first (live server + real auth), not a mock — the
  point is to test what a user actually hits. If the backend has a local-harness
  quirk that blocks some endpoints, neutralize it for the test (e.g. pre-bind the
  correct package before the shadowing import) so the subagent sees the
  prod-equivalent surface; otherwise it reports tool bugs that are really harness
  artifacts.
- Seed representative data with the signal you want tested present (e.g. a
  contradicted-claims count, a partial-coverage run, a thin vs deep run) so the
  judgment the skill will teach is actually exercisable.
- The cold run is cheap relative to its value: one delegated subagent, a few
  minutes, and you get the skill's spec + a tool bug list in one pass.

## Pitfall: the subagent MUST actually be able to run the tool — verify the toolset

The single most expensive way to waste a whole RED or GREEN iteration is to
delegate the subagent with a toolset that does not include the one it needs to
invoke the tool. Invalid toolset names are **silently ignored and fall back to
the defaults** (file/web only), so a subagent told to "run the CLI live" with a
mistyped toolset will instead quietly read whatever cached/on-disk data it can
find, write a plausible report grounded in that, and never touch the live tool.
The report looks complete; the run is worthless for comparing skill-vs-baseline
on the real seam.

- Use the exact terminal toolset name your environment expects for shell
  execution (the name that actually maps to running commands), not a guessed or
  capitalized variant. A wrong name does not error — it degrades.
- Tell the subagent explicitly "you MUST actually run `<tool>` via the terminal;
  do not substitute local files," and have it report the **exact commands it
  executed**. If the report shows file-read/search tools where you expected
  terminal calls, the toolset was wrong — discard that iteration and rerun.
- A tell that this happened: the subagent's summary contains an honest disclaimer
  like "this environment exposed only file tools, so I grounded the answer in the
  local cache instead of invoking the tool." That is a failed live run, not a
  result; do not score it.

## What you do with the result

- Self-drivable + right answer → write a **thin** skill: which surface for which
  question, trust-first ordering, pitfalls the agent missed. Not a command list.
- Got stuck on a real tool gap → file/fix the tool gap; don't encode "work around
  the broken thing" as a skill step (it becomes a stale constraint when fixed).
- The verbatim "next" breadcrumbs the agent followed tell you which paths already
  self-document well (skip them in the skill) vs which it discovered only by
  trial (reinforce those).
- When multiple GREEN-run agents independently reach for the same
  helper/file/command you didn't mention (e.g. all of them discover a tier-map
  index file on their own), that convergence is a signal to promote it to a lead
  instruction in the skill — it carries real weight and is currently undocumented.
