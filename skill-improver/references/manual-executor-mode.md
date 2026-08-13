# Manual Executor Mode (when the eval loop tooling is blocked)

The autonomous loop assumes you can spawn target-model runs. Sometimes you can't:
the in-repo runner (e.g. `hill_climb.py`) regenerates outputs through an agent
harness whose only registered credential is capped (billing limit, OAuth refusal),
or no alternate provider is wired into the pipeline's auth. Do NOT declare the whole
task blocked. Most of skill-improver still runs, because **you (the session model)
are a perfectly good target model.**

## When to use this mode

Use it whenever ANY of these holds AND committed fixture artifacts exist:
- The repo's eval-driven runner needs a provider that is hard-capped or missing, OR
- **The runner's regenerate path is too slow for a fleet sweep** (measure it: tens of
  minutes/skill = too slow — see the main SKILL.md "In-repo eval loops" callout). This
  is the common case, not the exception. Do not treat manual-executor mode as a
  fallback only for "blocked" loops; it is the DEFAULT for breadth sweeps because it
  is seconds/skill vs tens-of-minutes and produces more accepted wins.
- Committed fixture artifacts exist (e.g. `evals/fixtures/<TICKER>/analysis/*.md`,
  `report.md`, a saved transcript). Those artifacts ARE prior outputs of the skills.

## The manual loop (no harness regeneration needed)

1. **Pick a skill that has a scorable committed artifact.** The fixture's
   `analysis/<lens>.md`, `report.md`, etc. were produced by the very skills you're
   improving. They are real baseline outputs — score them directly.
2. **Write 4-6 binary evals** from the skill's own Output Format + Anti-Patterns +
   Rules sections. The skill telling you what NOT to do is your eval list.
3. **Score the committed artifact = baseline.** Be adversarial. A skill whose own
   rules are violated by its committed output is a real, demonstrable defect, not a
   contrived one.
4. **Make one structured edit** to a working copy under
   `autoresearch-<skill>/<skill>-improved.md` (never touch the original yet).
5. **Re-execute the skill yourself** on the same fixture data, following the edited
   instructions, and re-score. Accept only if score went up with zero regressions.
6. **Apply the validated edit to the PR branch's SKILL.md**, copy the loop artifacts
   (evals, baseline/mutated outputs + scores, changelog) to `evals/skill_improver/<skill>/`.

## Regenerating ONE artifact when the harness runner isn't even on main

`hill_climb.py` / `hill_climb_isolate.py` and their `--isolate` mode may live only in
a stale local checkout, not on `origin/main`. Don't conclude "isolate unavailable, must
regenerate the whole report." You can drive a single-artifact regen directly:

- The pipeline fragments under `pipeline/run_parts/NN_*.py` are concatenated into one
  namespace by `run_research.py` (`exec(compile(...))`), so they CANNOT be imported
  standalone (`NameError: RunConfig`, fragment globals undefined). Import the assembled
  entrypoint instead: `import run_research; run_research.run_lens_analysis(cfg, skill,
  filename, label)`. The same applies to `phase_compile` and any other fragment fn.
- Copy the committed fixture into a temp workspace (`shutil.copytree`), point a
  `RunConfig(ticker=..., workspace=tmp, model="claude-opus-4-8", provider="anthropic")`
  at it, `unlink(missing_ok=True)` the one artifact, and call the lens fn. It reads
  `SKILL.md` from the worktree's `hermes_home/skills/research/<skill>/`, so the MUTATED
  prompt is actually exercised. One agent run (~3-6 min), not a full report compile.
- Venv/import: the borrowed sibling `.venv` has the CPE deps; add `~/.hermes/hermes-agent`
  to `PYTHONPATH` so `import run_agent`/`hermes_state` resolve (the pipeline sets
  `HERMES_HOME` to the worktree's `hermes_home`). Healthy regen emits a burst of
  `Auto-repaired tool name:` lines within ~60s; that's the alive marker, not a hang.

## Score the regenerated artifact STANDALONE vs the committed artifact STANDALONE

The persona/judge baseline you captured on the FULL memo is NOT the right comparison for
an isolate edit. A lens artifact scored alone routinely outscores the same content inside
the assembled memo (this session: lens-competitive scored 4.2 standalone but the full AVGO
memo scored 3.2 on the same persona — the compiler/synthesizer was dropping mechanism
detail the lens produced). So for an isolate mutation:

- Baseline = the COMMITTED `analysis/<lens>.md` scored standalone.
- After = the REGENERATED `analysis/<lens>.md` scored standalone.
- KEEP on composite-up + zero-dimension-regression across both. Both runs single-shot,
  so opus grading noise makes ±0.2 composite directional; weight the dimension that moved
  most and the visible artifact change (e.g. every advantage now carries mechanism+magnitude),
  not the composite alone.

The standalone-vs-full gap is itself a signal: when a lens scores well alone but the memo
scores poorly on the same axis, the leak is downstream — target the compiler/synthesizer,
not the lens. That's usually the higher-leverage edit.

When you score with a NEW persona that lives only in a different worktree, copy the
`personas/<name>/` dir + `registry.py` into the scoring worktree as SCRATCH (trash it +
`git checkout registry.py` before committing) so the PR carries only the skill edit and
its `evals/skill_improver/<skill>/` evidence, never the borrowed persona.

## Cheap programmatic scoring

Score banned-vocabulary / format evals with a script, not by eye, and reuse the
repo's own constants so your eval matches production:

```python
from config import BANNED_REPORT_TERMS, RATING_CONTEXT_TERMS  # repo's own lists
import re
hits = [w for w in BANNED_REPORT_TERMS if re.search(r'\b'+re.escape(w)+r'\b', text.lower())]
```

A fast batch scan across all committed lens/report artifacts (banned terms, verdict
lines, confidence scores, severity headers, pre-mortem sections) tells you in seconds
which skills have real headroom vs which are already clean — so you don't manufacture
marginal mutations on skills that are fine.

## The recurring defect this mode keeps surfacing

**Output-time footgun: buried rule gets overridden.** Skills state a constraint in a
mid-document "Anti-Patterns" / "Rules" list, but the model overrides it at generation
time and the always-present output template invites the violation. Seen twice in one
session:

- `transcript-analyzer` (5/6 -> 6/6): output template unconditionally rendered a
  "Narrative Shifts from Prior Quarter" section with a fill-in bullet, so the model
  fabricated a quarter-over-quarter shift from a single call even though rule #4 said
  to skip it without a prior transcript.
- `lens-risk` (2/6 -> 6/6): committed output carried a "Conclusion:" verdict, a
  "Confidence: 7/10" score, a Risk Matrix with severity headers, a "Pre-Mortem
  Scenarios" section, and the banned word "thesis" — all already forbidden by the
  skill's Anti-Patterns list, which sat far from the Output Format block.

**The fix (generalizable):** hoist the constraint INTO the output template, at the
surface where the model acts, as a `<!-- HARD CONSTRAINTS ... -->` comment immediately
under `## Output Format`. Enumerate the exact banned vocabulary and tell the model the
literal first line to start at ("Start the output at ### Customer Concentration"). This
is the "structural rules beat phrase bans" mutation principle applied to the template,
not the rules list. The same buried-rule fix works across skills, so check for it first.

## Preventive hardening across structurally-identical sibling skills

When the batch scan finds the SAME defect in several sibling skills (e.g. 3 of 4 lens
agents leaked opinion language on the same fixture because the opinion-ban sat in a
buried Anti-Patterns list with no Output-Format guard), the remaining siblings that
share that exact structure are one input away from the same leak even if THEIR committed
artifact happened to score clean. Hoisting the same `HARD CONSTRAINTS` guard into those
clean-but-vulnerable skills is a legitimate **preventive** improvement, and it is the
honest way to give breadth coverage ("a PR per skill") without violating the
"don't blind-edit a clean skill" rule:

- Only do it when the defect is demonstrably SYSTEMIC (proven by 2+ siblings actually
  failing on the same fixture), and the target skill shares the identical vulnerable
  structure (buried rule + unguarded output template). A clean artifact alone is NOT a
  license to edit; structural identity to a proven-broken sibling IS.
- Label it honestly in the commit and PR body as PREVENTIVE, distinct from a scored
  WIN. Do not imply a baseline->mutated score; there was no leak to fix, only a
  structure to harden.
- One worktree + one branch + one PR PER skill, each off the default branch
  (`skill-improver/<skill>-YYYYMMDD`). docs-check green is the validation bar for a
  pure prompt edit; the frozen-fixture eval suite cannot score prose (state this).
- Still skip skills with NO scorable/relevant surface (extractors like
  alphasense-extract/filing-reader, deprecated ones like chat-analyst, and skills whose
  flagged tokens are legitimate — e.g. the evaluator's own `VERDICT: PASS` line, or
  "sell-side"/"positive" used as financial terms). Report those as N/A or CLEAN, no PR.

## Cost note: why the in-repo regenerate path is the slow one

Measured this session on `hill_climb.py`: ~30 min/skill (1 iteration) because each
iteration regenerates the WHOLE fixture report TWICE on the big model (once for
baseline, once for the mutation) before scoring. 14 skills serial is roughly 5-6 hrs;
the designed 3-5 iterations would be 6-10 full report regens per skill. The eval
scoring itself is fast — the LLM report-writing is ~80% of wall-clock. This is why
manual-executor mode (score committed artifacts directly, seconds/skill) is the default
for fleet sweeps, and why you should smoke-test ONE iteration to measure cost before
fanning the harness loop out across a fleet.

## Full-report-regen targets (compiler/synthesizer) are too noisy for SINGLE-run hill-climbing

A lens edit scored via isolate is low-variance: only that one artifact changes, so a
±0.2 composite move tracks the edit. A compiler/synthesizer edit is NOT: `phase_compile`
regenerates the ENTIRE report.md, so section-to-section regeneration variance (±0.2-0.4
composite, this session) swamps the signal of one targeted clause. The tell that you're
in this trap: after a compiler edit, the dimension you targeted stays FLAT while OTHER
personas regress on sections your edit never touched (this session: a Competition-spec
clause left econ competitive_economics at 3/5 unchanged but dropped Druckenmiller
liquidity_macro 2->1 and risk_reward 3->2, both in untouched sections). Those regressions
are regen noise, not a caused effect, but the zero-regression gate still (correctly)
rejects the edit. Net: you burn a ~13-min full-report regen to produce an un-validatable
result.

Rule: do NOT hill-climb the compiler/synthesizer with single-run full-report scoring.
Either (a) average 3+ regens per condition (expensive), or (b) build a per-section
deterministic eval that scores ONLY the prose the edit targets (e.g. the Competition
section), so the rest of the report's regen variance can't move the score. The
standalone-vs-full gap (a lens scores 4.x alone but the memo scores lower on the same
axis) correctly identifies the compiler as where the leak is — but identifying the
target is not the same as being able to validate a fix on it.

### The per-section eval primitive (built; cpe-research PR #770, `evals/judge/section_eval.py`)

Option (b) is now SHIPPED — use it instead of re-deriving the approach:
- `extract_section(report_md, section)` pulls one `## N. <name>` block by NORMALIZED name
  (drops the `N. ` numeric prefix and a trailing `: qualifier`, lowercased). Boundary is
  h2-only (`^##\s`), so nested `###` sub-headers stay INSIDE the section. Returns None if
  absent. Deterministic — unit-test it directly, no LLM.
- `SECTION_DIMENSIONS` maps each report section to the (persona, dimensions) that actually
  judge it (e.g. Competition -> economics_professor's competitive_economics +
  mechanism_specificity). A section maps only to the dimensions a compiler edit to it can
  plausibly move.
- `score_section(report_md, section, model="claude-opus-4-8")` extracts the section, runs
  the existing `critique_memo_persona` on JUST that text, returns only the mapped dimensions
  + a `section_score`, full critique under `_full`.

Why this is the right surface: on the committed AVGO fixture the Competition section alone
scored 2.0 (competitive_economics 2, mechanism_specificity 2) — the exact weakness the
full-memo composite (3.8-4.0) MASKED. The next compiler hill-climb gates on `score_section`,
not full-memo composite, so unrelated-section regen variance can't move it.

Build pattern (reuse for analogous "score one piece, not the whole regen" primitives): a
deterministic extractor (regex on stable structure) + a thin scorer that filters an existing
judge's full output to the relevant dimensions. Imports must use the repo package path
(`from evals.judge.persona_judge import ...`), NOT bare `from persona_judge import` —
persona_judge itself does `from config import ...`, so the module only resolves with repo
root on `pythonpath` (set in pyproject `[tool.pytest]`). Ship as a measurement primitive
ONLY (no CI wiring, no hill_climb.py change); the loop that consumes it is the next PR.

## Triage with the RIGHT grader: don't edit a deep-data artifact to please the wrong persona

Before editing a lens, batch-score the committed artifact and read WHICH persona/dimension
is low and whether that grader is even the right judge for the artifact's job:

- The economics_professor (rigor) persona is the right grader for analytical lenses; if a
  lens already scores 4.0+ "Rigorous" on it, the rigor headroom is gone.
- The portfolio_manager (job-relevance) persona is the WRONG grader for deep-data
  artifacts (`financial_data.md`, `value_chain.md`) that exist to feed the appendix /
  knowledge graph, not to sit in front of a PM. PM complaints like "dump the 40-row bond
  ladder to an appendix" or "cut the technical panel" are arguing with the artifact's role;
  acting on them would gut the dense-data surface the compiler consumes. That is the
  blind-edit anti-pattern wearing a low score as a disguise.
- A single legitimate lens-level nit (e.g. a point restated 3x) surfaced on ONE noisy PM
  run is not enough to validate a mutation cleanly. "No mutation warranted" across the
  remaining lenses is the honest, correct outcome — report it, don't manufacture marginal
  PRs for breadth. This is the eval-gate-simplicity-over-coverage principle applied to a
  fleet of lenses: cover the one canonical defect you can prove, decline the long tail.

## Cross-fixture sweep: find the SYSTEMIC defect, then generalize ONE rule

When the goal is "make this work across all of X" (e.g. every Tier-1 ticker), do NOT
hill-climb one fixture and call the win general. The reusable pattern:

1. **Find a pre-existing artifact set to avoid regeneration.** Before assuming you must
   regenerate N memos (the expensive path), grep `workspace/<T>_<date>_*/report.md` and
   `research-outputs/<T>/<date>/report.md` — a prior batch run often already produced a
   full output per item. Those are scorable baselines for free. (This session: a complete
   2026-06-12 opus memo set for all 12 Tier-1 names existed; scoring them was ~48 LLM
   calls, zero regeneration.)
2. **Staleness tradeoff, stated explicitly.** A pre-existing set was made by an OLDER prompt
   on possibly an OLDER layout. It is VALID signal for "does this defect recur across items"
   (defects that are layout-independent transfer), but it is NOT a current-prompt baseline.
   Score only the sections/dimensions that exist in both layouts; flag the caveat on the PR.
3. **Build the defect matrix: item × section × dimension.** Score the same axes across every
   item, then aggregate per (section, dimension): mean score + count of items low (<=3).
   The SYSTEMIC defect is the dimension that fails on a MAJORITY of items, not the one with
   the lowest single score. (This session: Business Overview causal_rigor failed 8/8 tickers
   mean 2.50 — that unanimity is the signal; a 2.0 on one ticker alone would be noise.)
4. **Generalize the rule by naming CLASSES, not facts.** A cross-item rule must be
   item-agnostic by construction: name the universal mechanism/force CLASSES
   (demand / price / cost / mix; NRE-lockin / switching-cost / capacity / node-access) and
   tell the model to pull the specific instance the lens carries for THIS item. A rule that
   hardcodes one item's facts is overfit; a rule that names the class and defers the
   specifics to the lens generalizes. Hoist it into the output template (the buried-rule fix).
5. **Validate across a SUB-SECTOR SPREAD, not the family the rule came from.** Re-execute the
   affected section for one item per distinct sub-type (GPU / foundry / memory / equipment),
   score standalone, KEEP only if the rule lifts the target dimension across the MAJORITY with
   zero regression. A rule that helps the originating sub-type but regresses another is
   overfit to a sub-sector — reject it. Cross-sub-sector agreement REPLACES the single-fixture
   no-regression gate as the generalization proof.

You don't need to validate all N items — one per sub-sector is enough to prove generality
cheaply; offer the remaining items as an optional fuller pass. Reuse the same
`evals/judge/section_eval.py` per-section scorer (pass explicit `persona`/`dimensions` to
score an old-layout section that isn't in `SECTION_DIMENSIONS`).

## Honesty guardrails specific to this mode

- The deterministic eval suite usually runs against a FROZEN fixture and never
  exercises skill prose — so it can confirm "no regression" but cannot score a prose
  edit. State that plainly; do not imply the suite validated the improvement.
- Body-size trims (moving sections to `references/`) are content-preserving and CAN be
  validated without harness regeneration: confirm every moved heading still exists in
  the reference file, the output template is intact, and docs-check passes.
- Do not blind-edit a skill whose committed artifact is already clean. Scoring it is
  the result; "no mutation warranted" is a legitimate, honest outcome to report.
