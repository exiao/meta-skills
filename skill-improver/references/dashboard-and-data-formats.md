# Dashboard and Data Formats

The full spec for the live dashboard and the artifact file formats. SKILL.md step 4 points here.

---

## live dashboard

Before running any experiments, create a live HTML dashboard at `autoresearch-[skill-name]/dashboard.html` and open it in the browser.

The dashboard must:
- Auto-refresh every 10 seconds (reads from `results.json`)
- Show TWO score progression lines: training score and validation score (experiment number on X axis, pass rate % on Y axis). Divergence between the two = overfitting signal.
- Show a colored bar for each experiment: green = keep, red = discard, blue = baseline, orange = slow update
- Show a table of all experiments with: experiment #, train_score, val_score, status, description, edit_ops applied
- Show per-eval breakdown: which evals pass most/least across all runs
- Show rejected-edit buffer contents (last 10)
- Show diagnostics frequency chart: how often each diagnostic category appears across all runs
- Show golden case status: a row per golden case with pass/fail history across experiments (🔒 indicator, green/red per experiment)
- Show the **score matrix heatmap** (the diagram's Scores Matrix): rows = tasks (`input_id` × `eval_name`), columns = pool candidates, cell = green (pass-rate high) to red (low). Mark Pareto-frontier candidates with a star in the column header so you can see which candidates are alive for selection.
- Show the **candidate pool tree**: each kept candidate as a node with an edge to its `parent_id` (mutation) or both `parents` (merge), so the branching structure is visible.
- Show current status: "Running experiment [N]..." or "Idle"
- Use clean styling with soft colors (white background, pastel accents, clean sans-serif font)

Generate the dashboard as a single self-contained HTML file with inline CSS and JavaScript. Use Chart.js loaded from CDN for the line chart. The JS should fetch `results.json` and re-render.

**Open it immediately** after creating it: `open dashboard.html` (macOS) so the user can see it in their browser.

---

## results.json format

The test set is NEVER scored before the final evaluation. During the run, `results.json` carries only train and validation scores. `final_test_score` is added once, at the very end.

```json
{
  "skill_name": "[name]",
  "status": "running",
  "current_experiment": 3,
  "optimizer_model": "claude-opus-4-6",
  "target_model": "gpt-5.5",
  "split": {"train": 4, "val": 2, "test": 2},
  "baseline": {"train_score": 70.0, "val_score": 65.0},
  "best": {"val_score": 90.0, "experiment": 5},
  "experiments": [
    {
      "id": 0,
      "train_score": 70.0,
      "val_score": 65.0,
      "max_train": 12,
      "max_val": 6,
      "status": "baseline",
      "description": "original skill — no changes",
      "edit_ops": [],
      "failure_patterns": [],
      "success_patterns": [],
      "diagnostics_summary": {"missing_context": 0, "guessed": 0, "tool_failure": 0, "low_confidence": 0, "none": 0},
      "golden_case_results": [],
      "self_diagnoses": []
    }
  ],
  "rejected_edits": [],
  "slow_updates": [],
  "eval_breakdown": [
    {"name": "Text legibility", "train_pass": 8, "val_pass": 3, "total_train": 12, "total_val": 6}
  ]
}
```

`max_train` and `max_val` are computed independently because train and validation sets differ in size:

```
max_train = [number of evals] × [runs per experiment] × [number of training inputs]
max_val   = [number of evals] × [runs per experiment] × [number of validation inputs]
```

When the run finishes (user stops it or ceiling hit), update `status` to `"complete"`, run the held-out test set ONCE, and add `final_test_score`. This is the only point at which the test set is ever scored.

---

## results.tsv format (tab-separated)

```
experiment	train_score	val_score	max_train	max_val	status	description
0	70.0%	65.0%	12	6	baseline	original skill — no changes
```

---

## output file tree

The skill produces these files in `autoresearch-[skill-name]/`:

```
autoresearch-[skill-name]/
├── dashboard.html           # live browser dashboard (train + val curves)
├── results.json             # data powering the dashboard
├── results.tsv              # score log with train_score and val_score columns
├── changelog.md             # detailed mutation log with edit ops and apply reports
├── rejected_edits.json      # buffer of failed mutations with structured edit details
├── slow_updates.json        # longitudinal comparison history
├── pool.json                # the candidate pool (every KEPT candidate + lineage)
├── score_matrix.json        # per-task × per-candidate pass-rates (the Scores Matrix)
├── checkpoint.json          # resume state
├── SKILL.md.baseline        # original skill before optimization (untouched)
└── [user-chosen-name].md    # working copy with protected guidance section
```

---

## checkpoint.json format

The resume state. Stores the **split membership** (not just counts) so a resumed run reuses the same sets instead of reshuffling.

```json
{
  "last_experiment": 7,
  "best_val_score": 90.0,
  "best_experiment": 5,
  "slow_update_count": 1,
  "best_skill_hash": "sha256:…",
  "pool_ids": ["cand_0", "cand_3", "cand_5", "cand_7"],
  "split": {
    "seed": 1337,
    "train": ["input_id_1", "input_id_4", "input_id_6", "input_id_8"],
    "val":   ["input_id_2", "input_id_7"],
    "test":  ["input_id_3", "input_id_5"]
  }
}
```

`best_skill_hash` is the hash of `[user-chosen-name].md.best`; on resume, restore from `.best` if the working file doesn't match. A deterministic `seed` plus an ordered input list is fine in place of explicit `split` arrays. `pool_ids` lists every candidate currently in `pool.json` so a resumed run rebuilds the same frontier.

---

## pool.json format

The candidate pool that Pareto selection (SKILL.md step 6.0) samples from. Every KEPT candidate gets an entry; the baseline is `cand_0`. The `parent_id` / `parents` fields give the diagram's branching tree.

```json
{
  "candidates": [
    {
      "id": "cand_0",
      "parent_id": null,
      "strategy": "baseline",
      "skill_file": "cand_0.md",
      "skill_hash": "sha256:…",
      "train_score": 70.0,
      "val_score": 65.0,
      "experiment": 0
    },
    {
      "id": "cand_3",
      "parent_id": "cand_0",
      "strategy": "mutation",
      "skill_file": "cand_3.md",
      "skill_hash": "sha256:…",
      "train_score": 80.0,
      "val_score": 75.0,
      "experiment": 3
    },
    {
      "id": "cand_7",
      "parents": ["cand_3", "cand_5"],
      "strategy": "merge",
      "skill_file": "cand_7.md",
      "skill_hash": "sha256:…",
      "train_score": 88.0,
      "val_score": 84.0,
      "experiment": 7
    }
  ]
}
```

Mutation children carry a single `parent_id`; merge children carry a `parents` pair. Store each candidate's frozen skill text as `cand_<id>.md` in the working directory so selection and merge can read any pool member's exact content, not just the current best.

---

## score_matrix.json format

The per-task × per-candidate pass-rate grid (the diagram's Scores Matrix). A "task" is one `(input_id, eval_name)` cell scored on the **training set only**; the value is the mean pass-rate over `runs per experiment`, in [0, 1]. This is the sole input to Pareto frontier computation.

```json
{
  "tasks": ["input_1::legibility", "input_1::accuracy", "input_4::legibility", "input_4::accuracy"],
  "matrix": {
    "cand_0": {"input_1::legibility": 0.0, "input_1::accuracy": 0.33, "input_4::legibility": 1.0, "input_4::accuracy": 0.0},
    "cand_3": {"input_1::legibility": 1.0, "input_1::accuracy": 0.66, "input_4::legibility": 1.0, "input_4::accuracy": 0.0},
    "cand_7": {"input_1::legibility": 1.0, "input_1::accuracy": 1.0,  "input_4::legibility": 1.0, "input_4::accuracy": 0.66}
  }
}
```

Validation cells are never written here: selection must not see validation, which stays a pure accept/reject gate. The frontier (per-task winners) and the task-win weights are computed from this file each time step 6.0 runs.
