# Changelog

## 2026-03-19

- Added a fourth executable workflow family: `screening_gap_closure`, with the first workflow `screening_gap_positive_fit_followup`.
- Added workflow-engine support for recursive family directories plus `yaml` workflow specs.
- Added `yaml + md + skill` structure for screening-gap family guidance and presentation.
- Added a standalone `/queue-demo` page to bring queue triage up to the same demo maturity as findings.
- Refined `/demo` top navigation into softer flyout-style brand and workflow controls that blend into the page background.
- Simplified the `/demo` top navigation to a single `Workflows` dropdown and tightened the landing module grid to show smaller workflow cards.
- Removed internal readiness labels from the product-facing workflow router responses and UI surfaces.
- Exposed `missed_diagnosis_detection` as a compact module in `/demo`.
- Integrated `queue_triage` into the unified `/demo` console with live queue APIs and a compact queue module view.
- Added a reusable `missed_diagnosis_detection` family runner with a first workflow: `missed_vertebral_fracture_detection`.
- Added a reusable `queue_triage` family runner with local demo cases for `high_risk_referral_triage` and `post_discharge_followup`.
- Tightened the `findings_closure` demo UI to emphasize the active case, numeric risk signal, concise summary cards, and focused evidence/action blocks.
- Added an end-to-end `findings_closure` demo module with compact UI and realistic de-identified sample cases.
- Added router and presentation-skill support for `findings_closure`.
- Added the first executable findings workflow showcase: `critical_lab_escalation`.
- Added a reusable workflow-engine foundation with 10 initial workflow specs.
- Added the first reusable workflow family: `findings_closure`.
- Added workflow-engine docs and family taxonomy docs.
- Added a compatibility-first `clinicalclaw.engine` namespace that mirrors the vendored runtime entry points.
- Added `clinicalclaw` CLI and `python -m clinicalclaw` entry points that delegate to the existing runtime CLI.
- Switched ClinicalClaw-owned runtime imports to `clinicalclaw.engine` where safe.
- Added focused compatibility tests for the new `clinicalclaw` engine namespace.

## 2026-03-18

- Added a unified `/demo` console with a real streamed agent path.
- Added workflow routing for `general_chat`, `neuro_longitudinal`, and `radiation_safety_monitor`.
- Added neuro and safety demo workspaces with cleaner product-style UI.
- Added presentation skills:
  - `clinical_report_presentation`
  - `neuro_report_presenter`
  - `safety_brief_presenter`
- Improved chat output formatting with markdown rendering and cleaner execution feedback.
- Validated SMART on FHIR and DICOMweb sandbox demo paths in the current codebase.
- Removed planning `.docx` and `.pdf` files from the current repository version.
