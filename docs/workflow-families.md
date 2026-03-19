# Workflow Families

ClinicalClaw workflow families are operational patterns, not specialty pages.

The same family can support multiple specialties:

- radiology
- cardiology
- primary care
- oncology
- neurology
- women’s health
- pulmonology
- pediatrics
- system-level operations

## Current Family Taxonomy

1. `findings_closure`
2. `screening_gap_closure`
3. `missed_diagnosis_detection`
4. `queue_triage`
5. `registry_abstraction`
6. `prior_auth_prep`
7. `trial_matching`
8. `documentation_reconciliation`

## Why This Matters

This structure keeps ClinicalClaw reusable:

- one family can power many concrete workflows
- one specialty can use multiple families
- router logic can first resolve a family, then choose a specific workflow
- presentation skills can be reused at the family level

## Initial Rollout Order

Recommended implementation order:

1. `findings_closure`
2. `queue_triage`
3. `missed_diagnosis_detection`
4. `screening_gap_closure`
5. `registry_abstraction`
6. `prior_auth_prep`
7. `trial_matching`
8. `documentation_reconciliation`

## Current Status

Implemented first:

- workflow engine loader and definition models
- the initial 10 workflow specs
- the first reusable family:
  - `findings_closure`
