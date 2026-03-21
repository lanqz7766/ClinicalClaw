# Changelog

## 2026-03-21

- Switched the Neuro viewer and preview assets to a privacy-preserving, lesion-focused crop so the demo no longer exposes full facial structure in MRI previews.
- Reworked the Neuro analysis panel to show three aligned axial comparison windows instead of a large viewer, with shared bounds and a common slice index so the windows stay visually aligned.
- Fixed `/demo` Neuro initialization so missing optional arrays like chat messages or uploads no longer leave the page stuck on `Loading`.
- Added a reusable Jinja2-backed `clinical_report_generator` skill and Python report bundle layer with HTML output and optional PDF fallback.
- Added a browser-oriented neuro visualization skill and tool layer that produces slice previews, overlays, comparison panels, and a NiiVue-style manifest.
- Wired the Neuro longitudinal demo to emit reusable report and visualization artifacts alongside the existing compact clinician-facing brief.
- Added a compact Neuro report generator bundle so the longitudinal review can present a cleaner clinical brief instead of a long wall of text.
- Added a browser-facing Neuro visualization bundle that can materialize derived assets for compact axial comparison panels under the local demo directory.
- Added neuro skills for report generation and visualization presentation.
- Wired the console agent to explicitly load the dedicated `neuro_report_generator` skill alongside the shared clinical report generator and neuro visualization skills for neuro longitudinal tasks.
- Exposed the Neuro viewer assets through the gateway so the demo can load real local volumes directly in the browser.
- Updated the Neuro demo UI to prioritize compact rendered report output and aligned axial comparison panes over a heavier viewer-style surface.

## 2026-03-20

- Switched the neuro longitudinal demo from a hippocampal placeholder narrative to a real local PROTEAS-backed neuro-oncology review when `CLINICALCLAW_NEURO_LONGITUDINAL_DATA_ROOT` is configured.
- Added PROTEAS neuro tooling for:
  - `dicom_series_selector`
  - `brain_met_response_tracker`
  - `rt_timeline_aligner`
  - `slice_preview_renderer`
  - `lesion_trend_plotter`
  - `treatment_event_timeline_renderer`
  - `key_slice_selector`
  - `overlay_composer`
  - `longitudinal_comparison_panel_builder`
  - `risk_signal_renderer`
- Switched the primary neuro longitudinal quantitative signal to radiomics-derived `T1C` tumor `MeshVolume`, with tumor masks retained for preview and overlay support.
- Fixed PROTEAS timepoint alignment so radiotherapy is rendered as a distinct event rather than being treated as an MRI follow-up timepoint.
- Tightened the Neuro module UI into a more focused single-case demo layout with a compact case selector, lighter hero, simplified timeline, and shorter physician brief.
- Added PROTEAS-specific regression tests covering workspace construction, demo workspace selection, and neuro tool availability.

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
