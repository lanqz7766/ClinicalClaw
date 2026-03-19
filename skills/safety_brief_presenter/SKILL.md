---
name: safety_brief_presenter
description: Format radiation safety monitoring outputs as concise operational briefs with risk summary, matched failure patterns, recommended checks, and escalation guidance.
allowed-tools: use_skill get_safety_queue get_safety_case search_safety_knowledge
---

Use this skill for radiation oncology safety monitoring answers, especially when the user asks whether a case should be flagged, reviewed, or escalated.

Assume the generic `clinical_report_presentation` skill is already loaded. This skill narrows the answer shape for safety outputs.

Final-answer contract:

1. Open with one sentence stating what case was screened and the current risk level.
2. Use exactly these headings unless the user explicitly asks for another format:
   - `### Risk Summary`
   - `### Matched Failure Patterns`
   - `### Recommended Checks`
3. End with a one-line `Escalation`.

What to emphasize:

- current risk tier and why it was assigned
- the strongest historical pattern match or the absence of one
- the process step most likely at risk
- the most actionable checks for the reviewer or QA lead

Style rules:

- Sound like an operational safety brief, not a technical matcher log.
- Keep paragraphs short and use bullets for actionable checks.
- Do not dump every signal or score; only surface the top evidence.
- Avoid internal tool names, raw retrieval scores, or engineering language.
