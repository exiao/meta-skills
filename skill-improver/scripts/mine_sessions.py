#!/usr/bin/env python3
"""Mine real skill executions from Hermes session + episode history into candidate eval cases.

Solves the cold-start problem: instead of designing test inputs in a vacuum,
extract the prompts a skill was ACTUALLY invoked on, plus the assistant's real
response, so step 1.5 (saturation pass) and step 2 (test inputs) are grounded
in production usage. Deterministic extraction only -- the agent still does the
judgment (relevance, expected_behavior rubric, golden-case selection).

Inspired by NousResearch/hermes-agent-self-evolution's external_importers.py
and kenn-io/agentsview's Hermes parser. Reads the REAL Hermes trace stores,
preferring the indexed one:
  - ~/.hermes/state.db (PREFERRED)  SQLite: `sessions` + `messages` (role,
    content, tool_calls, timestamp) + an FTS5 full-text index. This is the
    canonical store agentsview reads. Skill runs are stamped in the user turn
    as `[SYSTEM: The user has invoked the "<skill>"...]`, a ground-truth signal.
  - ~/.hermes/sessions/*.jsonl (FALLBACK)  flat transcripts, one JSON object
    per line; first line role=session_meta; user turns carry a "[Sender] " tag.
  - ~/.hermes/episodes/*.md          daily memory summaries; grepped for refs.

Usage:
    python mine_sessions.py --skill meta-ads-cli
    python mine_sessions.py --skill meta-ads-cli --max 40 --out candidates.jsonl
    python mine_sessions.py --skill meta-ads-cli --dry-run   # counts only, no file

Output: JSONL of candidate cases, one per line:
    {"task_input": "...", "assistant_response": "...", "source": "session:<file>",
     "timestamp": "...", "match": "why it matched"}

The agent reads this, scores relevance, writes expected_behavior rubrics, and
promotes production FAILURES to golden cases. Never trust these as finished
eval cases -- they are leads, not verdicts.
"""

import argparse
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

STATE_DB = Path.home() / ".hermes" / "state.db"
SESSIONS_DIR = Path.home() / ".hermes" / "sessions"
EPISODES_DIR = Path.home() / ".hermes" / "episodes"

# Hermes stamps every skill invocation with this prefix in the user turn (the
# lead-in word varies: "[SYSTEM:" or "[IMPORTANT:"). That's a deterministic
# ground-truth signal of "this skill actually ran" -- far stronger than keyword
# matching. Ported from agentsview's stripHermesSkillPrefix.
SKILL_INVOKE_RE = re.compile(r'^\[(?:SYSTEM|IMPORTANT): The user has invoked the "([^"]+)"')
SKILL_INSTR_MARKER = "The user has provided the following instruction alongside the skill invocation: "

# Secret patterns -- NEVER emit a candidate whose text matches. Anchored to
# known key formats to keep false positives off normal prose.
SECRET = re.compile(
    r"(sk-ant-api\S+|sk-or-v1-\S+|sk-[A-Za-z0-9]{20,}|ghp_\S+|ghu_\S+|gho_\S+"
    r"|xoxb-\S+|xapp-\S+|ntn_\S+|AKIA[0-9A-Z]{16}|Bearer\s+\S{20,}"
    r"|-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----"
    r"|(ANTHROPIC|OPENAI|OPENROUTER|SLACK_BOT|GITHUB|AWS_SECRET_ACCESS)[A-Z_]*_?(KEY|TOKEN)"
    r"|DATABASE_URL|\bpassword\s*[=:]\s*\S+|\bsecret\s*[=:]\s*\S+|\btoken\s*[=:]\s*\S{10,})",
    re.IGNORECASE,
)

# Strip the "[Sender Name] " prefix Hermes prepends to multi-user messages.
SENDER_PREFIX = re.compile(r"^\[[^\]]{1,40}\]\s+")

# System-injected pseudo-"user" turns that aren't real user tasks: compaction
# handoffs, gateway/system notes, model-switch notes, and bot-message echoes.
# These have role=user on disk but carry no skill-invocation signal.
BOILERPLATE = re.compile(
    r"^\s*(\[?(System note|Note|Replying to|OUT-OF-BAND)"
    r"|\[(SYSTEM|IMPORTANT): You are running"   # cron/scheduled-job wrapper (either lead-in)
    r"|\[(SYSTEM|IMPORTANT): Background process"  # background-process completion notice
    r"|\[Background process"
    r"|A code review was submitted"        # babysit-pr CI trigger, not a user ask
    r"|Earlier turns were compacted"
    r"|\[CONTEXT COMPACTION"
    r"|This is a handoff from a previous"
    r"|\[Image attached|\[Replying to)",
    re.IGNORECASE,
)

MIN_LEN = 12
MAX_INPUT = 2000
MAX_RESPONSE = 1500


def has_secret(text: str) -> bool:
    return bool(SECRET.search(text))


def clean_user(text: str) -> str:
    return SENDER_PREFIX.sub("", text).strip()


def flatten_content(content) -> str:
    """Content may be a string or a list of {type,text} blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for blk in content:
            if isinstance(blk, dict):
                parts.append(str(blk.get("text", blk.get("content", ""))))
            else:
                parts.append(str(blk))
        return " ".join(p for p in parts if p)
    return ""


def trigger_phrases(skill_text: str) -> list[str]:
    """Literal trigger phrases from the description's 'Use when:' clause.

    Skill descriptions encode the phrases a user actually types (e.g.
    "Use when: optimize this skill, make this skill better, run evals on").
    Matching a whole phrase is far higher-signal than single-keyword overlap,
    and unlike the folder name, users really say these.
    """
    m = re.search(r"---\n.*?description:\s*(.+?)\n(?:---|\w+:)", skill_text, re.DOTALL)
    desc = m.group(1) if m else skill_text[:1000]
    phrases = set()
    # "Use when: a, b, c" -> split on commas
    for uw in re.findall(r"[Uu]se when:?\s*(.+)", desc):
        for part in re.split(r"[,;]", uw):
            p = part.strip().strip('."\'').lower()
            if 3 < len(p) < 60 and len(p.split()) >= 2:
                phrases.add(p)
    # Quoted phrases anywhere in the description
    for q in re.findall(r'"([^"]{4,60})"', desc):
        q = q.strip().lower()
        if len(q.split()) >= 2:
            phrases.add(q)
    return sorted(phrases, key=len, reverse=True)


def relevance_terms(skill_name: str, skill_text: str) -> list[str]:
    """Terms whose presence in a turn suggests the skill is in play.

    Skill name (both hyphen and space forms), plus the highest-signal words
    from the skill's description line (first ~600 chars), minus stopwords.
    """
    terms = {skill_name.lower(), skill_name.lower().replace("-", " ")}
    stop = {
        "the", "and", "for", "with", "this", "that", "when", "use", "using",
        "your", "into", "from", "what", "which", "should", "would", "skill",
        "user", "used", "also", "via", "run", "runs", "make", "made",
        # generic agent-domain words that appear in most skills' descriptions
        # and cause cross-skill false positives (report/research/generate/etc.)
        "report", "reports", "research", "generate", "generated", "create",
        "created", "signal", "format", "output", "input", "session", "sessions",
        "agent", "prompt", "prompts", "score", "scores", "check", "checks",
        "data", "file", "files", "task", "tasks", "trigger", "triggers",
    }
    for w in re.findall(r"[a-z][a-z0-9\-]{4,}", skill_text[:600].lower()):
        if w not in stop:
            terms.add(w)
    return sorted(terms, key=len, reverse=True)


def match_reason(text: str, skill_name: str, terms: list[str], phrases: list[str]) -> tuple[str, str] | None:
    """Return (confidence, reason) or None. confidence in {"high","low"}."""
    tl = text.lower()
    name = skill_name.lower()
    if name in tl or name.replace("-", " ") in tl:
        return "high", f"names skill '{skill_name}'"
    for p in phrases:
        if p in tl:
            return "high", f"trigger phrase: '{p}'"
    hits = [t for t in terms if len(t.split()) == 1 and len(t) > 4 and t in tl]
    if len(hits) >= 2:
        return "low", "keyword overlap: " + ", ".join(hits[:4])
    return None


def next_assistant(rows: list[dict], i: int) -> str:
    """First assistant text after row i, stopping at the next user turn."""
    for j in range(i + 1, len(rows)):
        r = rows[j].get("role")
        if r == "assistant":
            txt = flatten_content(rows[j].get("content")).strip()
            if txt:
                return txt
        elif r == "user":
            break
    return ""


def strip_skill_prefix(content: str) -> tuple[str, str] | None:
    """If content is a Hermes skill-invocation turn, return (skill_name, user_instruction).

    Ported from agentsview's stripHermesSkillPrefix. Hermes injects the full
    skill body into the user turn; the real user ask (if any) follows an
    explicit instruction marker. Returns None if not a skill-invocation turn.
    """
    m = SKILL_INVOKE_RE.match(content)
    if not m:
        return None
    skill = m.group(1)
    instr = ""
    if SKILL_INSTR_MARKER in content:
        instr = content.split(SKILL_INSTR_MARKER, 1)[1]
        # Strip a trailing "[Runtime note: ...]" block if present.
        rt = instr.find("\n\n[Runtime note:")
        if rt >= 0:
            instr = instr[:rt]
        instr = instr.strip()
    return skill, instr


def mine_state_db(skill_name: str, phrases: list[str], max_cases: int) -> list[dict]:
    """Preferred source: the indexed state.db that agentsview reads.

    FTS-first (a plain `LIKE '[SYSTEM...%'` is a full scan of 470k large TEXT
    rows and times out on a multi-GB db). One FTS5 match on the skill name pulls
    every user turn that mentions it, then we classify each in Python:
      - starts with the invocation prefix -> explicit skill run (ground truth);
        extract the real user instruction from after the marker.
      - otherwise -> the user named the skill in an ordinary ask.
    Each candidate is paired with the assistant's next reply in the same session.
    """
    if not STATE_DB.exists():
        return []
    conn = sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    out: list[dict] = []

    def add(session_id, timestamp, confidence, reason, task_text):
        user = clean_user(task_text)
        if len(user) < MIN_LEN or has_secret(user) or BOILERPLATE.match(user):
            return
        resp = next_assistant_db(conn, session_id, timestamp)
        if resp and has_secret(resp):
            resp = "[redacted: response contained a secret pattern]"
        out.append({
            "task_input": user[:MAX_INPUT],
            "assistant_response": resp[:MAX_RESPONSE],
            "source": f"state.db:{session_id}",
            "timestamp": timestamp,
            "confidence": confidence,
            "match": reason,
        })

    try:
        rows = conn.execute(
            "SELECT m.session_id, m.content, m.timestamp "
            "FROM messages_fts f JOIN messages m ON m.id=f.rowid "
            "WHERE messages_fts MATCH ? AND m.role='user' "
            "ORDER BY m.timestamp DESC LIMIT ?",
            (f'"{skill_name}"', max_cases * 4),
        ).fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return []

    for row in rows:
        content = row["content"] or ""
        parsed = strip_skill_prefix(content)
        if parsed is not None:
            skill, instr = parsed
            # Invocation names may carry a category path (e.g. "memory/memory-gc").
            if skill.split("/")[-1] != skill_name or not instr:
                continue  # different skill's body, or no real user instruction to use
            add(row["session_id"], row["timestamp"], "high",
                f"explicit skill invocation of '{skill_name}'", instr)
        else:
            add(row["session_id"], row["timestamp"], "high",
                f"names skill '{skill_name}'", content)
        if len(out) >= max_cases:
            break
    conn.close()
    return out


def next_assistant_db(conn, session_id: str, after_ts) -> str:
    """First assistant reply after a timestamp in the same session, stopping at the next user turn."""
    for row in conn.execute(
        "SELECT role, content FROM messages WHERE session_id=? AND timestamp>? "
        "ORDER BY timestamp LIMIT 8",
        (session_id, after_ts),
    ):
        if row["role"] == "assistant" and (row["content"] or "").strip():
            return row["content"].strip()
        if row["role"] == "user":
            break
    return ""


def mine_sessions_jsonl(skill_name: str, terms: list[str], phrases: list[str], max_cases: int) -> list[dict]:
    """Fallback source: glob raw JSONL transcripts when state.db is absent."""
    if not SESSIONS_DIR.exists():
        return []
    out: list[dict] = []
    files = sorted(SESSIONS_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    for f in files:
        rows = []
        for line in f.read_text(errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("["):  # skip "[N more lines]" truncation markers
                continue
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(o, dict):
                rows.append(o)
        for i, row in enumerate(rows):
            if row.get("role") != "user":
                continue
            raw = flatten_content(row.get("content"))
            user = clean_user(raw)
            if len(user) < MIN_LEN or has_secret(user) or BOILERPLATE.match(user):
                continue
            why = match_reason(user, skill_name, terms, phrases)
            if not why:
                continue
            confidence, reason = why
            resp = next_assistant(rows, i)
            if resp and has_secret(resp):
                resp = "[redacted: response contained a secret pattern]"
            out.append({
                "task_input": user[:MAX_INPUT],
                "assistant_response": resp[:MAX_RESPONSE],
                "source": f"session:{f.name}",
                "timestamp": row.get("timestamp", ""),
                "confidence": confidence,
                "match": reason,
            })
            if len(out) >= max_cases:
                return out
    return out


def mine_episodes(skill_name: str, limit: int = 60) -> list[dict]:
    """Grep episode summaries for lines referencing the skill (context, not eval inputs).

    Capped and newest-first: episode files are dense, and a skill that doubles
    as a project name (e.g. cpe-research) can match thousands of lines. The
    agent wants a representative sample of recent references, not an exhaustive dump.
    """
    if not EPISODES_DIR.exists():
        return []
    out = []
    name = skill_name.lower()
    for f in sorted(EPISODES_DIR.glob("*.md"), reverse=True):
        for line in f.read_text(errors="ignore").splitlines():
            if name in line.lower() and not has_secret(line):
                out.append({"source": f"episode:{f.name}", "note": line.strip()[:400]})
                if len(out) >= limit:
                    return out
    return out


def dedup(cases: list[dict]) -> list[dict]:
    seen, keep = set(), []
    for c in cases:
        key = re.sub(r"\s+", " ", c["task_input"].lower())[:120]
        if key in seen:
            continue
        seen.add(key)
        keep.append(c)
    return keep


def load_skill_text(skill_name: str) -> str:
    base = Path.home() / ".hermes" / "skills"
    for pat in (skill_name, f"*/{skill_name}"):
        for d in base.glob(pat):
            sf = d / "SKILL.md"
            if sf.exists():
                return sf.read_text()
    raise FileNotFoundError(f"SKILL.md for '{skill_name}' not found under {base}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skill", required=True, help="Skill name (folder name under ~/.hermes/skills)")
    ap.add_argument("--max", type=int, default=40, help="Max session candidates (default 40)")
    ap.add_argument("--out", default=None, help="Output JSONL path (default: mined-<skill>.jsonl)")
    ap.add_argument("--dry-run", action="store_true", help="Print counts only, write nothing")
    args = ap.parse_args()

    skill_text = load_skill_text(args.skill)
    terms = relevance_terms(args.skill, skill_text)
    phrases = trigger_phrases(skill_text)

    # Prefer the indexed state.db (what agentsview reads). It's authoritative:
    # if it exists, trust its result rather than falling back to noisy JSONL
    # keyword-matching (a "0" usually means the skill only ran via cron, with no
    # genuine user ask to mine -- not that the data is missing).
    if STATE_DB.exists():
        source_label = "state.db"
        sessions = dedup(mine_state_db(args.skill, phrases, args.max))
    else:
        source_label = "jsonl (no state.db)"
        sessions = dedup(mine_sessions_jsonl(args.skill, terms, phrases, args.max))
    # High-confidence (names the skill) first; those are worth the agent's time.
    sessions.sort(key=lambda c: 0 if c["confidence"] == "high" else 1)
    episodes = mine_episodes(args.skill)

    conf = Counter(c["confidence"] for c in sessions)
    print(f"skill: {args.skill}   (source: {source_label})")
    print(f"session candidates: {len(sessions)}  ({conf.get('high',0)} high-confidence, {conf.get('low',0)} low)")
    print(f"episode references: {len(episodes)}")
    if sessions:
        print("\nsample task_inputs (high-confidence first):")
        for c in sessions[:6]:
            print(f"  - [{c['confidence']}] {c['task_input'][:90]}")

    if args.dry_run:
        print("\nDRY RUN -- nothing written.")
        return

    out = Path(args.out) if args.out else Path(f"mined-{args.skill}.jsonl")
    with out.open("w") as f:
        for c in sessions:
            f.write(json.dumps(c) + "\n")
    if episodes:
        with out.with_suffix(".episodes.jsonl").open("w") as f:
            for e in episodes:
                f.write(json.dumps(e) + "\n")
    print(f"\nwrote {len(sessions)} candidates -> {out}")
    if episodes:
        print(f"wrote {len(episodes)} episode notes -> {out.with_suffix('.episodes.jsonl')}")
    print("\nNext: agent reads these, scores relevance, writes expected_behavior rubrics,")
    print("and promotes production FAILURES to golden cases. They are leads, not verdicts.")


if __name__ == "__main__":
    main()
