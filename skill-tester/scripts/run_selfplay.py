#!/usr/bin/env python3
"""Self-play every lesson with RAW blank subagents (NO system prompt).

The most faithful course test: each lesson is run by two direct model calls through
the local Anthropic proxy, neither carrying a system prompt — mirroring how the lesson
behaves when pasted into Cursor. Writes one transcript per lesson into
test-output/<section>/<slug>.md for build_transcripts.py.

Adapt: LESSONS path, SECTIONS map, STUDENT_PERSONA, MODEL. "No system prompt" means
OMIT system= entirely (system="" is rejected with a 400). Run backgrounded; a 20-lesson
run exceeds the 60s shell cap. See references/raw-blank-subagent-selfplay.md.
"""
import anthropic, pathlib, re, concurrent.futures, traceback

ROOT = pathlib.Path(__file__).parent
LESSONS = pathlib.Path("/ABS/PATH/TO/lessons")   # EDIT
OUT = ROOT / "test-output"
MODEL = "claude-opus-4-8"                          # EDIT: model.default from ~/.hermes/config.yaml
MAX_TURNS = 10  # +1 if lessons have a Step 0 orientation beat

client = anthropic.Anthropic(base_url="http://127.0.0.1:18801", api_key="proxy")

SECTIONS = {                                       # EDIT: section -> lesson-number prefixes
    "arc1": ["01", "02", "03"],
    "arc2": ["04", "05", "06", "07", "08", "09"],
    "arc3": ["10", "11", "12", "13"],
    "arc4": ["14", "15", "16", "17"],
    "arc5": ["18", "19", "20"],
}

STUDENT_PERSONA = (                                # EDIT to the real audience (assume competence)
    "You are role-playing a STUDENT taking an interactive AI course inside Cursor. "
    "You are a product manager fluent with ChatGPT and Claude who can install apps and run "
    "setup commands. You are the learner, NOT the teacher. React in good faith: when the "
    "instructor demos, react briefly; when they offer multiple-choice options, pick one by "
    "letter; when they ask you to run something, paste a short plausible result. Occasionally "
    "hit a small realistic snag or ask one clarifier. Keep replies 1-4 sentences. Never teach."
)

def call(messages):
    r = client.messages.create(model=MODEL, max_tokens=1100, messages=messages)  # NOTE: no system=
    return "".join(b.text for b in r.content if b.type == "text").strip()

def find_lesson(num):
    hits = sorted(LESSONS.glob(f"{num}-*.md"))
    return hits[0] if hits else None

def run_lesson(num):
    path = find_lesson(num)
    if not path:
        return num, None, None
    lesson = path.read_text(encoding="utf-8")
    title = lesson.splitlines()[0].lstrip("# ").strip()
    instr_msgs = [{"role": "user", "content": (
        "You are running inside Cursor. The following is a lesson file the user pasted for you "
        "to teach them interactively. Follow it EXACTLY: one step per message, keep messages "
        "short, DO the demo by narrating it, pause after each step, use multiple-choice where the "
        "lesson says to ask the student. Do not dump the whole lesson at once. Begin now with the "
        "first step.\n\n----- LESSON FILE -----\n" + lesson)}]
    stu_msgs = [{"role": "user", "content": STUDENT_PERSONA +
                 "\n\nThe instructor speaks first. Wait for their message, then respond as the student."}]
    t = [f"# Lesson {int(num)}: {title}", "",
         "_SYNTHETIC self-play. Instructor and student are both RAW models with NO system prompt._", ""]
    try:
        for _ in range(MAX_TURNS):
            instr = call(instr_msgs)
            t += [f"**INSTRUCTOR:** {instr}", ""]
            instr_msgs.append({"role": "assistant", "content": instr})
            stu_msgs.append({"role": "user", "content": f"[Instructor]: {instr}"})
            stu = call(stu_msgs)
            t += [f"**STUDENT:** {stu}", ""]
            stu_msgs.append({"role": "assistant", "content": stu})
            instr_msgs.append({"role": "user", "content": stu})
            # End ONLY on the real closing beat, never a mid-lesson "notice what just happened".
            if re.search(r"🎉|share prompt|what next\?|you've completed|that completes", instr.lower()):
                break
    except Exception as e:
        t.append(f"\n_ERROR during run: {e}_"); traceback.print_exc()
    return num, title, "\n".join(t)

def main():
    OUT.mkdir(exist_ok=True)
    jobs = [(s, n) for s, nums in SECTIONS.items() for n in nums]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(run_lesson, n): (s, n) for s, n in jobs}
        for fut in concurrent.futures.as_completed(futs):
            s, n = futs[fut]
            _, title, body = fut.result()
            if not body:
                print("SKIP", n); continue
            d = OUT / s; d.mkdir(parents=True, exist_ok=True)
            (d / f"{find_lesson(n).stem}.md").write_text(body, encoding="utf-8")
            print(f"wrote {s}/{find_lesson(n).stem}.md ({len(body)} chars)")
    print("done")

if __name__ == "__main__":
    main()
