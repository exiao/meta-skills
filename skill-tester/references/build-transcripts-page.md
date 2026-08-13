# Build the transcripts page

`build_transcripts.py` converts a `test-output/<section>/*.md` tree of self-play
transcripts into one HTML page: collapsible per lesson, grouped by section, with a
SYNTHETIC warning header. It does minimal markdown rendering and styles
`**INSTRUCTOR:**` / `**STUDENT:**` turns as distinct bubbles. The canonical runnable
copy is `scripts/build_transcripts.py`; this file is the explainer + the durable
review lessons.

## Layout it expects
```
<worktree>/
  build_transcripts.py
  test-output/
    section1/01-*.md 02-*.md 03-*.md 04-*.md
    section2/05-*.md ... etc
```
Edit the `SECTIONS` list at the top (title, dir, one-line description) to match the
course. Paths resolve relative to the SCRIPT's own location (`Path(__file__).parent`),
so keep the script next to its `test-output/`. This is deliberate: `Path.cwd()` would
silently write `index.html` wherever you launched from. (Declined that change in
exiao/skills#158 for exactly this reason.)

## Run
```
python3 build_transcripts.py     # writes index.html
cp index.html 200.html           # SPA fallback for static hosts that need it
# deploy index.html + 200.html to any static host (surge, etc.)
```
Verify the live page with a real rendered screenshot (BrowserVision), not just a DOM
grep; static CDNs can 504 on the first cold hit, retry after a few seconds.

## Review lessons (baked into the script — keep them when you copy it)
From the exiao/skills#158 + meta-skills#3 review of this build script. Real
correctness/legibility fixes, not style nits:

1. **Multi-line speaker turns must stay in ONE bubble.** A per-line
   `<p class='turn'>` wraps only the first line; follow-on sentences, lists, or code
   under that speaker render as bare top-level paragraphs and break the "who is
   talking" cue. Track an open turn (a `turn_open` flag + `close_turn()` helper) and
   close it on the next heading / `hr` / speaker. Subsequent lines join with `<br>`.
2. **Always pass `encoding="utf-8"` to `read_text`/`write_text`.** Transcripts carry
   smart quotes, emoji, and full-width colons; Windows defaults to CP1252 and throws
   `UnicodeDecodeError` without the explicit encoding.
3. **Warn when `total == 0`.** A silent "wrote index.html — 0 lessons" hides a wrong
   `SECTIONS` config or a misplaced `test-output/`. Print a WARNING so the author knows.
4. **Docstring must name the REAL config vars** (`TITLE/HEADLINE/KICKER/SUBHEAD/AUDIENCE`,
   the sections list, the `:root` tokens). A docstring pointing at a `META` var that
   doesn't exist sends an editor hunting for a symbol that isn't there.

## Design tokens (Eric's visual identity — NOT dark mode)
Eric rejected the dark aps-testing-report look for his own deploys. Use his warm
editorial palette when building for HIM:
```
--bg:#f5f4ed (parchment) --surface:#faf9f5 (ivory) --ink:#141413 --ink2:#4d4c48
--muted:#5e5d59 --faint:#87867f --line:#f0eee6 --line2:#e8e6dc
--accent:#c96442 (terracotta) --accent2:#d97757 (coral) --marker:#f3d9b0
--serif:'EB Garamond' (headlines, lesson titles, h2-h6, 500 weight)
--sans:'General Sans',system-ui (body, labels, badges)
--mono:'JetBrains Mono' (code)
```
Load EB Garamond + JetBrains Mono via Google Fonts; General Sans falls back to
system-ui. 820px max width. Headlines serif weight 500 (no bold serif). Instructor
turns warm-tan bubble, student turns coral-tinted bubble. Each lesson is a `<details>`
accordion with a terracotta `+`/`–` marker and a terracotta number badge. Code/pre use
`white-space:pre-wrap; word-break:break-word` and inline code uses
`overflow-wrap:anywhere` so long GitHub URLs wrap on mobile instead of forcing
horizontal scroll. (For the PUBLIC skill copy, ship a neutral default theme and tell the
user to swap in their own `:root` tokens — don't hardcode a personal identity.)

## The render_md core (the part the review changed)
```python
def render_md(text):
    # Wrap CONSECUTIVE lines under one **INSTRUCTOR:** / **STUDENT:** in a single
    # bubble. A bare per-line bubble drops multi-line turns outside the styled block.
    out, in_code, in_ul = [], False, False
    turn_open = False
    def close_turn():
        nonlocal turn_open
        if turn_open:
            out.append("</div>"); turn_open = False
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if line.strip().startswith("```"):
            if in_code: out.append("</pre>"); in_code = False
            else:
                if in_ul: out.append("</ul>"); in_ul = False
                out.append("<pre>"); in_code = True
            continue
        if in_code: out.append(html.escape(line)); continue
        if not line.strip():
            if in_ul: out.append("</ul>"); in_ul = False
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            if in_ul: out.append("</ul>"); in_ul = False
            close_turn()
            lvl = min(len(m.group(1)), 4)
            tag = lvl + 2 if lvl > 1 else 4
            out.append(f"<h{tag}>{md_inline(m.group(2))}</h{tag}>")
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

# in the file loop:
text = f.read_text(encoding="utf-8")   # smart quotes / emoji / full-width colons
# at the end:
(ROOT / "index.html").write_text(PAGE, encoding="utf-8")
print(f"wrote index.html — {total} lessons, {len(PAGE)} bytes")
if total == 0:
    print("WARNING: no transcripts found. Check SECTIONS and that test-output/ "
          "holds the expected sectionN/*.md files next to this script.")
```
For the full page template (`<style>` + wrapper), copy `scripts/build_transcripts.py`
verbatim and edit the `:root` tokens and the metadata vars.
