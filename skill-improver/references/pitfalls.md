# Skill-Improver Pitfalls

## Self-scoring bias
When the same agent generates outputs AND scores them, scores inflate by 15-25%. The agent is generous with its own work and interprets eval criteria generously. The failure analysis is more valuable than the score itself. If baseline comes back 90%+, be skeptical: read the actual outputs and failure patterns before concluding the skill doesn't need work. The three most useful artifacts from a baseline run are: (1) which evals fail most, (2) what the failing outputs look like, and (3) what class of question triggers the weakest responses.

Mitigations that break the bias:
- **Separate grader subagent.** Spawn a dedicated grader that only sees the output and eval criteria, not the skill or generation context. The grader should not know which experiment produced the output.
- **Adversarial eval phrasing.** Look for the absence of bad patterns rather than the presence of good ones. "Does the output contain zero instances of [generic advice pattern]?" is harder to game than "Does it include specific tactical advice?"
- **Discrimination test eval.** Add: "Would this output be materially different without the skill? Could a vanilla model produce something equivalent?" If yes, the skill isn't adding value and the eval is non-discriminating. This is the most important eval for strategy/creative skills where the failure mode is "sounds good but says nothing the model wouldn't say anyway."
- **Calibrate with a known-bad output.** Before running the loop, manually write one deliberately mediocre output and score it against your evals. If it scores above 50%, your evals are too easy.

Suspect inflated scores when: baseline is above 90% on the first run, all evals pass on every run (no variance = no signal), or the specificity/anti-slop eval passes consistently but the outputs feel generic when you read them.

## High baseline doesn't mean stop
A 95%+ baseline with self-scoring often masks real gaps. In one session, a content-strategy skill scored 96% (24/25) but the failure analysis revealed: anti-slop leakage on conversion advice, research steps getting skipped on format-focused questions, and framework over-recitation instead of synthesis. The targeted fixes from failure analysis improved the skill more than 10 mutation experiments would have. When baseline is high, shift from the autoresearch loop to targeted fixes informed by the failure patterns.

## Subagent timeouts on heavy-output skills
Skills that produce long outputs from large inputs (e.g. summarizing 500 tweets into a digest) will timeout subagents at the default 600s limit. Each "run" requires the agent to read hundreds of items, triage, format, and output thousands of chars; a single run can take 3-5 minutes. With 3 runs per experiment, one experiment can exhaust the timeout. Mitigations: (1) reduce runs-per-experiment to 2 for heavy skills, (2) pre-filter the test input to a smaller representative sample (e.g. 100 tweets instead of 500), (3) use the orchestrator role so the subagent can delegate individual runs, or (4) run experiments sequentially in the parent agent instead of delegating the full loop. The parent agent continuing from where the subagent left off (checking results.tsv) is the pragmatic fallback.

## Skills with reference files
Large skills (500+ lines with references/) need evals that test whether the agent correctly routes to reference files rather than trying to cover everything inline. Add an eval like: "Does the output point to specific reference files for deeper implementation?" This prevents the skill from becoming a recitation engine.

## Eval-able vs taste-dependent improvements
Some skill gaps are eval-able (missing research step, broken skill references, generic CTA advice). Others are taste-dependent (does the strategy feel like genuine advice vs framework recitation?). The autoresearch loop handles the first kind well. The second kind needs human review of actual outputs and targeted rewrites, not more mutation cycles.

## Structural rules beat phrase bans
When a skill produces outputs with unwanted patterns (e.g. product-centric copy in an ad skill), banning specific phrases via kill lists triggers whack-a-mole: the model works around banned phrases with equivalent constructions. More effective: (1) structural rules ("if the brand is mentioned in the first sentence, you've failed"), (2) positive examples of the desired pattern, and (3) structural self-tests ("cover up the brand name; does the copy still work as content?"). One structural rule replaced 12 kill phrases in the meta-ads case study.

## Persona directives can cause regression
Adding named personas (e.g. "The Checker: checks portfolio 5x/day") as directives in a skill can pull the model toward problem-solution framing ("this person has problem X, product solves it"). Personas work as context in reference files but harm output quality when embedded as generation directives. If persona targeting is needed, frame it as "who this is for" metadata, not as the creative starting point.

## Self-diagnosis bias (step 6a.5)
When the target model is asked "what would need to change for you to get this right?", it rationalizes. Common biases: (1) blaming missing context when the real issue is a bad instruction, (2) suggesting surface-level fixes (add a rule) when the issue is structural (wrong process), (3) proposing changes that would fix this specific case but break others. The optimizer model should treat self-diagnoses as one signal among several, not as ground truth. If the self-diagnosis contradicts failure cluster analysis, the cluster analysis wins because it's based on patterns across multiple failures, not one model's introspection about a single case.

## False confidence in self-diagnostics (step 6d.5)
The most dangerous diagnostic is `DIAGNOSTIC: none` on a run that fails evals. This means the agent was confidently wrong and didn't notice. Track the correlation between `none` diagnostics and eval failures. A high false-confidence rate (>20%) suggests the skill is actively misleading the agent, giving it enough surface-level structure to feel confident while producing wrong outputs. This is harder to fix than missing context because the agent doesn't know it needs help.

## Public repo skill names differ from runtime names
When running autoresearch on skills that exist in both a public repo (exiao/skills) and a private runtime (~/.hermes/skills/), skill cross-references may use names that only exist in one context. The runtime uses aliases like `tweet-ideas`, `article-writer`, `slideshow-creator` that don't exist in the public repo (which uses `writer`, `video skills`). Always verify cross-referenced skill names exist in the target context before scoring reference-routing evals.

## Porting skill edits to a public mirror: patch surgically, never copy files over

When the same skill lives in a private runtime (`~/.hermes/skills/`) and a public mirror repo (e.g. `exiao/meta-skills`, `exiao/skills`), the two have usually diverged on purpose: the public copy strips `preloaded: true`, drops runtime-only reference files, and rewrites personal paths (`~/.hermes/skills/...`) to portable ones (`skills/...`). A wholesale `cp runtime/SKILL.md repo/SKILL.md` to land your change will silently revert all of that divergence AND add dangling links to references the public repo doesn't carry. Diff before you trust a copy.

The correct port: re-apply only YOUR change as a set of surgical `str_replace`/`patch` edits onto the repo's own version, anchoring each on text that is identical in both copies. Genuinely-new reference files are the only thing safe to copy verbatim. Diff-check that the runtime->repo delta, minus your intended additions, is empty before committing:

**Layered PRs in one session: re-anchor the second layer on the repo's ALREADY-PATCHED version, not the original.** When you build a feature as two stacked layers in the same session (GEPA/Pareto then Meta-Harness traces, June 2026, same PR branch), the runtime gets both edits before the repo gets either. By the time you port layer 2, layer 1's anchor text in the runtime has already mutated, so a runtime->repo diff shows BOTH layers' changes mixed together. Port one layer at a time: grep the repo for the layer-1 anchor to confirm whether the repo already has it (it does if you committed layer 1 first), then anchor each layer-2 patch on text the repo actually currently holds. Re-check `git status`/`grep` on the repo between layers; never assume the repo line matches the runtime line after you've edited the runtime twice.
```
diff repo/SKILL.md runtime/SKILL.md | grep -E '^[<>]' \
  | grep -ivE 'pareto|frontier|merge|<your-feature-keywords>' | head
```
If that filtered diff shows anything, it's pre-existing divergence you'd be clobbering. In the GEPA/Pareto port (June 2026) this caught the public repo's deliberate portable-path rewrites and its leaner ref set; copying would have reverted both. After patching, verify every `references/<file>.md` the SKILL.md links to actually exists in the repo, and that frontmatter still parses, before opening the PR.

## In-repo eval loop is the real engine; meta-skill is the methodology

When a target project already has its own eval-driven mutation script (e.g. CPE Research's `scripts/hill_climb.py`), that script IS skill-improver for that repo: deterministic pytest evals, structured edits, rejected-edit buffer, per-test regression guard. Do not reimplement the loop in the Hermes meta-skill. Use the in-repo runner and apply this skill's *principles* (binary evals, structured edits, regression gate, honest reporting). Read the runner's `main()` and acceptance gate before running it so you know what it can and can't accept.

## Frozen-fixture evals can never accept a mutation

If the in-repo loop scores against a FROZEN fixture (a pre-generated workspace checked into the repo) and the acceptance gate is `mutated_score > baseline_score`, then editing the skill prose can't change the score at all unless the loop REGENERATES the artifact first. Two consequences:
1. If the deterministic suite is already 100% green against the frozen fixture (CPE: 1191 passed / 0 failed), `--no-regenerate` runs can never accept — both sides are 100%. The headroom lives only in regenerated output.
2. The regeneration step is the expensive one (runs the full agent harness through the production model per iteration, ~5 min each). 14 skills x 3 iterations x ~2 regenerations = 80+ model generations = hours and real dollars. ALWAYS smoke-test ONE iteration to measure wall-time and confirm the loop produces a real mutation before fanning out across a fleet.

## Provider billing caps block regeneration, not tiny calls

A usage/billing cap on the model provider hard-fails the LARGE regeneration call (HTTP 400 "third-party apps now draw from your extra usage") while tiny direct probe calls still pass. So a one-token probe succeeding does NOT prove the loop will run. Verify with a ~4k-token call, or accept that a green tiny-probe + failing harness call means a usage cap, not a code bug. **Even a ~4k-token probe is not fully reliable:** a capped account has passed a mid-size probe while the *full* multi-call grade (e.g. `judge_workspace` making many Opus calls) still 400'd on the extra-usage wall on call #1. When the question is "has the cap cleared enough to run the real loop," the only trustworthy unblock test is a full grade, not any probe. The signature: a harness-sized Anthropic call returns `stop_reason: refusal` with zero content blocks (`len(response.content) == 0`), not an exception — code that does `response.content[0].text` then throws a confusing `IndexError` instead of surfacing the cap. When this hits mid-fleet, stop and ask the user to top up usage or approve rerouting regeneration to a fallback provider (changes the eval-target model) — do not silently burn a different paid bucket to dodge the cap.

## Mandatory budget caps on any optimize loop
An unbounded optimize→measure→accept loop is the fastest way to drain a shared model/proxy pool, so every run carries hard caps, not advice. Defaults to enforce when a task omits them: `goal_max_turns: 25`, `max_runtime: 60m`, optimizer `max_iterations: 30`, and an accept-rate < ~50% bailout with cost-per-accepted-change tracking. A run that hits a cap STOPS and reports the partial delta for review rather than running on; wanting to exceed a cap to "finish the win" is itself the stop signal. Reality check on cost: one full regeneration of a large artifact (e.g. a CPE compiler report on Opus) has measured ~20-25min *per round* including the agent's internal self-verify/patch retries, so a 60m wall holds at most 1-2 regen rounds before any grading — size the candidate/reward accordingly or the loop can't complete even one honest iteration.

## Scrub HERMES_KANBAN_* when spawning nested graders
If this loop runs inline on a kanban card and spawns a nested judge/grader agent, that subprocess inherits `HERMES_KANBAN_TASK` (and siblings) and can write a spurious completed-event to the *caller's* card. `sanitize_inherited_hermes_env` strips approval flags but not the `HERMES_KANBAN_*` vars, so scrub them explicitly in any subprocess env you spawn.

### Before declaring "blocked," prove no free fallback exists
A capped primary provider does NOT automatically mean blocked. Diagnose exhaustively before asking the user to spend:
1. **The pipeline forces its own HERMES_HOME.** In-repo harnesses set `os.environ["HERMES_HOME"] = ./hermes_home` at import, so the agent reads credentials from `hermes_home/auth.json` and `hermes_home/.env`, NOT the shell. Your shell having `GEMINI_API_KEY` / `OPENAI_API_KEY` / `OPENROUTER_API_KEY` is irrelevant — the harness never sees them.
2. **Check the credential pool first:** `python3 -c "import json; print(json.load(open('hermes_home/auth.json'))['credential_pool'])"`. If it's `['anthropic']` only, there is genuinely no wired fallback, even if `config.yaml` lists `fallback_providers`. A configured fallback with no registered key still fails: "Provider X is set but no API key was found."
3. **Provider key-name mismatches are silent:** the harness wants `GOOGLE_API_KEY` (not `GEMINI_API_KEY`) and `OPENAI-CODEX_API_KEY` (not `OPENAI_API_KEY`). Re-exporting the right name does nothing if the harness reads from auth.json rather than env.
4. Only after confirming the credential pool has no usable alternate provider should you tell the user "no free path exists." Then the choices are: top up the capped provider, OR authorize registering a key into the pipeline's `hermes_home` auth (a config + spend change — don't do it unilaterally).

## Be your own executor when the in-repo loop is credential-blocked

The in-repo eval-gated runner (e.g. hill_climb) and the Hermes meta-skill loop are two different execution paths. When the in-repo runner is blocked (provider cap on its `hermes_home/auth.json` credential, see credential-pool diagnosis above), you are NOT fully blocked — the meta-skill's own loop can still run because YOU are the executor and you have working LLM access this session. This path needs no project credential at all:
1. Pull a real input from the project's fixtures (e.g. `evals/fixtures/<TICKER>/raw/transcript.json`), not a synthetic one.
2. Define 3-6 binary evals from the skill's own output-format + Rules sections; designate one golden case from a stated-but-easily-violated rule.
3. Execute the BASELINE skill yourself (follow its SKILL.md literally as the target model), write the output, score it honestly against every eval.
4. Cluster the failure, propose ONE structured edit, apply to a working copy, RE-EXECUTE yourself, re-score. Keep only if it improves with zero regressions.
5. Commit the validated edit to the PR branch with the full artifact set (evals, baseline/mutated outputs, scores, changelog) under `evals/skill_improver/<skill>/`.

This delivered real eval-validated wins when hill_climb was capped (CPE transcript-analyzer 5/6 -> 6/6; lens-risk 2/6 -> 6/6). The golden eval is where the value concentrates: skills routinely state a constraint in their Rules list ("skip narrative shifts when no prior transcript") yet still violate it because the OUTPUT TEMPLATE unconditionally renders that section with a fill-in slot, inviting the model to populate it. The fix is structural: make the section conditional INSIDE the template where the model acts, with an explicit OMIT instruction and a single canonical "Skipped — <reason>" line. A buried rule does not beat an always-present template slot.

### The buried-constraint-list anti-pattern (constraints belong at the output surface)
Generalize the template-slot insight: a skill that lists its constraints in a mid-skill "Anti-Patterns" / "Rules" section, FAR from the "## Output Format" block, will see those constraints overridden. The lens-risk case proved it: the skill's Anti-Patterns explicitly banned severity ratings, opinion words, and pre-mortems, yet the produced output opened with a "Conclusion:" verdict, a "Confidence: 7/10" score, a Risk Matrix with severity headers ("Customer Concentration: Critical"), a "Pre-Mortem Scenarios" section, AND the hard-banned word "thesis" — 4 of 6 evals failing. The model read the framework, generated, and never re-consulted the distant rules list. Fix: hoist the hard constraints into the Output Format block as an explicit checklist right where the model is about to write ("Do NOT open with a Conclusion line; no Confidence score; no severity tags in headers; start the output at ### <first section>; if you catch yourself writing a verdict, delete it"). Co-locating the constraint with the action fixed all 4 fails with zero regressions. Rule of thumb: if a skill bans X but its outputs still contain X, the ban is in the wrong place — move it adjacent to the generation surface, don't restate it louder.

### Mine the project's own banned-term constants for cheap, objective evals
When the target repo defines its quality vocabulary as code constants (CPE: `config.BANNED_REPORT_TERMS`, `RATING_CONTEXT_TERMS`), import them and score with a `\b<term>\b` regex instead of eyeballing. This turns a taste-judgment eval into a deterministic one, lets you scan ALL committed fixture artifacts in one pass to find which skills' outputs already violate the contract (that scan is how lens-risk's "thesis" leak surfaced), and gives an objective before/after check on the mutation. Honor the repo's own context rules: e.g. CPE distinguishes hard-banned terms (fail on any whole-word hit) from rating-context terms that only fail when the report issues its OWN rating — replicate that logic, don't flag bare descriptive uses.

### Honest scope when only some skills are executable
Not every skill can be honestly executed against a given fixture: filing-reader needs `raw/risk_factors.json` etc. that may be absent; claim-verifier needs live web tools. Run the loop only where you can produce a genuine eval delta on real inputs. Do not manufacture marginal deltas on already-strong skills (re-running a high-quality fully-sourced lens output by hand for a +0 is wasted effort). One real validated win plus an honest "these others lacked fixture inputs to score" beats a fleet of fabricated 5/6->6/6 claims.

## Defer behavior-affecting structural edits out of a blind pass

Body-size trims (S2/B2) and reference-dedup (C4) MOVE content the agent loads and reasons from, so they change behavior. When you can't run the eval-gated loop (e.g. provider capped), apply only the SAFE additive fixes (descriptions, Gotchas) and ship the structural trims through the eval loop later. Track the deferred items explicitly in the PR (don't mark them silently "fixed").

## Run the algorithm against its own worked example before shipping it

When a reference file states an algorithm (a frontier computation, a scoring formula, a selection rule) AND a worked example meant to demonstrate it, the prose narrative and the actual math drift apart silently. Execute the algorithm against the example's numbers before committing. In the GEPA/Pareto build (June 2026), the worked example's score matrix gave a candidate a `1.0` tie on two tasks while the prose claimed that candidate was "dropped from the frontier" — but GEPA's frontier is tie-inclusive, so running the real `pareto_frontier()` over the example kept it, directly contradicting the narrative. The fix was to make the example's numbers genuinely dominated (`0.5` instead of `1.0`) so the math matched the words. A worked example that doesn't survive its own algorithm teaches the next agent the wrong intuition. Cheapest verification for a doc-only change: paste the algorithm and the example into a scratch script, run it, confirm the output matches every claim the prose makes (frontier membership, sampling shares, degenerate cases like singleton pool and all-zero matrix).

## Additive bias: more rules = worse performance
The optimizer's default is to append instructions when evals fail. This is a trap. In babysit-pr optimization (May 2026), adding explicit triage templates, concrete staleness verification steps, and scope check enforcement improved training from 78% to 100% but validation dropped from 87% to 77%. The added instructions crowded out the core loop structure, causing the model to skip scope checks and batch-classify comments instead of triaging individually. The fix was radical subtraction: moving 163 lines of gotchas to a reference file and rewriting the 632-line skill as 123 lines. The shorter version scored 91.7% train with a simpler, more followable structure. When multiple additive edits fail to improve validation, try cutting the skill in half instead. A model that reads 123 focused lines outperforms one drowning in 632 lines of edge cases.
