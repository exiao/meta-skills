#!/usr/bin/env python3
"""Check reference-link health across the whole skills tree.

Catches the two decay patterns that make a skill silently useless:

  DANGLING  SKILL.md points at references/<file>.md that exists nowhere
            (not in its own references/, not in any sibling skill).
            The agent follows the pointer and gets nothing.

  ORPHANED  A references/*.md file that SKILL.md never points to.
            Unreachable unless the agent greps for it by luck. Above
            ~40% orphan rate the skill has stopped being a router.

Cross-skill pointers are legitimate here: a SKILL.md may point at a
reference owned by a sibling skill. Those resolve and are NOT dangling.

Usage
-----
    python3 check_reference_health.py                # whole tree
    python3 check_reference_health.py --orphans      # include orphan report
    python3 check_reference_health.py <skill-dir>    # one skill

Exit code 1 when any dangling pointer is found, so it can gate a commit.
"""
import os
import re
import sys
import glob

SKILLS = os.path.expanduser("~/.hermes/skills")
SKIP = ("/node_modules/", "/.archive/", "/.curator_backups/")
# Illustrative or glob-pattern filenames that are prose, not real pointers.
IGNORE = {"foo.md", "bar.md", "example.md"}
REF_RE = re.compile(r"references/([a-zA-Z0-9._-]+\.md)")


def skill_files(target=None):
    root = target or SKILLS
    for p in glob.glob(os.path.join(root, "**", "SKILL.md"), recursive=True):
        if not any(s in p for s in SKIP):
            yield p


def all_reference_names():
    names = set()
    for p in glob.glob(os.path.join(SKILLS, "**", "references", "*.md"), recursive=True):
        if not any(s in p for s in SKIP):
            names.add(os.path.basename(p))
    return names


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    show_orphans = "--orphans" in sys.argv
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return 0

    known = all_reference_names()
    dangling, orphaned = [], []

    for path in skill_files(args[0] if args else None):
        d = os.path.dirname(path)
        text = open(path, errors="replace").read()
        pointed = {f for f in REF_RE.findall(text) if f not in IGNORE and "YYYY" not in f}

        for f in sorted(pointed):
            if os.path.exists(os.path.join(d, "references", f)):
                continue
            if f in known:
                continue  # valid cross-skill pointer
            dangling.append((os.path.relpath(path, SKILLS), f))

        on_disk = {os.path.basename(x) for x in glob.glob(os.path.join(d, "references", "*.md"))}
        if on_disk:
            orphans = on_disk - set(REF_RE.findall(text))
            if len(orphans) >= max(2, 0.4 * len(on_disk)):
                orphaned.append((os.path.relpath(path, SKILLS), len(orphans), len(on_disk)))

    print(f"DANGLING pointers (target exists nowhere): {len(dangling)}")
    for skill, f in dangling:
        print(f"  {skill} -> references/{f}")

    if show_orphans:
        print(f"\nORPHAN-HEAVY skills (>=40% references unreachable): {len(orphaned)}")
        for skill, n, tot in sorted(orphaned, key=lambda x: -x[1]):
            print(f"  {skill}: {n}/{tot} unreachable")

    return 1 if dangling else 0


if __name__ == "__main__":
    raise SystemExit(main())
