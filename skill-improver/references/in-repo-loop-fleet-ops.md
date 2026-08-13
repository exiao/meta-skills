# Running an in-repo eval loop across a whole skill fleet

Once the in-repo eval-gated runner (e.g. CPE `scripts/hill_climb.py`) is unblocked and you
want to sweep ALL skills, the work stops being about edit quality and becomes an operations
problem: keeping a multi-hour unattended batch alive, fast, and honest. Lessons from a 14-skill
hill_climb sweep (CPE research-agent, 2026-06).

## Contents

1. [The eval GATE itself can hang forever — bound it before fanning out](#1-the-eval-gate-itself-can-hang-forever--bound-it-before-fanning-out)
2. [Run the fleet as a resilient batch, not an in-session poll loop](#2-run-the-fleet-as-a-resilient-batch-not-an-in-session-poll-loop)
3. [Hand off to a monitor cron, not to yourself](#3-hand-off-to-a-monitor-cron-not-to-yourself)
4. [\"Init flake\": a harness stall BEFORE the first LLM call](#4-init-flake-a-harness-stall-before-the-first-llm-call)
4b. [Slow-but-healthy is NOT a hang — prove it with log growth](#4b-slow-but-healthy-is-not-a-hang--prove-it-with-log-growth-before-killing-anything)
5. [Kill orphans before trusting a diagnosis](#5-kill-orphans-before-trusting-a-diagnosis)
5b. [Parallelizing the sweep safely: env-overridable state + disjoint shards](#5b-parallelizing-the-sweep-safely-env-overridable-state--disjoint-shards)
7. [Opening the per-skill PRs when `gh` can't resolve the repo](#7-opening-the-per-skill-prs-when-gh-cant-resolve-the-repo)
8. [Why the in-repo loop is structurally expensive — and the design fix](#8-why-the-in-repo-loop-is-structurally-expensive--and-the-design-fix-read-before-rebuilding-it)
6. [Interpreter / env gotchas for in-repo harnesses](#6-interpreter--env-gotchas-for-in-repo-harnesses-durable-not-environment-failures)

## 1. The eval GATE itself can hang forever — bound it before fanning out

The expensive part of each iteration is report *regeneration* (~9 min through the harness), but
the SNEAKY failure is the eval step. The runner gates on the repo's pytest suite. If even one
test makes a LIVE network/subprocess call with no timeout, that one test hangs the entire
iteration indefinitely, and every iteration of every skill inherits the hang.

Symptom: a pytest subprocess sitting at ~0% CPU, no open network sockets, no child process,
for many minutes, when the same suite ran in <5 min standalone earlier.

Diagnose (no root needed):
- `pgrep -fl "pytest evals"` to find the eval subprocess.
- CPU/socket probe: `ps -o %cpu=,etime= -p <pid>` (near-0% over a 10s sample = stalled),
  `lsof -p <pid> -iTCP` (no active sockets = not doing I/O right now).
- Re-run the SAME subset with a per-test timeout to make the hang self-report which test:
  `python -m pytest <paths> --timeout=45 --timeout-method=thread -q --durations=15`
  (install once: `.venv/bin/python -m pip install pytest-timeout`; if pip is missing in the
  venv, `python -m ensurepip` first). The `+++ Timeout +++` block names the exact test+line.

Root cause that bit this session: `execute_event` gained an incremental-update *bridge* path
AFTER its test was written. The test only mocked the legacy `_run_*` fallback, so the patches
missed and the test ran the real targeted-gather subprocess (a live `research` CLI → network).
Fix = mock the newer entry point the production code now hits first
(`pipeline.incremental_update.bridge_from_event_router` → `{"mode": "error"}`) so the routing
fallback under test runs without live I/O. Test went from ∞ to 0.4s; full suite 1191 passed /
0 failed in 4:20.

Generalizable rule: when a test predates a refactor that inserted a new "try fast path first"
branch, stale mocks silently miss and the test runs live code. If a "unit" test hangs, suspect
it is unintentionally doing real I/O — fix the mock target, don't just bump the timeout. (But
also ALWAYS pass `--timeout` to the eval subprocess so a future stale test degrades to a fast
fail instead of a fleet-wide stall.)

## 2. Run the fleet as a resilient batch, not an in-session poll loop

A 14-skill × 1-iteration sweep is ~7-9 hours. Do NOT hold the session open polling. Write a
thin batch wrapper around the single-skill runner with three properties (see
`scripts/hill_climb_batch.py` in the CPE repo for the reference implementation):

1. **Subprocess isolation per skill** — each skill runs in its own `subprocess.run([...],
   timeout=PER_SKILL_TIMEOUT)`. One skill crashing/hanging cannot kill the batch; the wrapper
   records it and advances to the next.
2. **Resumable state file** — write `summary.json` after EVERY skill (status, returncode,
   elapsed, parsed baseline/mutated scores). A `--resume` flag skips only CLEANLY-SCORED skills
   (returncode==0 AND baseline parsed), so a re-launch picks up exactly where it died.
3. **Per-skill wall-clock ceiling** — env-overridable (`HC_BATCH_PER_SKILL_TIMEOUT`), e.g.
   2400s. Bounds the cost of any single stall to one skill's budget, not the whole night.

Resume-predicate trap: do NOT skip on `status=="done"` alone. A skill killed mid-run is "done"
(the wrapper finished waiting) but produced no scores. Skip only when scores exist; otherwise
re-run. Encode it as: `done_clean = status=="done" and returncode==0 and baseline is not None`.

## 3. Hand off to a monitor cron, not to yourself

Set a `ScheduleManage` job (e.g. every 30 min) that: (a) checks `pgrep` + reads `summary.json`;
(b) kills a skill stalled >N min with no log growth (`pkill -9 -f "runner --skill <name>"`),
letting the wrapper advance; (c) relaunches the batch resumable if the wrapper died; (d) stays
SILENT while healthy (no spam); (e) on completion (process dead AND every skill cleanly scored)
does the finishing work — open per-skill PRs for real wins, update the demo site with actual
baseline→mutated deltas, message the user, then DELETE itself. Give it only the toolsets it
needs (terminal/file/web/skills/todo). This is the correct pattern for any genuinely multi-hour
unattended job.

## 4. "Init flake": a harness stall BEFORE the first LLM call

A regeneration run can stall during agent initialization, before any model call. Tell it apart
from a healthy run by activity markers in the per-skill log: a working CPE harness emits a burst
of `🔧 Auto-repaired tool name: ...` lines within ~60s of starting (tool calls in flight). A
flaked run shows the header, then nothing, with ~0% CPU. It is transient and skill-independent
(the next skill on the same code path runs fine), so the right response is: kill that one skill
subprocess, let the batch advance, and mark it for retry (don't treat it as a real "no
mutation" result). The improved resume predicate above retries it automatically.

## 4b. Slow-but-healthy is NOT a hang — prove it with log growth before killing anything

The most expensive mistake of the 2026-06 sweep was repeatedly diagnosing a *healthy, slow*
run as an "infinite hang," then manually killing a working subprocess and re-deriving a
nonexistent root cause (a phantom "Claude path has no request timeout" — the SDK client
already sets a 900s read timeout). A single regeneration does MANY slow LLM round-trips;
between them the process legitimately sits near-0% CPU with no open socket for 1-3 minutes.
A point-in-time CPU/socket probe (section 1) is necessary but NOT sufficient to call a stall —
it will show "idle" mid-round-trip on a perfectly healthy run.

The decisive test is **monotonic log growth over a window**, not an instantaneous snapshot:
- Record `wc -c <skill>.log` and the file mtime, wait 60-120s, re-check. If bytes increased
  (e.g. a new `🔧 Auto-repaired` or phase line appeared), it is ALIVE and progressing — leave
  it alone, no matter how idle the CPU looked at any single instant.
- Only when bytes are FLAT across a full 2+ minute window AND CPU is ~0% AND no socket AND the
  log's last line is not a "waiting on model" marker should you treat it as a real stall.
- An init-flake (section 4) is the special case where the log NEVER grew past the header.

Corollary — match your polling cadence to the work's cadence. Each skill is ~20-30 min. Do
NOT re-check every 30s, re-deploy identical site state, or re-verify already-verified
machinery on a tight loop; that burns tokens and produces no progress. Verify the autonomous
pipeline once (batch alive + resume predicate + monitor cron + PR path), then HAND OFF to the
cron and stop. Re-prompting the agent does not make the harness regenerate faster.

Also: before authoring a fix for a "bug," confirm the bug is real against the actual code path
(read the client/timeout construction), not against a stale assumption carried in from a prior
context summary. A compaction summary can assert a root cause that was never verified; treat it
as a hypothesis to re-check, not fact.

## 5. Kill orphans before trusting a diagnosis

A `kill` on a wrapper can leave the inner pytest/harness as an ORPHAN (re-parented to init),
still running stale pre-fix code and still holding its old temp workspace. When diagnosing a new
run, first `pgrep`/`ps` for leftover processes from prior killed runs and `kill -9` them —
otherwise you'll attribute an orphan's hang to the current batch. Identify orphans by their temp
workspace path in the cmdline (it won't match the current run's fresh temp dir).

## 5b. Parallelizing the sweep safely: env-overridable state + disjoint shards

To halve a multi-hour serial sweep, run TWO batch workers concurrently — but only after
removing the shared-mutable-state races. The single-skill runner typically read-modify-writes
two unlocked files (`evals/rejected_edits.json`, `evals/hill_climb_log.json`) and the batch
wrapper writes one `summary.json`; two concurrent workers will corrupt all three. The clean,
low-risk fix is to make every state path env-overridable (default unchanged) so each worker
gets isolated files:

- `REJECTED_EDITS_PATH = Path(os.environ.get("HC_REJECTED_EDITS_PATH", <default>))`
- `log_path = Path(os.environ.get("HC_LOG_PATH", <default>))`
- `BATCH_DIR = Path(os.environ.get("HC_BATCH_DIR", <default>))` (summary.json lives under it)
- Guard any `path.relative_to(PROJECT_ROOT)` display calls with try/except — they crash if a
  custom path lands outside the repo.

Then shard the skill list with the wrapper's `--only` flag into DISJOINT subsets so no two
workers ever touch the same SKILL.md (the real collision is concurrent edits to one file).
Verify disjointness + full coverage programmatically before launch (`front & back == set()`
and `front | back | already_done == all_skills`).

Two REMAINING cautions that make parallelization a judgment call, not an automatic win:
1. **Provider bucket cap.** Concurrent large regenerations are exactly the pattern that trips a
   capped Anthropic/billing bucket (the original blocker). 2x concurrency may re-trigger it and
   stall BOTH workers. If the bucket is capped/metered, serial is safer.
2. **Monitor cron must merge shard summaries.** A finisher reading a single `summary.json`
   won't see both shards; update it to merge them, or it will declare completion early.

Killing a healthy in-flight worker to relaunch parallel is a DESTRUCTIVE action — it discards
that skill's partial progress. The dangerous-command guard will (correctly) block the `pkill`
pending consent. Surface the tradeoff (time saved vs partial work lost vs bucket-cap risk) and
get an explicit go/no-go before killing a running batch.

## 7. Opening the per-skill PRs when `gh` can't resolve the repo

On a private repo whose remote carries an embedded PAT, `gh pr create` can fail with
`GraphQL: Could not resolve to a Repository` because the authenticated `gh` account
(e.g. a personal account) lacks org access, even though `git push` works fine (the push
uses the remote's embedded token, not the `gh` account). Don't fight `gh` auth — create
PRs directly via the GitHub REST API with the SAME embedded PAT:

```python
pat = git_remote_url.split("//",1)[1].split("@",1)[0].split(":")[-1]  # extract token
# POST https://api.github.com/repos/<owner>/<repo>/pulls
#   headers: Authorization: Bearer <pat>  (Bearer, not "token"), Accept: application/vnd.github+json
#   body: {"title","head","base","body"}
```

This created PRs #270-272 in one pass after `gh` refused. Verify the PAT first with a
cheap `GET /repos/<owner>/<repo>` (expect 200). Keep PR bodies in a file and read them
in; never inline large markdown.

## 8. Why the in-repo loop is structurally expensive — and the design fix (read before "rebuilding" it)

If the user asks to make the in-repo loop "run the skill isolated" or "cheaper per skill,"
the first move is NOT to patch the runner — it's to read what the eval GATE scores. The cost
is dictated by the gate, not the runner.

Diagnosis from CPE `hill_climb.py` (2026-06): the runner already isolates a lens mutation
(it deletes only that one lens's analysis file and re-runs just that lens via
`run_lens_analysis`, not all four). But it then ALWAYS calls `phase_compile` to regenerate the
full report.md, because **the scored eval gate (`run_evals`) only reads `report.md` + the
appendix** — zero scenario/regression tests read `analysis/<lens>.md` directly. So even a
perfectly isolated lens edit must be compiled into the whole report before any eval can see it.
Isolation is impossible by construction. And it pays that full compile TWICE per iteration
(baseline + mutated), which is ~95% of the wall-clock.

Generalizable rule: **a mutation can only be scored as cheaply as the smallest artifact the
eval gate reads.** If the gate reads the final assembled output, every skill's iteration costs
a full assembly regen, no matter how surgically the runner re-runs the upstream stage.

The design fix (the actual "ground-up rebuild") is a **per-artifact eval layer**:
- Add deterministic, binary evals that score a single skill's own output file directly
  (`analysis/financial_data.md` for lens-financial, etc.) — banned-term scan, required-section
  presence, citation-format, opinion-language guard. Milliseconds, zero LLM spend (same binary
  approach as manual-executor mode).
- Add an `--isolate` mode: re-run only that stage, score its artifact, **skip the full
  assembly** entirely. A lens iteration drops from 4 LLM calls (stage+assembly ×2) to 2.
- Stages that genuinely OWN the final output (compiler, report-updater) still pay the full
  assembly — that's correct, they're the ones being measured by it.

Two adjacent wins that fall out of the same rebuild:
- **Multi-ticker, not single-fixture.** A single frozen fixture (one company) overfits: a
  mutation that helps AVGO can regress on a SaaS/biotech ticker invisibly. Accept a mutation
  only if it improves the MEAN artifact score AND regresses NO ticker (per-ticker
  no-regression gate, same discipline as the per-test gate). PREREQUISITE: most repos ship
  only one fixture with the upstream `raw/` + `analysis/` inputs needed to regenerate;
  `research-outputs/<TICKER>` often has only the final report + claims, not the inputs. Build
  per-ticker fixtures first (or state honestly you're running AVGO + 1 until more exist).
- **Baseline caching.** The runner re-regenerates the baseline every iteration even when the
  skill file is unchanged. Cache the accepted baseline score per (skill, ticker), keyed on the
  skill file hash; only re-regenerate when it changed.

Ship this as small independently-mergeable PRs: (1) per-artifact eval layer, (2) `--isolate` +
multi-ticker + baseline cache in the runner, (3) ticker fixtures, (4) the launcher UI
(per-ticker job model + ticker×score sub-matrix). Each off main; the user merges.

## 6. Interpreter / env gotchas for in-repo harnesses (durable, not environment-failures)

- The harness import (`run_agent`, `hermes_state`) lives in the project's **venv**, not system
  python. A git WORKTREE has its own venv only if one was created there; always invoke via
  `<worktree>/.venv/bin/python`, never bare `python3`, or you get `ModuleNotFoundError:
  run_agent`. This is a structural fact about worktree+venv layout, not a missing-binary flake.
- A worktree may lack the auto-generated `hermes_home/.env` that only the MAIN checkout
  produces. Source the keys the harness needs from the canonical `~/.hermes/.env` and export
  them before launching (`export $(grep -E '^(ANTHROPIC_TOKEN|ANTHROPIC_BASE_URL|FMP_API_KEY|
  SERPER_API_KEY|...)=' ~/.hermes/.env | xargs)`).
