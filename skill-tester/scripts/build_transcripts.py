#!/usr/bin/env python3
"""Build the lesson-transcripts page from per-arc self-play transcript md files.
Eric's warm editorial visual identity (parchment + EB Garamond + terracotta), NOT
dark mode. Collapsible per-lesson, grouped by arc. Edit ARCS and the page metadata.

Run this from the directory that contains test-output/ (paths resolve relative to
the script's own location, so keep it next to test-output/).
"""
import re, html, pathlib

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "test-output"

ARCS = [
    ("Arc 1 — First Contact", "arc1", "Lessons 1–4: get hands on the agent for the first time."),
    ("Arc 2 — Get AI to Do Work for Me", "arc2", "Lessons 5–8: atomic tools, files, memory, prototyping loops."),
    ("Arc 3 — Environments for Long-Running Tasks", "arc3", "Lessons 9–12: the harness, skills, MCP, the command line."),
    ("Arc 4 — Create Your Personal OS", "arc4", "Lessons 13–16: context, retrieval, a daily OS, your own voice."),
    ("Arc 5 — Build True AI Product Sense", "arc5", "Lessons 17–20: multi-agent, evals, OpenClaw, make it yours."),
]

def md_inline(s):
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    s = re.sub(r"^&gt; (.*)$", r"<span class='bq'>\1</span>", s)
    return s

def render_md(text):
    """Minimal markdown -> HTML for the transcript bodies.

    Speaker turns wrap CONSECUTIVE lines of the same speaker in ONE bubble. The
    naive version wrapped only the **INSTRUCTOR:** line and let follow-on lines
    (explanations, lists, code) render as top-level <p>, breaking the bubble.
    Keep the turn_open/close_turn machinery — gemini-code-assist flagged the
    single-line version as a real fidelity bug (exiao/skills#158).
    """
    out, in_code, in_ul = [], False, False
    turn_open = False

    def close_turn():
        nonlocal turn_open
        if turn_open:
            out.append("</div>"); turn_open = False

    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if line.strip().startswith("```"):
            if in_code:
                out.append("</pre>"); in_code = False
            else:
                if in_ul: out.append("</ul>"); in_ul = False
                out.append("<pre>"); in_code = True
            continue
        if in_code:
            out.append(html.escape(line)); continue
        if not line.strip():
            if in_ul: out.append("</ul>"); in_ul = False
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            if in_ul: out.append("</ul>"); in_ul = False
            close_turn()
            lvl = min(len(m.group(1)), 4)
            out.append(f"<h{lvl+2 if lvl>1 else 4}>{md_inline(m.group(2))}</h{lvl+2 if lvl>1 else 4}>")
            continue
        if line.strip() in ("---", "***"):
            if in_ul: out.append("</ul>"); in_ul = False
            close_turn()
            out.append("<hr>"); continue
        m = re.match(r"^\s*[-*]\s+(.*)", line)
        if m:
            if not in_ul: out.append("<ul>"); in_ul = True
            out.append(f"<li>{md_inline(m.group(1))}</li>"); continue
        if in_ul: out.append("</ul>"); in_ul = False
        # speaker turns
        sm = re.match(r"^\*\*(Claude|Instructor|INSTRUCTOR|Student[^:]*|STUDENT[^:]*)[:：]\*\*\s*(.*)", line)
        if sm:
            who = sm.group(1)
            cls = "ins" if re.search(r"claude|instr", who, re.I) else "stu"
            close_turn()
            out.append(f"<div class='turn {cls}'><span class='who'>{html.escape(who)}</span> {md_inline(sm.group(2))}")
            turn_open = True
            continue
        if turn_open:
            out.append(f"<br>{md_inline(line)}")
        else:
            out.append(f"<p>{md_inline(line)}</p>")
    if in_code: out.append("</pre>")
    if in_ul: out.append("</ul>")
    close_turn()
    return "\n".join(out)

cards = []
total = 0
for arc_title, arc_dir, arc_desc in ARCS:
    files = sorted((OUT / arc_dir).glob("*.md"))
    inner = []
    for f in files:
        total += 1
        text = f.read_text(encoding="utf-8")
        # pull lesson title from first heading
        mt = re.search(r"^#\s+(.*)", text, re.M)
        title = mt.group(1).strip() if mt else f.stem
        title = re.sub(r"^Self-Play Transcript\s*[—-]\s*", "", title)
        body = render_md(text)
        inner.append(f"""<details class="lesson"><summary><span class="lnum">{f.stem.split('-')[0]}</span> {html.escape(title)}</summary>
<div class="body">{body}</div></details>""")
    cards.append(f"""<h2>{html.escape(arc_title)}</h2>
<p class="arcdesc">{html.escape(arc_desc)}</p>
{''.join(inner)}""")

PAGE = f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>APS Course — Full Lesson Transcripts (Synthetic)</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{{--bg:#f5f4ed;--surface:#faf9f5;--ink:#141413;--ink2:#4d4c48;--muted:#5e5d59;--faint:#87867f;
--line:#f0eee6;--line2:#e8e6dc;--accent:#c96442;--accent2:#d97757;--marker:#f3d9b0;--error:#b53333;
--serif:'EB Garamond',Georgia,serif;--sans:'General Sans',system-ui,-apple-system,'Segoe UI',sans-serif;
--mono:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,monospace}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.6 var(--sans);-webkit-font-smoothing:antialiased}}
.wrap{{max-width:820px;margin:0 auto;padding:56px 24px 96px}}
.kick{{color:var(--accent);font-weight:500;letter-spacing:.1em;text-transform:uppercase;font-size:12px;font-family:var(--sans)}}
h1{{font-family:var(--serif);font-weight:500;font-size:52px;line-height:1.1;margin:10px 0 8px;letter-spacing:-.01em}}
.sub{{color:var(--muted);font-size:18px;margin:0 0 24px}}
.warn{{background:var(--surface);border:1px solid var(--line2);border-left:3px solid var(--accent);border-radius:8px;
padding:16px 18px;margin:20px 0 10px;font-size:15px;color:var(--ink2)}}
.warn b{{color:var(--ink);font-weight:600}}
.chips{{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0}}
.chip{{background:var(--surface);border:1px solid var(--line2);border-radius:999px;padding:5px 13px;font-size:13px;color:var(--muted)}}
.chip b{{color:var(--ink);font-weight:600}}
h2{{font-family:var(--serif);font-weight:500;font-size:30px;letter-spacing:-.01em;color:var(--ink);
margin:48px 0 4px;padding-bottom:10px;border-bottom:1px solid var(--line2)}}
.arcdesc{{color:var(--faint);font-size:15px;margin:0 0 16px}}
details.lesson{{background:var(--surface);border:1px solid var(--line2);border-radius:8px;margin:10px 0;overflow:hidden;
box-shadow:rgba(0,0,0,0.04) 0px 2px 12px}}
details.lesson summary{{cursor:pointer;padding:16px 20px;font-family:var(--serif);font-size:21px;font-weight:500;
list-style:none;display:flex;align-items:center;gap:12px;color:var(--ink)}}
details.lesson summary::-webkit-details-marker{{display:none}}
details.lesson summary::after{{content:"+";margin-left:auto;color:var(--faint);font-weight:400;font-size:22px;font-family:var(--sans)}}
details.lesson[open] summary::after{{content:"–"}}
details.lesson[open] summary{{border-bottom:1px solid var(--line)}}
.lnum{{display:inline-flex;min-width:28px;height:28px;align-items:center;justify-content:center;
background:#f3e6e0;border:1px solid #e6cfc5;border-radius:7px;font-size:13px;color:var(--accent);font-weight:600;font-family:var(--sans)}}
.body{{padding:10px 22px 20px}}
.body p{{margin:10px 0}}
.turn{{padding:10px 14px;border-radius:8px;margin:9px 0}}
.turn.ins{{background:#f3ede4;border:1px solid var(--line2)}}
.turn.stu{{background:#faf2ee;border:1px solid #f0ddd4}}
.who{{display:inline-block;font-size:11px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;margin-right:6px;font-family:var(--sans)}}
.turn.ins .who{{color:var(--ink2)}} .turn.stu .who{{color:var(--accent)}}
.bq{{display:block;border-left:3px solid var(--line2);padding:2px 14px;color:var(--muted);margin:4px 0;font-style:italic}}
pre{{background:#faf8f2;border:1px solid var(--line2);border-radius:8px;padding:13px 15px;overflow:auto;
font:13.5px/1.55 var(--mono);color:#2a2a28;white-space:pre-wrap;word-break:break-word}}
code{{background:#f0ece2;border:1px solid var(--line2);border-radius:5px;padding:1px 6px;font-size:13px;
font-family:var(--mono);color:#5a3d33;overflow-wrap:anywhere}}
hr{{border:0;border-top:1px solid var(--line2);margin:14px 0}}
h4,h5,h6{{font-family:var(--serif);font-weight:500;margin:18px 0 6px;font-size:18px;letter-spacing:-.005em;color:var(--ink)}}
.body ul{{margin:8px 0;padding-left:20px}} .body li{{margin:5px 0}}
.foot{{color:var(--faint);font-size:13px;margin-top:48px;border-top:1px solid var(--line2);padding-top:18px}}
</style></head><body><div class="wrap">
<div class="kick">AI Product Sense Course · QA</div>
<h1>Full Lesson Transcripts</h1>
<p class="sub">Self-play walkthroughs of all 20 lessons, end to end. Raw output.</p>
<div class="warn"><b>Synthetic.</b> These are simulated sessions: an agent plays both the instructor (following each lesson's script) and a calibrated student persona (a ChatGPT/Claude-literate PM). No real student produced these. They show how each lesson runs turn by turn and where it snags.</div>
<div class="chips"><span class="chip"><b>{total}</b> lessons</span><span class="chip"><b>5</b> capability arcs</span><span class="chip">audience: <b>AI-literate PM</b></span></div>
{''.join(cards)}
<div class="foot">Generated by self-play QA. Each lesson ends with a "where it snagged" note.</div>
</div></body></html>"""

(ROOT / "index.html").write_text(PAGE, encoding="utf-8")
print(f"wrote index.html — {total} lessons, {len(PAGE)} bytes")
if total == 0:
    print("WARNING: no transcripts found. Check ARCS and that test-output/ "
          "holds the expected arcN/*.md files next to this script.")
