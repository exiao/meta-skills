#!/usr/bin/env bash
# Skill Budget & Usage Report
# Scans all skills for token cost, size, usage, duplicates, and budget ratios.
# Usage: bash bulk-budget-report.sh [--days N] [--context-tokens N]

set -euo pipefail

SKILLS_DIR="${SKILLS_DIR:-$HOME/.hermes/skills}"
EPISODES_DIR="${EPISODES_DIR:-$HOME/.hermes/episodes}"
DAYS=90
CONTEXT_TOKENS=200000
while [[ $# -gt 0 ]]; do
  case "$1" in
    --days) DAYS="$2"; shift 2 ;;
    --context-tokens) CONTEXT_TOKENS="$2"; shift 2 ;;
    *) DAYS="$1"; shift ;;
  esac
done

SKILL_LIST=$(mktemp)
PRELOADED_TSV=$(mktemp)  # name\tdesc for dupe detection (preloaded only)
find "$SKILLS_DIR" -name SKILL.md -not -path "*/skills-archive/*" | sort > "$SKILL_LIST"
trap "rm -f $SKILL_LIST $PRELOADED_TSV" EXIT

extract_desc() {
  awk '
    /^---$/ { if(++n==2) exit; next }
    n==1 && /^description:/ {
      sub(/^description: */, "")
      if ($0 == "|" || $0 == ">") { ml=1; next }
      gsub(/^"/, ""); gsub(/"$/, "")
      print; exit
    }
    ml && /^  / { sub(/^  +/, ""); printf "%s ", $0; next }
    ml && !/^  / { exit }
  ' "$1"
}

count_usage() {
  local name="$1"
  local count=0
  local last="-"
  if [[ -d "$EPISODES_DIR" ]]; then
    local ep_hits
    ep_hits=$(find "$EPISODES_DIR" -type f -mtime "-$DAYS" -print0 \
      | xargs -0 -r grep -li "\b${name}\b" 2>/dev/null || true)
    if [[ -n "$ep_hits" ]]; then
      count=$(echo "$ep_hits" | wc -l | tr -d ' ')
      last=$(echo "$ep_hits" | sort -r | head -1 | xargs basename 2>/dev/null | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | head -1 || echo "-")
      [[ -z "$last" ]] && last="-"
    fi
  fi
  echo "$count $last"
}

# --- Main table ---
printf "%-35s %-20s %-9s %10s %10s %10s %10s %8s %-12s %s\n" \
  "NAME" "CATEGORY" "PRELOADED" "DESC_BYTES" "DESC_TOKS" "BODY_BYTES" "BODY_TOKS" "USES" "LAST_USED" "FLAGS"
printf "%s\n" "$(printf '=%.0s' {1..155})"

t_preloaded=0
t_desc_tokens=0
t_body_tokens=0
t_heavy=0
t_large=0

while IFS= read -r skillmd; do
  skill_dir=$(dirname "$skillmd")
  skill_name=$(basename "$skill_dir")
  category_dir=$(dirname "$skill_dir")
  category=$(basename "$category_dir")

  if [[ "$category_dir" == "$SKILLS_DIR" ]]; then
    category="(flat)"
  fi

  desc=$(extract_desc "$skillmd")
  desc_bytes=${#desc}
  desc_tokens=$(( (desc_bytes + 3) / 4 ))

  body_bytes=$(wc -c < "$skillmd" | tr -d ' ')
  body_tokens=$(( (body_bytes + 3) / 4 ))

  if grep -q 'preloaded: *true' "$skillmd" 2>/dev/null; then
    preloaded="YES"
    t_preloaded=$((t_preloaded + 1))
    t_desc_tokens=$((t_desc_tokens + desc_tokens))
    t_body_tokens=$((t_body_tokens + body_tokens))
    # Save for dupe detection
    printf '%s\t%s\n' "$skill_name" "$desc" >> "$PRELOADED_TSV"
  else
    preloaded="no"
  fi

  read -r uses last_used <<< "$(count_usage "$skill_name")"

  flags=""
  if [[ "$preloaded" == "YES" && "$uses" -eq 0 ]]; then
    flags="UNUSED"
  fi
  if [[ "$desc_bytes" -gt 200 ]]; then
    [[ -n "$flags" ]] && flags="$flags,"
    flags="${flags}HEAVY_DESC"
    if [[ "$preloaded" == "YES" ]]; then t_heavy=$((t_heavy + 1)); fi
  fi
  if [[ "$body_bytes" -gt 20000 ]]; then
    [[ -n "$flags" ]] && flags="$flags,"
    flags="${flags}LARGE_BODY"
    if [[ "$preloaded" == "YES" ]]; then t_large=$((t_large + 1)); fi
  fi

  printf "%-35s %-20s %-9s %10d %10d %10d %10d %8d %-12s %s\n" \
    "$skill_name" "$category" "$preloaded" "$desc_bytes" "$desc_tokens" "$body_bytes" "$body_tokens" "$uses" "$last_used" "$flags"
done < "$SKILL_LIST"

# --- Budget % ---
echo ""
echo "=== BUDGET ==="
budget_tokens=$(( CONTEXT_TOKENS * 2 / 100 ))
echo "Context window:        $CONTEXT_TOKENS tokens"
echo "2% skill budget:       $budget_tokens tokens"
echo "Preloaded desc tokens: $t_desc_tokens ($(( t_desc_tokens * 100 / budget_tokens ))% of budget)"
echo "Preloaded skills:      $t_preloaded"
echo "Heavy descriptions:    $t_heavy (preloaded, over 200 bytes)"
echo "Large bodies:          $t_large (preloaded, over 20KB)"
remaining=$((budget_tokens - t_desc_tokens))
echo "Remaining budget:      $remaining tokens"

# --- Duplicate detection via Jaccard on preloaded descriptions ---
echo ""
echo "=== POTENTIAL DUPLICATES (preloaded, description similarity >= 40%) ==="

python3 - "$PRELOADED_TSV" <<'PYEOF'
import sys

STOP = {'the','a','an','and','or','is','to','for','of','in','on','with',
        'use','when','this','that','it','as','by','be','are','was','at',
        'from','also','can','any','all','do','has','have','its','not','will'}

def words(s):
    return set(w for w in s.lower().replace(',','').replace('.','').replace('"','').split() if w not in STOP and len(w) > 2)

def jaccard(a, b):
    if not a and not b: return 1.0
    if not a or not b: return 0.0
    return len(a & b) / len(a | b)

skills = []
with open(sys.argv[1]) as f:
    for line in f:
        line = line.rstrip('\n')
        if '\t' in line:
            name, desc = line.split('\t', 1)
            skills.append((name, desc, words(desc)))

found = 0
for i in range(len(skills)):
    for j in range(i+1, len(skills)):
        sim = jaccard(skills[i][2], skills[j][2])
        if sim >= 0.40:
            print(f"  {skills[i][0]} <-> {skills[j][0]}: {int(sim*100)}% similar")
            found += 1

if found == 0:
    print("  (none found among preloaded skills)")
PYEOF

echo ""
echo "Run with --days N to change lookback (default: 90)"
echo "Run with --context-tokens N to set context window (default: 200000)"
