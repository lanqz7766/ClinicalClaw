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

The engine now supports:

- executable workflow specs in `json`
- executable workflow specs in `yaml`
- family guidance in `md`
- family guidance in `yaml`

## Presentation Skill

The engine separates decision logic from output formatting.

- family logic decides what happened
- workflow config decides what should be checked
- presentation skills decide how the result is shown to clinicians or operators

## Initial Workflow Library

These are the first 11 workflows selected for realistic, mock-testable implementation in the current repository:

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
11. `screening_gap_positive_fit_followup`

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

## Fourth Implemented Family: Screening Gap Closure

The latest family is `screening_gap_closure`.

This family is now organized in the repository with:

- executable runner:
  - [src/clinicalclaw/workflow_families/screening_gap.py](/Users/qlan/Documents/Agent/ClinicalClaw/src/clinicalclaw/workflow_families/screening_gap.py)
- local demo store:
  - [src/clinicalclaw/screening_gap.py](/Users/qlan/Documents/Agent/ClinicalClaw/src/clinicalclaw/screening_gap.py)
- executable workflow specs:
  - [workflows/screening_gap](/Users/qlan/Documents/Agent/ClinicalClaw/workflows/screening_gap)
- family guidance:
  - [workflows/families/screening_gap_closure.md](/Users/qlan/Documents/Agent/ClinicalClaw/workflows/families/screening_gap_closure.md)
  - [workflows/families/screening_gap_closure.yaml](/Users/qlan/Documents/Agent/ClinicalClaw/workflows/families/screening_gap_closure.yaml)
- presentation skill:
  - [skills/screening_gap_presenter/SKILL.md](/Users/qlan/Documents/Agent/ClinicalClaw/skills/screening_gap_presenter/SKILL.md)

## Recommended Next Step

Build the next end-to-end executable workflow on top of `screening_gap_closure`:

- `identify_eligible_lung_cancer_screening`

It is a strong next target for validating:

- eligibility checking
- open-gap detection
- review-first outreach planning
- queue creation
- compact clinician-facing presentation
