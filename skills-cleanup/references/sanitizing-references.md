# Sanitizing Skill References for Public Repo

After copying skills from runtime to the public repo, audit each skill's `references/` directory. Many contain operational war stories tied to specific products. The SKILL.md itself is usually generic and useful; references are where private operational detail accumulates.

## Frontmatter & Shell-Snippet Hazards (NOT credential leaks — they break at load/paste time)

Separate from credential/PII scrubbing, public skills get bounced by automated reviewers (Codex especially) for two mechanical defects a secrets-grep won't catch. Sweep for both BEFORE the first push — they caused 3+ extra review rounds on exiao/skills PR #156 (June 2026), each re-flagged as a "regression" after a rebase dropped the fix.

### 1. YAML frontmatter `description:` that doesn't survive the parser
The `description` field is loaded by a YAML parser, so raw `#` and `:` are active syntax:
- **`#` starts a comment.** `description: ... review PR #N, look at this PR` silently truncates at ` #N` — the parsed description ends at "review PR" and every trigger after it is lost, so the skill under-routes for exactly those cases.
- **Unquoted `:` after a word is a mapping separator.** `description: Roleplay X. Use when: adversarial test` raises `mapping values are not allowed in this context` (Ruby/Psych and most safe-loaders) → the skill **fails to load at all**.
- **Fix:** wrap the whole description in a block scalar (`description: >-` then the text indented on the next line) OR double-quote it. Block scalar reads cleaner for long descriptions. Mental check after editing: "would `yaml.safe_load` keep every trigger phrase?" Reviewers verify this on the exact commit, so a stray `#` or unquoted `:` gets caught.

### 2. Angle-bracket placeholders that break when pasted into a shell
`<...>` is shell redirection. A snippet like `git add <files>`, `repos/<owner>/<repo>`, `<short-topic>`, or `for REPO in <owner>/<repo-a>` is meant as fill-in-the-blank but will redirect/clobber or error if pasted verbatim. Inside runnable shell blocks, replace with:
- a real shell variable the snippet already defines (`$OWNER`, `$REPO`, `$PR`), or
- an explicit placeholder var set just above (`SHORT_TOPIC="docs-wording"   # replace per group`), or
- an ALL-CAPS bareword (`FILES`, `SHORT_TOPIC`) that is obviously a placeholder and shell-safe.
Angle brackets are FINE in three non-shell spots: markdown prose, inside double-quoted strings (`--title "Follow up: <short topic>"`), and config/data tables (a `<owner>/<repo>` cell). Only the unquoted-in-a-`bash`-block occurrences are hazards. Codex reproduces the break and cites `-h` docs, so these are not declinable nits — just fix them.

Detection grep (run on the changed skills before pushing):
```bash
# descriptions with a # comment or an unquoted mid-line colon:
grep -rnE '^description: .*( #| [a-zA-Z]+:)' --include=SKILL.md .
# angle brackets (eyeball each hit for in-quote / in-table / prose false positives):
grep -rnE '<[a-z][a-z0-9-]*>' --include=SKILL.md .
```

## Remove entirely
- Dated lesson files (e.g. `2026-05-11-sentry-cron-lessons.md`) referencing specific repos, PRs, or issue IDs
- Account-specific config notes (PAT quirks, alternate GitHub account setup)
- Product-specific validation patterns (e.g. `investing-log-validation-prs.md`)
- Workflow files specific to the user's runtime setup (e.g. `backporting-pr-fixes-to-runtime.md`)

## Keep
- Generic workflow guides (e.g. `automated-review-final-sweep.md`, `delegation-and-git-pitfalls.md`)
- Technique references that apply to any repo (e.g. `branch-preservation-and-ci-auth.md`)

## Sanitize SKILL.md itself
- Remove product-specific file paths, model names, repo-specific commit patterns
- Remove `## Notes from prior runs` sections that reference deleted lesson files
- Keep workflow structure, triage frameworks, and general patterns
- Keep noise reduction tables and pattern catalogs (these are universally useful)

## Example: fix-sentry-issues (2026-05-12)
- Removed 8 reference files (all Bloom-specific: PR numbers, INVEST-xxx IDs, DB pool patterns, cron notes)
- Rewrote SKILL.md: removed Bloom file paths, Cerebras model names, repo-specific sections
- Kept: workflow steps, triage criteria, noise reduction patterns, PR template

## Example: babysit-pr (2026-05-12)
- Removed 4 of 11 references (alternate-github-accounts, cpe-research-pat-quirks, investing-log-validation-prs, backporting-pr-fixes-to-runtime)
- Kept 7 generally useful references about CI, delegation, redaction, review sweeps
