# PR #12 babysit plan

Objective: make exiao/meta-skills#12 merge-ready by removing stale catalog entries that link to the deleted workflow skills.

Steps:
1. Verify the live PR head, status, all review surfaces, and local/repository guidance; use an isolated worktree at the live head.
2. Reproduce the documentation defect and make the smallest scoped README correction on the PR branch.
3. Verify the catalog has no stale links and run applicable repository validation; inspect the precise diff.
4. Commit only the intended file, push to the existing PR branch, reply to and resolve addressed thread(s).
5. Re-query the new head for CI, review bodies/comments/threads, and merge cleanliness; complete only if clean.

Acceptance criteria: README has no references to either deleted skill; the PR branch contains the scoped fix; relevant validation and CI are green; all live review findings are resolved.
