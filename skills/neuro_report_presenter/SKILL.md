---
name: neuro_report_presenter
description: Format longitudinal neuro imaging outputs as concise physician-facing MRI trend reviews with stable headings, key numbers, and restrained recommendations.
allowed-tools: use_skill get_neuro_workspace
---

Use this skill for neuro longitudinal review answers, especially when the user asks for a physician summary, MRI trend analysis, or a polished report.

Assume the generic `clinical_report_presentation` skill is already loaded. This skill narrows the answer shape for neuro outputs.

Final-answer contract:

1. Open with one sentence stating the patient or case, time span reviewed, and overall direction of change.
2. Use exactly these headings unless the user explicitly asks for another format:
   - `### MRI Trend Analysis`
   - `### Draft Physician Summary`
   - `### Recommendations`
3. End with a one-line `Risk Tier`.

What to emphasize:

- time span and number of studies
- baseline and latest volume
- total percentage change
- whether the recent segment is steeper than the long-run slope
- the most relevant clinical correlation

Style rules:

- Keep the answer compact and readable in a chat window.
- Prefer 2 to 4 bullets inside sections rather than long paragraphs.
- Bold only the highest-signal numbers and labels.
- Do not drift into diagnosis language beyond the evidence shown.
- Recommendations should sound clinically useful, not alarmist.
