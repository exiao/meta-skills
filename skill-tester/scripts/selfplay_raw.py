#!/usr/bin/env python3
"""Self-play every lesson with RAW blank subagents (no system prompt).

Faithful test of how a lesson runs when pasted into a bare Cursor/Claude chat:
the instructor is a model with NO system prompt, fed only the pasted lesson file;
the student is a separate blank model given a persona as its FIRST USER message.
Writes one transcript per lesson into test-output/<section>/NN-*.md for
build_transcripts.py.

Edit LESSONS (path to the lessons dir) and SECTIONS (section -> [lesson-number
prefixes]) for your course. Launch backgrounded (terminal background=true), poll
the log. See references/raw-blank-subagent-selfplay.md for the why.
"""
import anthropic, pathlib, re, concurrent.futures, traceback

ROOT = pathlib.Path(__file__).parent
LESSONS = pathlib.Path("EDIT_ME/lessons")  # <- absolute path to the lessons dir
OUT = ROOT / "test-output"
MODEL = "claude-opus-4-8"  # or read model.default from ~/.hermes/config.yaml
MAX_TURNS = 9

client = anthropic.Anthropic(base_url="http://127.0.0.1:18801", api_key="proxy")

SECTIONS = {
    "arc1": ["01", "02", "03"],
    "arc2": ["04", "05", "06", "07", "08", "09"],
    "arc3": ["10", "11", "12", "13"],
    "arc4": ["14", "15", "16", "17"],
    "arc5": ["18", "19", "20"],
}

STUDENT_PERSONA = (
    "You are role-playing a STUDENT taking an interactive AI course inside Cursor. "
    "You are a product manager who is fluent with ChatGPT and Claude, can install apps "
    "and run setup commands. You are the learner, NOT the teacher. React in good faith "
    "to what the instructor just said: when they demo, react briefly; when they offer "
    "multiple-choice options, pick one by letter; when they ask you to run something, "
    "paste a short plausible result. Occasionally hit a small realistic snag or ask one "
    "clarifying question. Keep each reply to 1-4 sentences. Never teach or narrate the "
    "lesson yourself."
)

def call(messages):
    # NO system param == no system prompt. An empty-string system is rejected (400).
    r = client.messages.create(model=MODEL, max_tokens=1100, messages=messages)
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
        "You are running inside Cursor. The following is a lesson file the user pasted "
        "for you to teach them interactively. Follow it EXACTLY: one step per message, "
        "keep messages short, DO the demo by narrating it, pause after each step, and use "
        "multiple-choice options where the lesson says to ask the student. Do not dump the "
        "whole lesson at once. Begin teaching now, starting with the first step.\n\n"
        "----- LESSON FILE -----\n" + lesson)}]
    stu_msgs = [{"role": "user", "content": STUDENT_PERSONA +
        "\n\nThe instructor will speak first. Wait for their message, then respond as the student."}]

    transcript = [f"# Lesson {int(num)}: {title}", "",
                  "_SYNTHETIC self-play. Instructor and student are both RAW models with NO system prompt._", ""]
    try:
        for _ in range(MAX_TURNS):
            instr = call(instr_msgs)
            transcript += [f"**INSTRUCTOR:** {instr}", ""]
            instr_msgs.append({"role": "assistant", "content": instr})
            stu_msgs.append({"role": "user", "content": f"[Instructor]: {instr}"})
            stu = call(stu_msgs)
            transcript += [f"**STUDENT:** {stu}", ""]
            stu_msgs.append({"role": "assistant", "content": stu})
            instr_msgs.append({"role": "user", "content": stu})
            # End ONLY on a real completion signal, not a mid-lesson "what just happened" aside.
            if re.search(r"🎉|share prompt|what next\?|you've completed|that completes", instr.lower()):
                break
    except Exception as e:
        transcript.append(f"\n_ERROR during run: {e}_")
        traceback.print_exc()
    return num, title, "\n".join(transcript)

def main():
    OUT.mkdir(exist_ok=True)
    jobs = [(sec, num) for sec, nums in SECTIONS.items() for num in nums]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(run_lesson, num): (sec, num) for sec, num in jobs}
        for fut in concurrent.futures.as_completed(futs):
            sec, num = futs[fut]
            n, title, body = fut.result()
            if body is None:
                print("SKIP", num); continue
            d = OUT / sec; d.mkdir(parents=True, exist_ok=True)
            (d / f"{find_lesson(num).stem}.md").write_text(body, encoding="utf-8")
            print(f"wrote {sec}/{find_lesson(num).stem}.md ({len(body)} chars)")
    print("done")

if __name__ == "__main__":
    main()
