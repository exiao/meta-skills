# PR #10 babysit plan

Objective: Make exiao/meta-skills#10 merge-ready after removal of the `mcporter` skill.

Steps:
1. Confirm live PR head/state, CI, all review and issue-comment sources, and worktree alignment.
2. Verify stale README references against the live head; make the smallest scoped documentation fix if needed.
3. Run focused validation, inspect the staged diff, commit only intended paths, and push to the PR branch.
4. Reply to and resolve addressed review threads; re-query all review sources on the new head.
5. Confirm green CI, clean merge state, clean diff, and zero live unresolved threads.

Acceptance criteria: README has no stale `mcporter` listing/credit, PR is on its own updated branch, CI is green, mergeable is clean, every live review thread is resolved, and plan steps are completed or explicitly cut.
