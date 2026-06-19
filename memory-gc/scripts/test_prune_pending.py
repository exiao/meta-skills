#!/usr/bin/env python3
"""Regression tests for prune_pending.py.

Each test runs the script with HOME pointed at a tempdir so the real
~/.hermes tree is never touched.
"""
import os
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
SCRIPT = HERE / "prune_pending.py"

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}")


def run_script(home: Path):
    env = os.environ.copy()
    env["HOME"] = str(home)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def make_pending(home: Path, body: str) -> Path:
    pending = home / ".hermes" / "episodes" / ".pending.md"
    pending.parent.mkdir(parents=True, exist_ok=True)
    pending.write_text(body, encoding="utf-8")
    return pending


def run():
    print("\n[1] missing pending file exits cleanly")
    with tempfile.TemporaryDirectory(prefix="pp-test-") as d:
        home = Path(d)
        proc = run_script(home)
        check("missing pending returns 0", proc.returncode == 0)
        check("missing pending explains noop", "nothing to prune" in proc.stdout.lower())

    print("\n[2] uppercase MEMORY/USER targets are parsed")
    with tempfile.TemporaryDirectory(prefix="pp-test-") as d:
        home = Path(d)
        pending = make_pending(home, "\n".join([
            "MEMORY\t[2026-06-01][tmp] drop this transient tmp",
            "USER\t[2026-06-01][pref] keep this stable preference",
            "",
        ]))
        proc = run_script(home)
        out = pending.read_text(encoding="utf-8")
        check("uppercase parse returns 0", proc.returncode == 0)
        check("uppercase tmp target hard-dropped", "drop this transient tmp" not in out)
        check("uppercase user pref survives", "keep this stable preference" in out)

    print("\n[3] hyphenated project namespaces keep distinct roots")
    with tempfile.TemporaryDirectory(prefix="pp-test-") as d:
        home = Path(d)
        pending = make_pending(home, "\n".join([
            "memory\t[2026-06-01][proj:alpha-api] pipeline contract for API service",
            "memory\t[2026-06-01][proj:alpha-web] pipeline contract for web frontend",
            "memory\t[2026-06-01][proj:alpha-agent] pipeline contract for shared alpha sprawl",
            "memory\t[2026-06-01][proj:alpha-wiki] pipeline contract for shared alpha sprawl",
            "",
        ]))
        proc = run_script(home)
        out = pending.read_text(encoding="utf-8")
        check("hyphen namespace run returns 0", proc.returncode == 0)
        check("alpha-api survives", "proj:alpha-api" in out)
        check("alpha-web survives", "proj:alpha-web" in out)
        # Known sprawl suffixes still collapse, so only one alpha agent/wiki survivor remains.
        check("known sprawl suffixes still collapse", ("proj:alpha-agent" in out) != ("proj:alpha-wiki" in out))

    print("\n[4] durable env facts survive pending prune")
    with tempfile.TemporaryDirectory(prefix="pp-test-") as d:
        home = Path(d)
        pending = make_pending(home, "\n".join([
            "memory\t[2026-06-01][env] production API host moved to us-east-2",
            "memory\t[2026-06-01][fact] keep this stable architecture fact",
            "",
        ]))
        proc = run_script(home)
        out = pending.read_text(encoding="utf-8")
        check("env prune run returns 0", proc.returncode == 0)
        check("durable env fact survives", "production API host moved" in out)

    print("\n[5] active pending tasks survive until review window")
    with tempfile.TemporaryDirectory(prefix="pp-test-") as d:
        home = Path(d)
        today = date.today().isoformat()
        old = (date.today() - timedelta(days=30)).isoformat()
        pending = make_pending(home, "\n".join([
            f"memory\t[{today}][task] follow up with customer about beta invite",
            f"memory\t[{old}][task] stale follow-up from last month",
            "",
        ]))
        proc = run_script(home)
        out = pending.read_text(encoding="utf-8")
        check("task review-window run returns 0", proc.returncode == 0)
        check("fresh task survives pending prune", "follow up with customer" in out)
        check("stale task is dropped after threshold", "stale follow-up" not in out)

    print("\n[6] non-project facts with shared topic words stay distinct")
    with tempfile.TemporaryDirectory(prefix="pp-test-") as d:
        home = Path(d)
        pending = make_pending(home, "\n".join([
            "memory\t[2026-06-01][fact] auth token rotation moved to weekly automation",
            "memory\t[2026-06-01][fact] auth bearer-cookie behavior changed for web clients",
            "",
        ]))
        proc = run_script(home)
        out = pending.read_text(encoding="utf-8")
        check("non-project shared topic run returns 0", proc.returncode == 0)
        check("auth token fact survives", "auth token rotation" in out)
        check("bearer-cookie fact survives", "bearer-cookie behavior" in out)

    print("\n[7] distinct same-project general facts stay distinct")
    with tempfile.TemporaryDirectory(prefix="pp-test-") as d:
        home = Path(d)
        pending = make_pending(home, "\n".join([
            "memory\t[2026-06-01][proj:alpha] repo uses pnpm workspaces",
            "memory\t[2026-06-01][proj:alpha] customer data lives in Supabase",
            "",
        ]))
        proc = run_script(home)
        out = pending.read_text(encoding="utf-8")
        check("same-project general facts run returns 0", proc.returncode == 0)
        check("workspace fact survives", "pnpm workspaces" in out)
        check("supabase fact survives", "Supabase" in out)

    print("\n[8] active tasks beginning with complete survive review window")
    with tempfile.TemporaryDirectory(prefix="pp-test-") as d:
        home = Path(d)
        today = date.today().isoformat()
        pending = make_pending(home, "\n".join([
            f"memory\t[{today}][task] complete auth migration next week",
            f"memory\t[{today}][task] completed auth migration yesterday",
            "",
        ]))
        proc = run_script(home)
        out = pending.read_text(encoding="utf-8")
        check("complete-prefix task run returns 0", proc.returncode == 0)
        check("imperative complete task survives", "complete auth migration next week" in out)
        check("past-tense completed task drops", "completed auth migration yesterday" not in out)

    print("\n[9] fresh tmp entries survive their seven-day window")
    with tempfile.TemporaryDirectory(prefix="pp-test-") as d:
        home = Path(d)
        today = date.today().isoformat()
        old = (date.today() - timedelta(days=8)).isoformat()
        pending = make_pending(home, "\n".join([
            f"memory\t[{today}][tmp] keep same-day scratch note for triage",
            f"memory\t[{old}][tmp] drop expired scratch note",
            "",
        ]))
        proc = run_script(home)
        out = pending.read_text(encoding="utf-8")
        check("tmp review-window run returns 0", proc.returncode == 0)
        check("fresh tmp survives", "same-day scratch note" in out)
        check("expired tmp drops", "expired scratch note" not in out)

    print("\n[10] distinct preferences with ui substrings or tools stay distinct")
    with tempfile.TemporaryDirectory(prefix="pp-test-") as d:
        home = Path(d)
        pending = make_pending(home, "\n".join([
            "user\t[2026-06-01][pref] prefer quiet status updates after deploys",
            "user\t[2026-06-01][pref] SuiteScript changes should be summarized separately",
            "user\t[2026-06-01][pref] prefer CLI tool examples over screenshots",
            "",
        ]))
        proc = run_script(home)
        out = pending.read_text(encoding="utf-8")
        check("preference substring run returns 0", proc.returncode == 0)
        check("quiet preference survives", "quiet status updates" in out)
        check("SuiteScript preference survives", "SuiteScript changes" in out)
        check("tool preference survives", "CLI tool examples" in out)

    print("\n[11] distinct memory rules are not collapsed")
    with tempfile.TemporaryDirectory(prefix="pp-test-") as d:
        home = Path(d)
        pending = make_pending(home, "\n".join([
            "memory\t[2026-06-01][rule] never delete memory safety rails during GC",
            "memory\t[2026-06-01][rule] memory writes must archive discarded pending rows",
            "",
        ]))
        proc = run_script(home)
        out = pending.read_text(encoding="utf-8")
        check("memory-rule run returns 0", proc.returncode == 0)
        check("safety rail rule survives", "never delete memory safety" in out)
        check("archive rule survives", "archive discarded pending rows" in out)

    print("\n[12] same-project recognized-topic facts stay distinct")
    with tempfile.TemporaryDirectory(prefix="pp-test-") as d:
        home = Path(d)
        pending = make_pending(home, "\n".join([
            "memory\t[2026-06-01][proj:alpha] auth uses Cognito user pools",
            "memory\t[2026-06-01][proj:alpha] bearer cookies expire after 12 hours",
            "",
        ]))
        proc = run_script(home)
        out = pending.read_text(encoding="utf-8")
        check("project auth fact run returns 0", proc.returncode == 0)
        check("Cognito auth fact survives", "auth uses Cognito" in out)
        check("bearer cookie fact survives", "bearer cookies expire" in out)

    print("\n[13] pruned rows are archived to gc log")
    with tempfile.TemporaryDirectory(prefix="pp-test-") as d:
        home = Path(d)
        old = (date.today() - timedelta(days=8)).isoformat()
        pending = make_pending(home, "\n".join([
            "memory\t[2026-06-01][proj:alpha-agent] duplicate operational fact",
            "memory\t[2026-06-01][proj:alpha-wiki] duplicate operational fact",
            f"memory\t[{old}][tmp] expired scratch note should be recoverable",
            "",
        ]))
        gc_log = pending.parent / ".gc.log"
        proc = run_script(home)
        log = gc_log.read_text(encoding="utf-8") if gc_log.exists() else ""
        check("archive run returns 0", proc.returncode == 0)
        check("semantic duplicate archived", "duplicate operational fact" in log)
        check("hard-dropped tmp archived", "expired scratch note should be recoverable" in log)

    print(f"\n=== {PASS} passed, {FAIL} failed ===")
    return FAIL == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
