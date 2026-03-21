# Current State

Updated: 2026-03-21

## Summary

ClinicalClaw currently sits at the stage of a working clinical workflow platform prototype with:

- a real gateway and streamed agent path
- workflow routing from a unified `/demo` console
- scenario execution, review, audit, and SQLite persistence
- SMART on FHIR and DICOMweb sandbox validation
- workflow-specific presentation skills for cleaner user-facing output
- a reusable Jinja2-backed report generator skill with optional PDF fallback
- a browser-oriented neuro visualization skill that renders privacy-preserving slice previews, overlays, and a NiiVue-style manifest
- a template-driven neuro report generator plus a browser viewer manifest for the PROTEAS demo
- a neuro workflow path that now explicitly loads shared report generation, neuro-specific report generation, and neuro visualization skills before answering
- a compatibility-first `clinicalclaw.engine` namespace for gradual runtime migration
- the first reusable workflow engine spec plus executable `findings_closure`, `queue_triage`, `missed_diagnosis_detection`, and `screening_gap_closure` families

It is beyond the original Week 1 shell, but it is not yet a production hospital deployment.

## What Works Now

### Platform

- original `clawagents` gateway remains the external API
- internal `ClinicalClawService` orchestration layer is in place
- scenario-driven execution supports controlled tool use and review requirements
- SQLite persistence stores tasks, artifacts, audit events, SMART sessions, token state, and run memory

### Integrations

- SMART on FHIR:
  - launch and callback flow
  - token exchange and persistence
  - read-path validation
- DICOMweb:
  - QIDO studies / series / instances
  - WADO metadata and object retrieval

### Demo Product Surface

- `/demo`
  - simplified general chat landing page
  - progressive brand/workflow flyout navigation
  - router agent
  - findings module page
  - queue triage module page
  - missed diagnosis module page
  - screening gap module page
  - streamed execution feedback
  - neuro module page
  - safety module page
- `/findings-demo`
  - direct findings-closure entry point
- `/queue-demo`
  - direct queue-triage entry point
- `/safety-demo`
  - direct safety-monitor entry point

### Agent Layer

Current routed workflows:

- `general_chat`
- `findings_closure`
- `queue_triage`
- `missed_diagnosis_detection`
- `screening_gap_closure`
- `neuro_longitudinal`
- `radiation_safety_monitor`

Current presentation skills:

- `clinical_report_presentation`
- `clinical_report_generator`
- `findings_brief_presenter`
- `queue_triage_presenter`
- `missed_diagnosis_presenter`
- `screening_gap_presenter`
- `neuro_report_presenter`
- `neuro_report_generator`
- `neuro_visualization_presenter`
- `safety_brief_presenter`

### Workflow Engine

The repository now also has the beginning of a reusable workflow engine layer:

- 11 initial workflow definitions under [workflows/](/Users/qlan/Documents/Agent/ClinicalClaw/workflows)
- engine models and loader in [src/clinicalclaw/workflow_engine.py](/Users/qlan/Documents/Agent/ClinicalClaw/src/clinicalclaw/workflow_engine.py)
- workflow definitions can now be stored as `json` or `yaml`
- family guidance can now be stored as `md` and `yaml`
- the first reusable family in [src/clinicalclaw/workflow_families/findings_closure.py](/Users/qlan/Documents/Agent/ClinicalClaw/src/clinicalclaw/workflow_families/findings_closure.py)
- a second executable family in [src/clinicalclaw/workflow_families/queue_triage.py](/Users/qlan/Documents/Agent/ClinicalClaw/src/clinicalclaw/workflow_families/queue_triage.py)
- a third executable family in [src/clinicalclaw/workflow_families/missed_diagnosis.py](/Users/qlan/Documents/Agent/ClinicalClaw/src/clinicalclaw/workflow_families/missed_diagnosis.py)
- a fourth executable family in [src/clinicalclaw/workflow_families/screening_gap.py](/Users/qlan/Documents/Agent/ClinicalClaw/src/clinicalclaw/workflow_families/screening_gap.py)

This is now both a platform-layer design and an initial UI-exposed family module.

Current findings demo status:

- `findings_closure` is available as a compact demo workspace
- the default end-to-end example is `critical_lab_escalation`
- seeded cases are realistic but de-identified and local-only
- the UI now prioritizes the active case, numeric risk signal, concise summary cards, and compact evidence/action blocks

Current queue triage family status:

- `queue_triage` has executable local stores and tests
- current demo-ready workflows include `high_risk_referral_triage` and `post_discharge_followup`
- it is now exposed as a compact module in `/demo`

Current missed diagnosis family status:

- `missed_diagnosis_detection` has an executable family runner and tests
- the first workflow is `missed_vertebral_fracture_detection`
- de-identified demo cases are local-only
- it is now exposed as a compact module in `/demo`

Current screening gap family status:

- `screening_gap_closure` has an executable family runner and tests
- the first workflow is `screening_gap_positive_fit_followup`
- de-identified demo cases are local-only
- it is now exposed as a compact module in `/demo`

Current neuro longitudinal demo status:

- `/demo` now supports a real local PROTEAS-backed neuro-oncology case review when `CLINICALCLAW_NEURO_LONGITUDINAL_DATA_ROOT` is configured
- the default real local demo case is currently `P28`
- the quantitative trend now uses radiomics-derived `T1C` tumor `MeshVolume` as the primary burden signal
- radiotherapy is aligned as a distinct event on the timeline instead of being treated as an imaging timepoint
- tumor masks remain available for preview and overlay, but are no longer the primary headline metric
- compact neuro tools now cover:
  - series selection
  - response tracking
  - treatment-event alignment
  - representative preview selection
  - trend/timeline/comparison visual rendering
  - compact risk signal generation
- the Neuro module now also materializes a compact report bundle plus a privacy-preserving NiiVue-backed slice/overlay viewer for the selected timepoints

### Runtime Migration

Phase 1 of runtime migration is now in place:

- `clinicalclaw.engine` exposes the vendored runtime through a ClinicalClaw-branded compatibility facade
- `clinicalclaw` top-level exports now point at the new engine namespace
- `clinicalclaw` CLI/module entry points delegate to the existing runtime CLI
- ClinicalClaw-owned imports have started moving from `clawagents` to `clinicalclaw.engine`

The repository is not yet fully physically migrated:

- `src/clawagents` is still the true implementation path
- broad runtime tests and examples still target `clawagents`
- gateway implementation still lives under the vendored runtime path

## What Is Still Prototype-Only

- most workflow demos still use mocked or de-identified local demo cases
- the neuro longitudinal module can now run on a real local PROTEAS dataset, but it is still a demo presentation path rather than a validated clinical product
- neuro analysis is not yet connected to a real segmentation / volumetry toolchain
- safety monitoring uses a local RO-ILS-inspired seed knowledge base rather than site-specific incident history
- email escalation is still mock escalation
- no real user auth or shareable preview gate yet

## Current Risks and Gaps

- no production secret management
- no production deployment hardening
- no real hospital EHR/PACS tenant validation
- no write-back path
- no formal reviewer UI beyond the current demo module interactions

## Working Rule For Future Pushes

Before pushing visible feature changes:

1. update `README.md`
2. update `docs/current-state.md`
3. append a short dated note to `docs/changelog.md`
