# Pareto-based Candidate Selection

This is GEPA's core search mechanism (Agrawal et al. 2026, arxiv 2507.19457, Figure 1: "Pareto-based Candidate Filtering"). It's what lets reflective evolution escape the local optimum that greedy single-line hill-climbing falls into. SKILL.md step 6.0 points here.

---

## the problem with greedy selection

Without this, the loop always mutates from the single highest-`val_score` candidate. That candidate is an *average* winner. It can be mediocre-to-bad on a specific task that some other, lower-average candidate nails. By only ever branching from the average-best, you throw away the candidate that holds the key to the hard task, and you get stuck: every mutation is a small perturbation of one point in prompt space.

GEPA's fix: keep the candidate that's best on *at least one task* alive in the pool, and sometimes mutate from it instead. Diversity of parents = diversity of search directions = escape from local optima.

---

## the score matrix

Selection reads `score_matrix.json` (schema in `dashboard-and-data-formats.md`). Conceptually it's the diagram's Scores Matrix: a grid of pass/fail.

```
              cand P0   cand P1   cand P2   cand P3
task (i1,e1)    0         0         0         1      ← P3 best here
task (i1,e2)    0         1         0         0      ← P1 best here
task (i2,e1)    0         1         1         0      ← P1, P2 tie best
task (i2,e2)    0         0         1         0      ← P2 best here
```

A "task" is one `(input_id, eval_name)` cell, scored on the **training set only** (validation stays a pure gate; never let val outcomes steer selection). Average over the `runs per experiment` so a cell value is a pass-rate in [0,1], not a single noisy bit.

---

## computing the Pareto frontier

A candidate is **on the frontier** if there exists at least one task where no other candidate in the pool scores strictly higher. (Equivalently: it is the unique or tied-best on ≥1 task.) Ties are allowed: if two candidates both top a task, both get credit for it.

```python
def pareto_frontier(matrix):
    # matrix[cand_id][task_id] = pass_rate in [0,1]
    tasks = {t for c in matrix.values() for t in c}
    frontier = set()
    for task in tasks:
        best = max(matrix[c].get(task, 0.0) for c in matrix)
        if best == 0.0:
            continue  # nobody solves this task; it gives no selection signal
        for c in matrix:
            if matrix[c].get(task, 0.0) == best:
                frontier.add(c)
    return frontier
```

This is GEPA's exact filter: the union of per-task winners, not the classic dominance frontier. It's deliberately generous — a candidate that wins even one task survives.

---

## sampling the parent

From the frontier, sample the mutation parent **weighted by how many tasks it wins** (GEPA's stochastic Pareto sampling). A candidate that's best on 5 tasks is 5x more likely to be picked than one best on a single task.

```python
import random

def sample_parent(matrix, frontier, prefer_smaller_size=None):
    wins = {c: 0 for c in frontier}
    tasks = {t for c in matrix.values() for t in c}
    for task in tasks:
        best = max(matrix[c].get(task, 0.0) for c in matrix)
        if best == 0.0:
            continue
        winners = [c for c in frontier if matrix[c].get(task, 0.0) == best]
        for c in winners:
            wins[c] += 1.0 / len(winners)   # split credit on ties
    parents = list(wins)
    weights = [wins[c] for c in parents]
    # tie-break toward smaller skills (simplicity > coverage)
    if prefer_smaller_size:
        weights = [w / max(1, prefer_smaller_size[c]) for c, w in zip(parents, weights)]
    return random.choices(parents, weights=weights, k=1)[0]
```

**Tie-break toward smaller skills.** When weights are close, bias toward the candidate with the smaller SKILL.md byte size. Matches the standing simplicity-over-coverage preference and stops the pool from drifting toward bloated prompts that won by accretion.

---

## interaction with the rest of the loop

- **Golden cases are orthogonal.** Frontier membership never exempts a candidate from the golden-case gate. A mutation that regresses any golden case is still discarded instantly (6e), regardless of which parent produced it.
- **Rejected-edit buffer still applies.** The buffer is injected into the failure-clustering prompt as before. Pareto changes *which parent* you mutate, not *which edits* you've already ruled out.
- **The delivered artifact is still the single best.** `.best` / `best_skill_hash` remain the highest-`val_score` candidate. The pool exists only to feed selection; at the end you ship the one best skill, not the pool.
- **Degenerate case = today's behavior.** With a 1-candidate pool (the baseline, before any KEEP), the frontier is that one candidate and selection trivially returns it. So a fresh run behaves exactly like the old greedy loop until the pool grows. Fully backward-compatible.

---

## why this beats greedy (the worked intuition)

Suppose P1 averages 80% (best overall) but scores 0 on task T. P2 averages 60% but is the only candidate that solves T. Greedy always mutates P1 and never has the substrate to learn T, because P1's lineage has never seen a version that gets T right. Pareto keeps P2 on the frontier; eventually a mutation of P2 (or a merge of P1 and P2, see `system-aware-merge.md`) carries T's solution into a high-average candidate. That crossover of "good on average" with "good on the hard task" is the whole point.
