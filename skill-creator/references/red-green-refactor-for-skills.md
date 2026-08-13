# RED-GREEN-REFACTOR for Skills

Follow the TDD cycle:

### RED: Write Failing Test (Baseline)

Run pressure scenario with subagent WITHOUT the skill. Document exact behavior:
- What choices did they make?
- What rationalizations did they use (verbatim)?
- Which pressures triggered violations?

This is "watch the test fail" - you must see what agents naturally do before writing the skill.

> For a skill that teaches a **tool / CLI / API** (not a behavioral-compliance
> skill), the RED test is different: delegate a fully COLD subagent with only the
> invocation path + minimal config + a real task + "this is all the docs you
> get," and read its honest "where I got stuck" report. A self-documenting tool
> can make the baseline already good — which means the skill should be thin
> (judgment, not commands), and the subagent's stumbles double as a tool-bug
> list to fix BEFORE writing the skill. See
> @red-phase-cold-subagent-for-tool-skills.md.

### GREEN: Write Minimal Skill

Write skill that addresses those specific rationalizations. Don't add extra content for hypothetical cases.

Run same scenarios WITH skill. Agent should now comply.

### REFACTOR: Close Loopholes

Agent found new rationalization? Add explicit counter. Re-test until bulletproof.

**Testing methodology:** See @testing-skills-with-subagents.md for the complete testing methodology:
- How to write pressure scenarios
- Pressure types (time, sunk cost, authority, exhaustion)
- Plugging holes systematically
- Meta-testing techniques
