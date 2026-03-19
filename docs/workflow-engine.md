# Workflow Engine

ClinicalClaw should not implement each new clinical automation as a separate one-off app. The reusable workflow engine splits the problem into three layers:

1. `family`
2. `workflow`
3. `presentation skill`

## Family

A family is a reusable clinical automation pattern that can span multiple specialties.

Current family taxonomy:

- `findings_closure`
- `screening_gap_closure`
- `missed_diagnosis_detection`
- `queue_triage`
- `registry_abstraction`
- `prior_auth_prep`
- `trial_matching`
- `documentation_reconciliation`

## Workflow

A workflow is a concrete use case inside a family.

Each workflow definition captures:

- the problem statement
- required inputs
- trigger signals
- evidence sources
- rule sets
- allowed actions
- presentation style
- family-specific configuration

Workflow definitions live in:

- [workflows/](/Users/qlan/Documents/Agent/ClinicalClaw/workflows)

## Presentation Skill

The engine separates decision logic from output formatting.

- family logic decides what happened
- workflow config decides what should be checked
- presentation skills decide how the result is shown to clinicians or operators

## Initial Workflow Library

These are the first 10 workflows selected for realistic, mock-testable implementation in the current repository:

1. `actionable_radiology_findings`
2. `suspicious_lung_nodule_followup`
3. `critical_lab_escalation`
4. `positive_fit_followup`
5. `abnormal_pap_routing`
6. `high_risk_referral_triage`
7. `post_discharge_followup`
8. `undiagnosed_hypertension_detection`
9. `missed_vertebral_fracture_detection`
10. `unrecognized_af_detection`

## First Implemented Family: Findings Closure

The first family is `findings_closure`.

This family fits the current ClinicalClaw environment because it can already be exercised with:

- pasted report text
- local mock patient context
- review queue patterns
- mock escalation email
- clinician-facing brief generation

Shared family behavior:

- detect actionable language from the incoming text
- check whether closure is already documented
- assign a light risk tier
- recommend the next workflow actions
- keep human review in the loop

Current code entry points:

- engine models and loader:
  - [src/clinicalclaw/workflow_engine.py](/Users/qlan/Documents/Agent/ClinicalClaw/src/clinicalclaw/workflow_engine.py)
- first family implementation:
  - [src/clinicalclaw/workflow_families/findings_closure.py](/Users/qlan/Documents/Agent/ClinicalClaw/src/clinicalclaw/workflow_families/findings_closure.py)

## Recommended Next Step

Build the first end-to-end executable workflow on top of this family:

- `critical_lab_escalation`

It is the simplest real workflow for validating:

- intake
- family normalization
- action recommendation
- review gating
- mock escalation
