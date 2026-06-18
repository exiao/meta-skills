#!/usr/bin/env python3
"""Regression tests for prune_pending.py.

Each test runs the script with HOME pointed at a tempdir so the real
~/.hermes tree is never touched.
"""
import os
import subprocess
import sys
import tempfile
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
            "MEMORY\t[2026-06-01][task] drop this transient task",
            "USER\t[2026-06-01][pref] keep this stable preference",
            "",
        ]))
        proc = run_script(home)
        out = pending.read_text(encoding="utf-8")
        check("uppercase parse returns 0", proc.returncode == 0)
        check("uppercase task target hard-dropped", "drop this transient task" not in out)
        check("uppercase user pref survives", "keep this stable preference" in out)

    print("\n[3] hyphenated project namespaces keep distinct roots")
    with tempfile.TemporaryDirectory(prefix="pp-test-") as d:
        home = Path(d)
        pending = make_pending(home, "\n".join([
            "memory\t[2026-06-01][proj:alpha-api] pipeline contract for API service",
            "memory\t[2026-06-01][proj:alpha-web] pipeline contract for web frontend",
            "memory\t[2026-06-01][proj:alpha-agent] pipeline contract for shared alpha sprawl A",
            "memory\t[2026-06-01][proj:alpha-wiki] pipeline contract for shared alpha sprawl B",
            "",
        ]))
        proc = run_script(home)
        out = pending.read_text(encoding="utf-8")
        check("hyphen namespace run returns 0", proc.returncode == 0)
        check("alpha-api survives", "proj:alpha-api" in out)
        check("alpha-web survives", "proj:alpha-web" in out)
        # Known sprawl suffixes still collapse, so only one alpha agent/wiki survivor remains.
        check("known sprawl suffixes still collapse", ("proj:alpha-agent" in out) != ("proj:alpha-wiki" in out))

    print(f"\n=== {PASS} passed, {FAIL} failed ===")
    return FAIL == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
