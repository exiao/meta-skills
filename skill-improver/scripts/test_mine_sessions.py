#!/usr/bin/env python3
"""Deterministic unit test for the JSONL fallback in mine_sessions.py.

Run: python3 test_mine_sessions.py   (stdlib only, no pytest required)

The crux: when ~/.hermes/state.db is absent, mine_sessions_jsonl used to keyword-match
raw user turns. A Hermes skill-invocation turn carries the INJECTED SKILL BODY, so a
turn that merely mentions the skill name matched and the truncated skill body was
written as `task_input` -- not a production user prompt, which silently invalidates
the generated eval set. The fallback must apply the same invocation parsing as
mine_state_db: emit the instruction after SKILL_INSTR_MARKER, and drop a DIFFERENT
skill's invocation entirely.
"""
import json, pathlib, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import mine_sessions
from mine_sessions import SKILL_INSTR_MARKER

FAILS = []


def check(name, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


SKILL = "meta-ads-cli"
BODY = ("This skill does many things. " * 200)[:3000]   # > MAX_INPUT, like a real body
REAL_ASK = "pause the retargeting campaign and report yesterday's spend"

TURNS = [
    # 1. This skill's invocation: real ask lives after the marker, body must not leak.
    {"role": "user", "content": f'[SYSTEM: The user has invoked the "{SKILL}" skill.]\n\n{BODY}\n\n{SKILL_INSTR_MARKER}{REAL_ASK}'},
    {"role": "assistant", "content": "Paused it; spend was $412."},
    # 2. A DIFFERENT skill's invocation whose body happens to name this skill.
    {"role": "user", "content": f'[SYSTEM: The user has invoked the "some-other-skill" skill.]\n\nUse {SKILL} when reporting. {BODY}'},
    {"role": "assistant", "content": "ok"},
    # 3. An ordinary user ask naming the skill: still mined, unchanged.
    {"role": "user", "content": f"can you run {SKILL} against the new account"},
    {"role": "assistant", "content": "done"},
]

with tempfile.TemporaryDirectory() as td:
    sessions = pathlib.Path(td) / "sessions"
    sessions.mkdir()
    (sessions / "s1.jsonl").write_text("\n".join(json.dumps(t) for t in TURNS))
    mine_sessions.SESSIONS_DIR = sessions

    terms = [SKILL, SKILL.replace("-", " ")]
    got = mine_sessions.mine_sessions_jsonl(SKILL, terms, phrases=[], max_cases=10)

inputs = [c["task_input"] for c in got]
check("invocation turn yields the real user instruction, not the skill body",
      REAL_ASK in inputs, f"got {inputs!r}")
check("no candidate is the injected skill body",
      not any(c["task_input"].startswith("This skill does many things") for c in got),
      f"got {inputs!r}")
check("another skill's invocation is dropped",
      not any("some-other-skill" in c["task_input"] for c in got)
      and not any(BODY[:40] in c["task_input"] for c in got),
      f"got {inputs!r}")
check("ordinary ask naming the skill is still mined",
      any("run meta-ads-cli against the new account" in i for i in inputs), f"got {inputs!r}")
check("invocation candidate is high-confidence with the invocation reason",
      any(c["confidence"] == "high" and "explicit skill invocation" in c["match"]
          for c in got if c["task_input"] == REAL_ASK), f"got {got!r}")

print()
if FAILS:
    print(f"RESULT: {len(FAILS)} FAILED -> {FAILS}")
    sys.exit(1)
print("RESULT: all assertions passed")
sys.exit(0)
