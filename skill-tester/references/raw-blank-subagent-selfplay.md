# Raw blank-subagent self-play (no system prompt)

When the user asks that each lesson be run by "a blank raw subagent with no system
prompt" (the most FAITHFUL test — it mirrors how the lesson actually behaves when
pasted into Cursor, where the model carries no special SOUL/persona), do NOT use
`delegate_task` for the instructor. delegate_task subagents inherit the framework
system prompt; that is not a blank model. Instead drive two direct model calls per
lesson through the local Anthropic proxy.

## Key facts
- Proxy: `anthropic.Anthropic(base_url="http://127.0.0.1:18801", api_key="proxy")`.
  Health: `curl -s -o /dev/null -w "%{http_code}" http://localhost:18801/health` → 200.
- "No system prompt" means **OMIT the `system=` param entirely.** Passing `system=""`
  is REJECTED: `400 system: text content blocks must be non-empty`. Just leave it out.
- Model: read `model.default` from `~/.hermes/config.yaml` (e.g. `claude-opus-4-8`).
- The INSTRUCTOR is a blank model fed the lesson file as a first user message, framed
  exactly as a Cursor paste ("the following is a lesson file the user pasted, teach it
  one step per message…"). The STUDENT is a SEPARATE blank model given the persona as
  its FIRST USER message (not a system prompt), then the instructor's turns relayed in.
- Loop instructor↔student for ~9-10 turns; bump to 10 when lessons have a Step 0
  orientation beat (it adds one exchange before the first demo).

## The termination-regex trap (cost me a re-run this session)
A naive break on `"what just happened"` fires on a MID-lesson aside like "Notice what
just happened" and truncates the transcript to 1-2 turns. Match only the lesson's real
CLOSING beat: `re.search(r"🎉|share prompt|what next\?|you've completed|that completes",
instr.lower())`. Verify after the run that transcripts are full length (~6-12k chars),
not 1.5k — a cluster of tiny files means the break regex is too loose.

## Run it backgrounded, poll for files
A 20-lesson × ~10-turn × 2-call run far exceeds the 60s shell cap and even a single
inline lesson does. Launch with `terminal(background=true, notify_on_complete=true)`,
redirect to a log, then poll `find test-output -name '*.md' | wc -l`. Use `python3 -u`
so the log flushes. A silent empty log + dead process right after launch is usually a
transient proxy blip — re-verify the proxy with a 1-token call and relaunch; it isn't
a code bug.

## Runner script
A ready-to-adapt runner lives at `scripts/run_selfplay.py` (edit LESSONS path, SECTIONS
map, persona). It writes `test-output/<section>/<slug>.md` for `build_transcripts.py`.

## Deterministic audit after the run (don't trust the models' self-verdict)
- Step 0 present per transcript: `grep -ic "of 20\|what we're covering\|magic moment coming"`.
- STOP leak (instructor speaking a stage direction): grep INSTRUCTOR lines for `\bstop\b`,
  then filter benign English ("stops being", "stop overestimating", "stop re-explaining").
- Spot-confirm the POSITIVE change landed (e.g. lesson 2 shows the STUDENT doing the model
  swap, not the instructor "swapping its own model" — a model cannot change its own model
  mid-session; any transcript where the instructor claims to is a lesson-design bug to fix
  in the source, not the transcript).
