#!/usr/bin/env python3
"""Deterministic unit test for probe isolation in run_eval.py.

Run: python3 test_run_eval.py   (stdlib only, no pytest required; no API calls)

The crux: with `--num-workers > 1`, registering a probe skill PER WORKER puts
several identically-described skills in the same project's .claude/skills. Each
`claude -p` then sees indistinguishable probes and can invoke a sibling worker's
generated name, which the caller scores as not-triggered -- corrupting trigger
rates under the default batch configuration.

A stub `claude` on PATH stands in for the model: it lists the probe skills
visible in the project and invokes the LAST one (any visible probe is a legal
model choice), streaming the same stream-json shape the real detector parses.
With one shared probe every worker's invocation is unambiguous and the trigger
rate is 1.0; with a probe per worker it is not.
"""
import json, os, pathlib, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from scripts.run_eval import run_eval, registered_probe

FAILS = []


def check(name, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


STUB_CLAUDE = """#!/usr/bin/env python3
import json, pathlib, sys
skills = sorted(p.name for p in (pathlib.Path.cwd() / ".claude" / "skills").iterdir() if p.is_dir())
(pathlib.Path.cwd() / "probe-counts.log").open("a").write(f"{len(skills)}\\n")
chosen = skills[-1]          # any visible probe is a legal model choice
for ev in (
    {"type": "stream_event", "event": {"type": "content_block_start",
     "content_block": {"type": "tool_use", "name": "Skill"}}},
    {"type": "stream_event", "event": {"type": "content_block_delta",
     "delta": {"type": "input_json_delta", "partial_json": json.dumps({"skill": chosen})}}},
    {"type": "stream_event", "event": {"type": "content_block_stop"}},
):
    print(json.dumps(ev), flush=True)
"""

EVAL_SET = [{"query": f"query {i}", "should_trigger": True} for i in range(6)]

# Guarded: with spawn/forkserver start methods (POSIX default from 3.14) the
# pool's children re-run this module, which would re-enter run_eval.
if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        (root / ".claude" / "skills").mkdir(parents=True)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        stub = bin_dir / "claude"
        stub.write_text(STUB_CLAUDE)
        stub.chmod(0o755)
        os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"

        out = run_eval(EVAL_SET, "probe", "test description", num_workers=6,
                       timeout=30, project_root=root, runs_per_query=2)

        counts = {int(n) for n in (root / "probe-counts.log").read_text().split()}
        leftover = list((root / ".claude" / "skills").iterdir())

    check("exactly one probe skill is visible to every concurrent worker",
          counts == {1}, f"observed probe counts {sorted(counts)}")
    check("every worker's invocation is scored as triggered",
          all(r["trigger_rate"] == 1.0 for r in out["results"]),
          f"{out['summary']['passed']}/{out['summary']['total']} passed")
    check("the shared probe is removed after the pool drains",
          leftover == [], f"leftover {[p.name for p in leftover]}")

    # The probe directory exists only inside the context manager.
    with tempfile.TemporaryDirectory() as td2:
        root2 = pathlib.Path(td2)
        with registered_probe(root2, "probe", "desc") as name:
            inside = sorted(p.name for p in (root2 / ".claude" / "skills").iterdir())
        after = list((root2 / ".claude" / "skills").iterdir())
    check("registered_probe creates one named probe and cleans it up",
          inside == [name] and after == [], f"inside={inside} after={after}")

    print()
    if FAILS:
        print(f"RESULT: {len(FAILS)} FAILED -> {FAILS}")
        sys.exit(1)
    print("RESULT: all assertions passed")
    sys.exit(0)
