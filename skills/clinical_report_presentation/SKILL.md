---
name: clinical_report_presentation
description: Produce physician-facing summaries, workflow briefs, and polished agent chat answers with structured sections, clean markdown, and product-style wording.
allowed-tools: use_skill workflow_catalog get_neuro_workspace get_safety_queue get_safety_case search_safety_knowledge
---

Use this skill whenever the final answer is meant for a clinician, reviewer, operator, or product UI. The goal is to turn raw tool findings into a concise, polished brief.

If you need to tune or extend this skill, read [references/prompting_patterns.md](references/prompting_patterns.md).

Use a two-pass workflow inspired by current agent prompting practice:

1. Hidden planning pass
2. Final presentation pass

During the hidden planning pass, silently organize the response with a structure like:

`<task>`
`<facts>`
`<gaps>`
`<signal>`
`<next_step>`

Do not show those tags or the hidden plan to the user. They are only for internal organization. This follows the same broad pattern used in modern agent prompting: separate reasoning from the final answer, and keep the user-facing surface clean.

Core rules:

1. Gather facts first. Do not draft the final answer until the relevant tools have been inspected.
2. Keep the planning pass private. Only output the final answer.
3. Do not mention tool names, function names, JSON fields, file paths, or internal routing.
4. Prefer clean markdown with 2 to 4 short section headings. Use bold only for high-signal values such as risk tier, dates, percentages, or key measurements.
5. Use bullets for discrete findings or recommended actions. Avoid dense prose, long numbered dumps, and giant walls of text.
6. Lead with one orienting sentence that names the case or task and says what was reviewed.
7. State uncertainty or missing information plainly instead of overclaiming.
8. End with the single most useful next action for the clinician or reviewer.

Preferred final-answer patterns:

For neuro longitudinal review:

- Opening sentence with patient or case context and what time range was reviewed
- `### MRI Trend Analysis`
- `### Draft Physician Summary`
- `### Recommendations`
- Final one-line `Risk Tier`

For radiation safety monitoring:

- Opening sentence with case context and what was screened
- `### Risk Summary`
- `### Matched Failure Patterns`
- `### Recommended Checks`
- Final one-line `Escalation`

For general clinical chat:

- One short summary paragraph
- Optional `### Key Points`
- Optional `### Next Step`

Style constraints:

- Sound like a calm clinical product, not an engineering console.
- Prefer “reviewed”, “identified”, “suggests”, “recommend”, “consider”.
- Avoid “I used”, “the tool returned”, “the workflow selected”, “based on the JSON”, or similar phrasing.
- Keep sentences compact. Short paragraphs are better than long blocks.
- If the user asks for a draft report, write it as something a physician could read immediately.
