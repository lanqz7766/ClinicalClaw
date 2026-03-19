# Current State

Updated: 2026-03-18

## Summary

ClinicalClaw currently sits at the stage of a working clinical workflow platform prototype with:

- a real gateway and streamed agent path
- workflow routing from a unified `/demo` console
- scenario execution, review, audit, and SQLite persistence
- SMART on FHIR and DICOMweb sandbox validation
- workflow-specific presentation skills for cleaner user-facing output

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
  - router agent
  - streamed execution feedback
  - neuro module page
  - safety module page
- `/safety-demo`
  - direct safety-monitor entry point

### Agent Layer

Current routed workflows:

- `general_chat`
- `neuro_longitudinal`
- `radiation_safety_monitor`

Current presentation skills:

- `clinical_report_presentation`
- `neuro_report_presenter`
- `safety_brief_presenter`

## What Is Still Prototype-Only

- demo cases are currently mocked rather than driven by real OASIS-3 or site data
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
