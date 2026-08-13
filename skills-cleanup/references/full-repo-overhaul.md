# Full Repo Overhaul — Lessons from 2026-05-12

## When to use
User wants to completely replace the public repo contents with a curated subset: new categories, different skill selection, reorganized structure.

## Workflow

### 1. Plan the mapping
Create `~/.hermes/plans/skills-repo-overhaul.md` with new category structure (source → dest), inclusion/exclusion list, sanitization checklist.

### 2. Create worktree, delete everything except .github/, copy skills using mapping

### 3. Clean runtime artifacts
```bash
find . -name "_meta.json" -not -path "./.git/*" -delete
find . -name ".usage.json" -not -path "./.git/*" -delete
```

### 4. Credential scan (CRITICAL)
```bash
grep -rn "AKIA\|sk-\|ghp_\|ghs_\|xai-\|AIza\|@gmail\|@outlook\|exiao3\|eric@promptpm\|investwithbloom\|sk_live\|pk_live" . --include="*.md" -l
```
Also scan for: phone numbers (`+1`, formatted variants), Render IDs (`dpg-`, `tea-`), Meta Business IDs, RevenueCat project IDs (`proj[a-z0-9]+`), bundle IDs (`com.bloom.*`). Replace all with `$ENV_VAR` placeholders.

### 5. Cross-skill reference scan (BIGGEST TIME SINK)
After deleting skills, surviving skills still reference them. This caused 6 rounds of CI review churn in the 2026-05-12 overhaul.

**Do this BEFORE the first commit:**
```bash
for skill in <deleted-skill-names>; do
  hits=$(grep -rn "$skill" --include="*.md" . | grep -v ".git/" | wc -l)
  [ "$hits" -gt 0 ] && echo "BROKEN: $skill ($hits refs)"
done
```
Check both backticked and plain text references. Fix by replacing with surviving equivalent, genericizing, or removing the line.

### 6. CLAUDE.md and README
- CLAUDE.md is canonical; AGENTS.md symlinks to it
- Tables sorted alphabetically
- README: resource links, install instructions, "find more skills" links, skill structure tree, full attribution section with source repo links
- Verify counts: `find <cat> -name SKILL.md | wc -l`

### 7. PR creation (exiao token required)
```bash
source ~/.hermes/.env
GH_TOKEN="$EXIAO_SKILLS_GITHUB_TOKEN" gh pr create ...
```

### 8. CI review loop
Expect 3-6 rounds. Resolve threads via GraphQL after each fix push.

## Key lesson
Cross-skill reference validation is the #1 time sink. Do it exhaustively before the first push.
