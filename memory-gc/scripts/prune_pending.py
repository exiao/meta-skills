#!/usr/bin/env python3
"""Two-pass semantic prune for .pending.md.

Proven pattern from May 2026 sessions. Run AFTER dedup-pending.py (which catches
exact duplicates). This catches semantic duplicates and cross-category overlap.

Usage: python3 ~/.hermes/skills/memory/memory-gc/scripts/prune_pending.py

Expected reduction: 191->31 entries (84% removal) on typical daily pending files.

Key insight: project namespace sprawl is the #1 duplication source. A single
project often generates entries under several related namespaces, e.g.
proj:<name>, proj:<name>-wiki, proj:<name>-agent, proj:<name>/<subdir>,
proj:<name>-cli. The mega_topic function in Pass 2 collapses entries that
share a project-namespace root into one group.
"""

import re
from collections import defaultdict
from pathlib import Path

PENDING = Path.home() / ".hermes/episodes/.pending.md"

if not PENDING.exists():
    print(f"Pending file {PENDING} does not exist; nothing to prune.")
    raise SystemExit(0)

lines = [l.strip() for l in PENDING.read_text().splitlines() if l.strip()]
print(f"Input: {len(lines)} entries")

# Parse entries
entries = []
for line in lines:
    m = re.match(r'^(memory|user)\t\[(\d{4}-\d{2}-\d{2})\]\[([^\]]+)\]\s*(.+)$', line, re.IGNORECASE)
    if m:
        entries.append({
            'target': m.group(1).lower(), 'date': m.group(2),
            'cat': m.group(3), 'content': m.group(4), 'raw': line
        })
    else:
        entries.append({'target': 'unknown', 'date': '', 'cat': 'unknown',
                        'content': line, 'raw': line})

# -- Pass 1: Category-based hard drops + intra-category topic dedup --

HARD_DROP_CATS = {'task', 'tmp'}

# Fact patterns that are transient operational data, not durable memory.
# These get re-extracted every session but have no lasting architectural value.
TRANSIENT_FACT_KEYWORDS = [
    # Ad campaign metrics (change daily)
    'meta ads daily run', 'ad set budget crept', 'spend cap at',
    # Disk / cleanup (one-off operational)
    'disk cleanup', 'photorec', 'testdisk', 'recovered/',
    # Token usage / billing snapshots
    'all-time token usage',
    # PR status snapshots (stale within hours)
    'ready to merge', 'review comments addressed',
    # Specific earnings data (ephemeral)
    'earnings: eps',
]

RULE_MINUTIAE_KEYWORDS = [
    'frontmatter parser', 'regex pattern', 'prisma', 'pydantic',
    'css var', 'test mock data', 'campaign-level spending',
    'special ad category', 'meta special ad', 'force re-push',
    'head sha stale', 'trigger ci', 'gh auth switch',
    'not-null constraint', 'migration', 'lint formatting',
]

# Generic coding rules that are common knowledge, not durable memory.
# These get re-extracted every session because they appear in code reviews
# and PR fixes, but they encode no project-specific convention.
GENERIC_CODING_KEYWORDS = [
    # Syntax / formatting
    'f-string', 'f_string', 'backslash', 'import line', 'line-length',
    'ruff format', "ruff's", 'eslint', 'compound statements',
    # Git basics
    'git stash pop', 'git stash apply', 'merge conflict', 'conflict marker',
    '<<<<<<', 'push commit', 'push after', 'always push commits',
    'must be staged', 'force re-push',
    # Security patterns (common knowledge)
    'xss', 'html_escape', 'innerhtml', 'textcontent', 'path traversal',
    'os.sep', 'symlinks', 'toctou', 'race condition',
    # Error handling patterns
    'bare except', 'silent exception', 'try/except', 'try/finally',
    'catch-all exception', 'logger.warning not logger.error',
    'explicit error handling', 'graceful fallback', 'graceful shutdown',
    'transient failures', '5xx responses', 'response.ok',
    'async error responses', 'async polling handlers',
    # Testing patterns
    'caplog fixture', 'pytest-xdist', 'get_or_create', 'update_or_create',
    'test fixtures', 'test assertions on nav',
    # Validation patterns
    'type validation', 'validate command prefix', 'type-check phone',
    'fuzzy string matching', 'substring containment', 'full phrase match',
    'datetime string parsing', 'fromisoformat',
    # API / HTTP patterns
    'fetch api resolves on 4xx', 'stale response guards',
    'batch operations returning counts', 'connection leak',
    'db connection', 'pool exhaustion',
    # General coding
    'cache key function', 'cache key functions', 'import and reuse',
    'stub dataclass', 'backward compat', 'must be wrapped', 'auto-wrap',
    'set -e', 'executable scripts', 'process-wide file descriptor',
    'concurrent file writes', 'global variable scope', 'iife wrapping',
    'importlib.reload', 'cross-test module',
    # CI / review patterns
    'github actions ci failures at', 'fine-grained pat',
    'claude code review workflows', 'claude code review lgtm',
    'codex code review flags', 'dismiss codex', 'dismiss reviews',
    'stale changes_requested',
    # Framework-specific (not project-specific)
    'sector snapshot validation', 'middleware validation',
    'identical constraints', 'mega-file splits', 'ordered exec',
    'stripincompletemath', 'remarkmath',
]

kept = []
dropped_pass1 = 0
for e in entries:
    cat = e['cat']
    if cat in HARD_DROP_CATS:
        dropped_pass1 += 1
        continue
    if cat == 'fact':
        content_lower = e['content'].lower()
        if any(kw in content_lower for kw in TRANSIENT_FACT_KEYWORDS):
            dropped_pass1 += 1
            continue
    if cat == 'rule':
        content_lower = e['content'].lower()
        if any(kw in content_lower for kw in RULE_MINUTIAE_KEYWORDS):
            dropped_pass1 += 1
            continue
        if any(kw in content_lower for kw in GENERIC_CODING_KEYWORDS):
            dropped_pass1 += 1
            continue
    kept.append(e)

print(f"Pass 1 hard drops: {len(kept)} kept, {dropped_pass1} dropped")


def topic_key(e):
    """Intra-category topic key. Keep longest entry per key."""
    content = e['content'].lower()
    cat = e['cat']

    if cat.startswith('proj:'):
        project = cat
        if 'knowledge' in content or 'wiki' in content or 'entity' in content:
            return f"{project}:knowledge"
        if 'proxy' in content or 'gateway' in content:
            return f"{project}:proxy"
        if 'roadmap' in content or 'phase' in content:
            return f"{project}:roadmap"
        if 'middleware' in content or 'validation' in content or 'gate' in content:
            return f"{project}:validation"
        if 'sentry' in content or 'write_todos' in content:
            return f"{project}:sentry"
        pr_match = re.search(r'pr\s*#?(\d+)', content)
        if pr_match:
            return f"{project}:pr{pr_match.group(1)}"
        if 'sandbox' in content or 'vps' in content:
            return f"{project}:sandbox"
        if 'dashboard' in content or 'business insights' in content:
            return f"{project}:dashboard"
        if 'auth' in content or 'bearer' in content or 'cookie' in content:
            return f"{project}:auth"
        if 'issue' in content and 'cluster' in content:
            return f"{project}:issues"
        if 'site' in content or 'design system' in content or 'unified' in content:
            return f"{project}:sites"
        return f"{project}:general"

    if cat == 'fact':
        return f'fact:{content[:40]}'

    if cat == 'rule':
        if 'memory' in content:
            return 'rule:memory'
        if 'git' in content and ('auth' in content or 'token' in content):
            return 'rule:git-auth'
        return f'rule:{content[:40]}'

    if cat == 'pref':
        if 'ui' in content or 'tool' in content:
            return 'pref:ui-tool'
        return f'pref:{content[:40]}'

    if cat == 'meta':
        return f'meta:{content[:40]}'

    return f'{cat}:{content[:40]}'


topic_groups = defaultdict(list)
for e in kept:
    topic_groups[topic_key(e)].append(e)

after_pass1 = []
for key, group in topic_groups.items():
    group.sort(key=lambda x: len(x['content']), reverse=True)
    after_pass1.append(group[0])

print(f"Pass 1 topic dedup: {len(after_pass1)} entries")


# -- Pass 2: Cross-category mega-topic dedup --
# Collapses project namespace sprawl (the #1 duplication source) without
# hardcoding any specific project name. Entries under proj:<root>,
# proj:<root>-<suffix>, and proj:<root>/<subdir> all collapse to one group,
# sub-keyed by a detected topic word so distinct project facts still survive.
# Non-project facts keep content-derived keys; generic words like "auth" must
# not collapse unrelated durable facts before manual triage.

# Common sub-topic words seen across projects. Tune for your own workspace.
SUBTOPIC_WORDS = [
    'roadmap', 'phase', 'knowledge', 'wiki', 'entity', 'ingest',
    'auth', 'proxy', 'gateway', 'sandbox', 'deploy', 'launch',
    'dashboard', 'site', 'design system', 'validation', 'middleware',
    'issue', 'cluster', 'eval', 'pipeline', 'schema', 'migration',
    'market', 'events', 'health',
]


KNOWN_SPRAWL_SUFFIXES = {'agent', 'cli', 'site', 'wiki'}


def _ns_root(cat):
    """Reduce a proj: category to its namespace root.

    proj:foo-agent -> foo ; proj:foo/bar -> foo ; proj:foo-wiki -> foo.
    Hyphenated project names without a known sprawl suffix are preserved.
    """
    ns = cat.split(':', 1)[1] if ':' in cat else cat
    ns = ns.split('/', 1)[0]
    root, sep, suffix = ns.rpartition('-')
    if sep and suffix in KNOWN_SPRAWL_SUFFIXES:
        ns = root
    return ns


def mega_topic(e):
    """Cross-category topic key that collapses namespace sprawl generically."""
    c = e['content'].lower()
    cat = e['cat']

    if cat.startswith('proj:'):
        root = _ns_root(cat)
        for w in SUBTOPIC_WORDS:
            if w in c:
                return f'{root}:{w.replace(" ", "-")}'
        return f'{root}:other:{c[:30]}'

    return f'unique:{cat}:{c[:30]}'


groups = defaultdict(list)
for e in after_pass1:
    groups[mega_topic(e)].append(e)

final = []
for topic, group in groups.items():
    group.sort(key=lambda x: len(x['content']), reverse=True)
    final.append(group[0])
    if len(group) > 1:
        print(f"  Collapsed {len(group)} entries for '{topic}'")

print(f"\nFinal: {len(final)} entries")

# Preserve original order
idx_map = {id(e): i for i, e in enumerate(entries)}
final.sort(key=lambda e: idx_map.get(id(e), 999))

with open(PENDING, 'w') as f:
    for e in final:
        f.write(e['raw'] + '\n')

print(f"Written to {PENDING}")
