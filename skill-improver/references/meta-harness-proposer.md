# Meta-Harness Proposer (full-trace, filesystem-browsing edit proposal)

GEPA's reflection step (6a/6a.5) is *compressed*: the optimizer sees the input, the final output, the names of failed evals, and a one-line self-diagnosis. It never sees WHERE in the run the skill went wrong. Meta-Harness (Lee et al. 2026, arxiv 2603.28052) shows that this aggressive feedback compression is exactly what makes text optimizers underperform on harness/skill code. Their fix: give the proposer **filesystem access to the source, training/selector scores, and full training execution traces of prior candidates**, and let it browse that evidence agentically before proposing a change. Held-out validation evidence stays outside this browsing context and is used only by the accept/reject gate.

This reference defines how skill-improver implements that. It REPLACES the compressed 6a→6c summary path with a trace-grounded proposer. SKILL.md step 6a/6c point here.

---

## what "execution trace" means

The full transcript of one run of the skill on one input, captured verbatim, not summarized:

- every tool call (name, full arguments, full result/error)
- every intermediate reasoning/assistant turn
- retries, fallbacks, and the order they happened in
- the final output
- the eval verdicts for that run (per-eval pass/fail + the grader's reason)

A summary throws away the one thing the optimizer needs: the *step where the run diverged*. "Failed the accuracy eval" tells you the destination; the trace tells you the wrong turn.

**Redact secrets and sensitive data before persisting.** Tool arguments and results are written verbatim and retained for cross-candidate comparison, so a skill that uses authenticated tools, private files, or customer data would otherwise leak credentials/PII into the delivered optimization directory. Before writing a trace, run tool arguments and results through a redactor: mask anything matching known secret shapes (API keys, tokens, `Authorization`/`Cookie` headers, passwords, connection strings) and any caller-declared sensitive fields, replacing the value with `[REDACTED:<kind>]`. Prefer an allowlist of fields to persist for known-sensitive tools over a denylist. The divergence-relevant structure (which tool, success/failure, error class) is preserved; only the sensitive *values* are masked.

---

## the trace archive (filesystem the proposer browses)

Every **training/selector** run writes a trace file. Traces are organized by candidate so the proposer can read across the whole train-side search history, not just this round. Validation run traces are never exposed to the proposer; if they are captured for debugging, keep them outside this archive and never include them in proposer context:

```
autoresearch-[skill-name]/
└── traces/
    ├── cand_0/                      # baseline candidate
    │   ├── run_input1_r1.md         # one file per (input, run)
    │   ├── run_input1_r2.md
    │   └── ...
    ├── cand_3/                      # a kept mutation
    │   └── ...
    └── cand_7/                      # a kept merge
        └── ...
```

Each `run_*.md` file:

```markdown
# trace: cand_3 / input_1 / run 2
## eval verdicts
- accuracy: FAIL (grader: "claimed AAPL up 1.2% but tool returned -0.4%")
- legibility: PASS

## execution
[turn 1 assistant] I'll fetch the quote first.
[tool_call bloom_info {"ticker":"AAPL"}]
[tool_result {"price":187.4,"change_pct":-0.4, ...}]
[turn 2 assistant] AAPL is up 1.2% today...     ← divergence: misread change_pct sign
[final output] AAPL: $187.42 (+1.2%) ...
```

Mark the divergence line when the self-diagnosis or grader reason localizes it; if not, leave the raw trace and let the proposer find it.

**Retention:** keep traces for every candidate currently in `pool.json` plus the last 3 rounds' discarded candidates. Prune older discarded-candidate traces (they rarely inform new proposals and the directory grows fast). Never prune a pool member's traces; the proposer is allowed to compare a regression against the exact run where an ancestor got it right.

---

## the agentic proposer (replaces the 6a summary prompt)

Instead of pre-digesting failures into a summary and handing the optimizer a paragraph, give the **optimizer model** read access only to a validation-redacted proposer view and let it investigate. The proposer runs as a short agentic loop with file-read tools scoped to a directory such as `autoresearch-[skill-name]/proposer_view/`, not to the raw experiment root. Build that view from train-side candidate sources, train/selector scores, train traces, and rejected-edit history; exclude raw `results.json`, validation traces, validation grader reasons, and any per-validation-case failure details.

> "You are improving a skill. You have read access to this run's `proposer_view/` directory:
> - `[user-chosen-name].md` and `cand_<id>.md` — the source of every candidate
> - `score_matrix.json` and `proposer_context.json` — train/selector per-task scores, lineage, and keep/discard history with validation details redacted
> - `traces/cand_<id>/run_*.md` — the FULL execution trace of every training/selector run, including tool calls, intermediate reasoning, and the exact step where each failing run diverged
> - `rejected_edits.json` — edits already tried and rejected (do not repeat)
>
> You may use validation only as an opaque accept/reject signal already reflected in keep/discard status. Do not read validation outputs, validation traces, validation grader reasons, or per-validation-case failures; if a file contains those details, it is outside your context.
>
> Investigate before proposing. Read the traces of the failing runs on the current parent (`cand_<sampled_id>`, where `sampled_id` is the candidate id returned by frontier sampling, not a child's `parent_id` lineage field). Find the exact step where each run went wrong, not just that it failed. When useful, compare against a trace where an ancestor candidate got the same input RIGHT — the diff between a right run and a wrong run on the same input is the highest-signal evidence you have.
>
> Then produce: (a) for each failure cluster, the specific step/decision that caused it and the trace lines that prove it; (b) one structured edit (see structured-edits.md) that fixes the highest-impact cluster, justified by the trace evidence you cited."

The proposer's output still funnels into the same structured-edit JSON (step 6c) and the same validation gate (6f). What changed is the *evidence*: it reasoned from traces it read, not from a summary it was fed.

### cross-candidate comparison (the Meta-Harness payoff)

The single most valuable read is **the same input under two candidates with different verdicts**. If `cand_0` failed input_1 and `cand_3` passed it, the proposer should diff those two traces to see which step `cand_3` fixed, then check whether the current parent reintroduced the bug. This is only possible because traces are archived per candidate. A round-local summary can't do it.

---

## why not just keep the summary

The summary path (old 6a) is cheaper per round but structurally blind: it can fix "the output was wrong" but not "the skill told the agent to call the tool before reading the input, so it always has stale data." The latter is a *process* bug visible only in the trace's tool ordering. Process bugs are where skills actually fail in production, which is exactly why trajectory evals exist; the proposer needs trajectory-level evidence to fix them.

**Cost control:** reading full traces costs optimizer tokens. Bound it: cap the proposer at reading train-side traces for the failing runs of the current parent plus at most 3 cross-candidate comparison pairs per round. If a run's trace exceeds ~2k tokens, the capture step should keep the tool-call/result spine and the turns around the marked divergence, dropping long verbatim tool payloads (store those truncated with a `[...truncated N chars...]` marker). Never drop the divergence window. Do not use validation traces as a cost-control shortcut; they remain sealed from the proposer regardless of size.

---

## relationship to self-diagnostics

6a.5 self-diagnosis (target model reflecting on its own failure) still runs and still feeds the proposer as one more signal. But it is now the *weaker* signal: a self-report is what the agent THINKS went wrong; the trace is what ACTUALLY happened. When they conflict, the trace wins. Self-diagnosis is most useful for pointing the proposer at which trace to read first, not as a substitute for reading it.
