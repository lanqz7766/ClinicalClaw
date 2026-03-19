---
name: missed-diagnosis-presenter
description: Use when a missed_diagnosis_detection workflow needs a compact, review-first brief that focuses on the suspected gap, follow-up status, and safest next workup step.
---

# Missed Diagnosis Presenter

Use this skill when the workflow belongs to the `missed_diagnosis_detection` family.

## Goal

Turn raw diagnostic-gap output into a compact brief that answers four questions quickly:

1. What signal suggests a missed diagnosis or missed workup?
2. Is there any sign that follow-up is already underway?
3. What is the safest next workup step?
4. Does the case still need reviewer sign-off?

## Output Frame

Use short markdown sections with one or two sentences each.

1. `Gap Signal`
2. `Follow-up Check`
3. `Recommended Workup`
4. `Review Status`

If the case is urgent, start with one short escalation line.

## Style Rules

- Keep the answer compact and scannable.
- Prefer short paragraphs over long lists.
- Keep the brief review-first and evidence-based.
- Do not expose tool names, internal routing, rule identifiers, or chain-of-thought.
- Do not restate the full report.

## Constraints

- Do not invent diagnoses, procedures, or completed follow-up steps.
- Do not say the gap is closed unless the case explicitly says so.
- If follow-up is still open, name one primary next step.
