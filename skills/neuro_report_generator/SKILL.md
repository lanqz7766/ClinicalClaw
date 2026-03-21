---
name: neuro_report_generator
description: Turn structured longitudinal neuro-oncology facts into a compact physician-facing report with fixed sections, stable numbers, and restrained recommendations.
allowed-tools: get_neuro_longitudinal_report render_clinical_report use_skill
---

Use this skill when ClinicalClaw needs to produce a polished longitudinal neuro-oncology brief from structured case data.

## Goal

Turn a stable neuro workspace payload into a compact clinician-facing report with:

- `Overview`
- `Trend`
- `Interpretation`
- `Recommended next review focus`

## Rules

- Start from structured facts, not free-form improvisation.
- Keep the tone clinical, concise, and review-oriented.
- Never expose internal tool names, local paths, asset URLs, or implementation details.
- Prefer short sections over long paragraphs.
- If a metric is unavailable, use a graceful fallback phrase instead of printing `None`, `NaN`, or placeholders.

## Expected inputs

- `patient`
- `timeline`
- `analysis`
- `workflow.events`
- `report.summary`
- `report.physician_questions`

## Output shape

- One concise title
- One subtitle
- One risk tier
- Four fixed sections:
  - `Overview`
  - `Trend`
  - `Interpretation`
  - `Recommended next review focus`

## Style

- Use structured radiology-report thinking inspired by open structured-reporting work such as SRRG.
- Organize the facts silently first, then present only the final formatted report.
- Keep language suitable for physician review, not patient-facing education.
