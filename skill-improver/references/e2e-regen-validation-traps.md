# E2E-regen validation traps (in-repo memo/report pipelines)

When you hill-climb a compiler/prompt rule and prove it by re-running the real
generator (e.g. CPE Research `phase_compile`) and scoring section-by-section,
two traps will silently give you wrong deltas. Both bit a real run and cost a
full re-validation. Check BOTH before trusting any before/after table.

## Trap 1 — the regen and baseline compilers must differ by EXACTLY one rule

The delta you report is only attributable to your new rule if the baseline
compile and the regen compile are identical except for that rule.

Failure mode that happened: the baseline reports were compiled in a worktree
whose compiler already carried two earlier merged rules (#771 mechanism+magnitude,
#772 causal-chain). The new rule's PR branch was cut off `origin/main`, where
those two rules are NOT merged. So the regen compiler had ONLY the new rule and
was MISSING the other two. Result: unrelated sections (Competition, Business
Overview) looked like they "regressed" by 1.0-2.0 — but that was just the
ABSENCE of the other two rules in the regen, nothing the new rule did.

Why a temp `HERMES_HOME` does NOT save you: in CPE Research `config.py` hardcodes
`SKILLS_DIR = PROJECT_ROOT / "hermes_home" / "skills" / "research"`. It does NOT
read `$HERMES_HOME`. So `phase_compile` always loads the compiler SKILL.md from
the WORKTREE it runs in, regardless of any `HERMES_HOME` env var you export. A
`cp -R hermes_home /tmp/hh_all3 && HERMES_HOME=/tmp/hh_all3` does nothing.

Fixes:
- Stack the new rule ON TOP of a compiler that already has every other rule the
  baseline has (add it as an UNCOMMITTED edit in the baseline worktree, regen
  there, then revert the uncommitted edit). The rule's own PR branch stays
  cut from main and carries only the one-rule diff.
- BEFORE trusting any delta, grep-count EVERY rule in BOTH the baseline compiler
  and the regen compiler and confirm they match except the one under test:
  `grep -c "RULE PHRASE" <worktree>/hermes_home/skills/research/compiler/SKILL.md`
- Verify which SKILL.md the generator actually reads:
  `HERMES_HOME=... python3 -c "import config; print(config.SKILLS_DIR)"`
  and confirm it points where you think (it points at PROJECT_ROOT, not HERMES_HOME).

## Trap 2 — a single-shot section score is ±0.5 noisy on BOTH ends; debunk flags before believing them

The persona section scorer (opus) is single-shot noisy by ~±0.5. A before/after
table built from one score per cell will routinely show a phantom 1.0 swing on a
section your rule did not even touch.

Failure mode that happened: a full recompile reshuffles EVERY section, so an
untargeted section (MU Competition) read 4.5 in the baseline and 3.0 in the regen
— a flagged "−1.5 regression". Re-scoring that one section 3x on each side gave
4.0 vs 4.0, identical. The 4.5 and the 3.0 were both single-shot noise.

Discipline:
- A rule can only causally affect the section(s) whose spec it edits. If a flagged
  regression is on a section your rule does NOT touch, it is noise until proven
  otherwise — do not report it as a regression, and do not "fix" it.
- Before believing ANY regression flag (Δ ≤ −1.0), re-score that section 3x on
  BOTH baseline and regen. Trust the stable value, not the first read. (This is
  the same 3x-re-score discipline the Q2 cross-time gate used.)
- Conversely, treat single-shot GAINS as upper bounds too. Manual splices and
  one-shot regen scores overstate; the re-checked number is the honest one.

## One-line checklist before reporting a hill-climb delta
1. Rule-count parity in both compilers (only the test rule differs)? 
2. Generator reads the compiler you think (config.SKILLS_DIR, not $HERMES_HOME)?
3. Every flagged regression on an untouched section re-scored 3x and still real?
4. Target lift re-scored (not a single-shot upper bound)?
