# Findings Closure Family

`findings_closure` is the first reusable ClinicalClaw workflow family.

## Purpose

This family handles cases where a clinically meaningful finding is already present in source text or result data, but the downstream closure step may still be missing.

Examples:

- actionable radiology findings
- suspicious lung nodule follow-up
- critical lab escalation
- positive FIT follow-up
- abnormal Pap routing

## Typical Inputs

- report text
- lab result text
- patient summary
- follow-up completion status

## Typical Evidence Sources

- finalized report text
- result summary
- prior follow-up status
- responsible team or owner metadata

## Decision Questions

1. Is there actionable language in the incoming finding?
2. Has closure already happened?
3. Does the finding need urgent escalation?
4. What is the safest next action?

## Default Actions

- create review item
- draft follow-up plan
- draft order suggestion
- draft scheduling step
- draft mock escalation email

## Review Policy

All current findings-closure workflows remain human-review-first.

## Presentation Pattern

Recommended structure:

- signal
- closure check
- recommended next step
- review status

For actionable radiology findings, keep the brief compact and preserve three details when they are present:

- the core radiology signal
- the requested follow-up or timeframe
- the current closure gap or resolved state

Recommended radiology-specific emphasis:

- distinguish routine actionable follow-up from same-day or emergent escalation
- name the likely owner only when the workflow provides it
- prefer one primary next step over a long action list

## Current Candidate Workflows

- `actionable_radiology_findings`
- `suspicious_lung_nodule_followup`
- `critical_lab_escalation`
- `positive_fit_followup`
- `abnormal_pap_routing`
