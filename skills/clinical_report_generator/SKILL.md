---
name: clinical_report_generator
description: Generate reusable clinician-facing report artifacts from structured workflow data using the shared Jinja2 report builder, with optional PDF export fallback and concise section formatting.
allowed-tools: render_clinical_report use_skill
---

Use this skill when the task is to produce or refresh a formatted report, physician brief, case handout, or exportable HTML/PDF artifact.

Prefer the shared report builder instead of hand-writing long prose. The report should be:

- short, structured, and readable in a clinical setting
- built from sections, metrics, and a compact signal line
- exportable as HTML by default
- exportable as PDF only when the optional PDF backend is available

Workflow:

1. Gather the structured case payload first.
2. Build a report document with a clear title, subtitle, short summary, 3-5 metrics, and 2-4 sections.
3. Keep each section focused on one idea: signal, evidence, action, review.
4. Render the bundle to HTML for the user-facing artifact.
5. If PDF is requested, attempt export; if the PDF backend is unavailable, fall back to HTML and note that the PDF is optional.

Style rules:

- Keep titles concise.
- Use small, clinically readable section headings.
- Do not expose raw tool traces or routing logic in the final report.
- Prefer bullet lists only when they clarify action items or evidence.
- If the source data is sparse, say so plainly instead of padding the report.

If you need formatting guidance, read [references/reporting_patterns.md](references/reporting_patterns.md).
