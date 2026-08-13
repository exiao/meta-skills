# Trigger-eval harness pitfalls (run_eval.py / run_loop.py)

The Description-Optimization trigger eval (`scripts/run_eval.py`, also driven by
`run_loop.py`) probes whether a skill's description makes Claude auto-invoke it.
It writes a temporary probe skill, runs `claude -p` on each query, and watches the
stream-json for a `Skill`/`Read` tool_use matching the probe name. Two failure
modes make EVERY query read as not-triggered (uniform 0.00), which looks like a
broken skill but is really a broken harness.

## How to recognize a false negative (do this control FIRST)
If a trigger eval returns 0.00 across the board — including should-trigger
queries you're confident about — do NOT conclude the description is bad. Run a
control: point the SAME harness at a known-good, reliably-triggering skill (e.g.
`simplify`) with an obvious trigger query like "run /simplify on my recent
changes". If the control also scores 0.00, the harness is the problem, not your
skill. (Confirmed this way: `simplify` scored 0/2 on a dead-certain trigger.)

## Bug 1 — wrong directory (.claude/commands vs .claude/skills)
In current Claude Code (2.1.x), a file in `.claude/commands/<name>.md` registers
as a SLASH COMMAND (only fires when a user literally types `/name`) and lands in
the init event's `slash_commands[]` array. It NEVER enters the model's
auto-invokable `skills[]` list, so the model can't reach it via the `Skill` tool
and the detector can never see a trigger. Auto-invokable skills must live at
`.claude/skills/<name>/SKILL.md` (with a `name:` frontmatter field); those show
up in `skills[]`. The two mechanisms used to be one and got split.
- Proof: write the same probe to each location and inspect `head -1` of the
  stream-json init event — `commands/` → present in `slash_commands`, absent from
  `skills`; `skills/<name>/SKILL.md` → present in `skills`.
- Fix (already applied): the probe is registered once per eval run at
  `.claude/skills/<clean_name>/SKILL.md` by `registered_probe`, and removed when
  the worker pool drains. Registration is deliberately NOT per worker: with
  `--num-workers 10`, ten identically-described probes in one project let a
  worker invoke a sibling's name and score itself as not-triggered.

## Bug 2 — timeout too short for an agentic run
The probe runs a REAL `claude -p` agent, which needs ~15-30s just to make its
first tool decision, and far longer under parallel load. The old default
`--timeout 30` killed runs before the `Skill` call streamed, so even a correct
trigger read as false. A single isolated run that triggers in ~15s will still
score 0 in a `--num-workers 10` batch because contention pushes each process
past the deadline.
- Fix (already applied): default `--timeout` raised to 60 in both `run_eval.py`
  and `run_loop.py`. For a clean measurement of a few hard cases, run a small
  positives-only set at low concurrency (`--num-workers 2-3 --timeout 75`).

## Residual limitation (not a quick fix)
The detector waits for a live agentic run to reach its first tool call rather than
just capturing the routing decision, so batch pass-rates UNDERSTATE true triggering
under parallel load. When you need ground truth for a specific query, instrument a
single `claude -p` directly (write the probe to `.claude/skills/<name>/SKILL.md`,
run with `--include-partial-messages`, grep the stream for the `Skill` tool_use and
its `{"skill": "<name>"}` input). A direct run is the authoritative signal; the
batch score is a noisy lower bound.

## What a clean trigger looks like (direct instrumented run)
The model emits a `Skill` tool_use whose input is `{"skill": "<probe-name>", ...}`,
often preceded by text like "This is exactly what the <skill> is for." Seeing that
means the description works even if the batch harness scored the query as a miss.
