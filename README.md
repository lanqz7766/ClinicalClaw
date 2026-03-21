# ClinicalClaw

ClinicalClaw is a modular clinical AI execution and integration platform built on top of the vendored `clawagents` runtime. The project is no longer just a Week 1 shell. It now includes:

- the original `clawagents` gateway as the external API
- an internal ClinicalClaw orchestration layer
- scenario-controlled execution with review and audit state
- local SQLite persistence and run memory
- SMART on FHIR and DICOMweb sandbox validation paths
- a unified `/demo` console with real chat routing into workflow modules
- workflow-specific presentation skills for cleaner, clinician-facing output
- a reusable Jinja2-backed report generator skill with optional PDF fallback
- a browser-oriented neuro visualization skill that renders slice previews, overlays, and a NiiVue-style manifest
- a new `clinicalclaw.engine` compatibility namespace that begins internalizing the runtime under the ClinicalClaw brand

## What It Is Today

The current repository is best understood as a clinical workflow platform prototype with working agent infrastructure and demo modules, not a production hospital deployment.

Current implemented areas:

- generic gateway chat via `POST /chat`, `POST /chat/stream`, and `WS /ws`
- scenario-controlled execution for:
  - `diagnostic_prep`
  - `imaging_qc`
  - `t1_raw_ingest`
- local persistence for:
  - tasks
  - artifacts
  - audit/access events
  - SMART launch sessions
  - SMART token state
  - run memories
- strict review queue and task state transitions
- SMART on FHIR launch, callback, token exchange, and read-path validation
- DICOMweb QIDO and WADO sandbox validation
- unified demo console with:
  - general chat landing page
  - findings closure module
  - queue triage module
  - missed diagnosis review module
  - screening gap closure module
  - router agent
  - neuro longitudinal review module
  - radiation safety monitor module

## Current Product Surface

### 1. Gateway API

The external interface stays aligned with the original `clawagents` gateway.

Useful endpoints:

- `GET /health`
- `GET /queue`
- `POST /chat`
- `POST /chat/stream`
- `WS /ws`

### 2. Demo Console

The fastest way to see the current product prototype is the unified console:

- route: `/demo`
- local URL: `http://127.0.0.1:3000/demo`

The console includes:

- a simplified general chat landing page
- lightweight routing into the correct workflow
- product-style streamed execution feedback
- progressive topbar flyouts for brand and workflow navigation
- separate module pages instead of flattening everything into one screen
- compact module cards that surface 3 to 4 workflows per row on larger screens

### 3. Demo Modules

Findings closure:

- route: `/findings-demo`
- focuses on actionable findings follow-up and closure verification
- currently demonstrates `critical_lab_escalation`, `positive_fit_followup`, and `suspicious_lung_nodule_followup`
- includes a compact signal view, closure path, recommended actions, mock escalation, and review

Queue triage:

- route: `/queue-demo`
- also mounted inside `/demo`
- focuses on high-risk referral triage and post-discharge follow-up prioritization
- demonstrates `high_risk_referral_triage` and `post_discharge_followup`
- uses a compact risk signal, queue move recommendation, and concise evidence blocks

Missed diagnosis review:

- mounted inside `/demo`
- focuses on diagnosis-gap detection from report text and follow-up signals
- currently demonstrates `missed_vertebral_fracture_detection`
- uses a compact gap signal, workup recommendation, and review-first evidence summary

Screening gap closure:

- mounted inside `/demo`
- focuses on open screening follow-up and review-first closure recommendations
- currently demonstrates `screening_gap_positive_fit_followup`
- uses a compact gap signal, follow-up recommendation, and reviewer-facing evidence summary

Neuro longitudinal review:

- mounted inside `/demo`
- supports a real local PROTEAS-backed neuro-oncology longitudinal review when `CLINICALCLAW_NEURO_LONGITUDINAL_DATA_ROOT` is configured
- focuses on post-radiotherapy brain metastasis follow-up, treatment-aligned MRI review, and concise physician-facing summaries
- includes radiomics-backed lesion trend tracking, RT-aligned timeline, a NiiVue-powered slice/overlay viewer, compact report bundles, and reviewer actions
- exposes reusable `render_clinical_report` and `build_neuro_visualization_bundle` tools for agent-driven report and visualization generation

Radiation safety monitor:

- route: `/safety-demo`
- uses a local RO-ILS-inspired knowledge base
- supports watch / alert / urgent classification
- includes matched failure patterns, recommended checks, and mock escalation

## Repository Layout

```text
.
├── docs/                      # project state, environment, connector, and planning docs
├── examples/                  # runnable SMART and DICOM sandbox entry scripts
├── scenarios/                 # scenario specifications
├── skills/                    # presentation and workflow-oriented agent skills
├── workflows/                 # reusable workflow definitions and family docs
├── src/clawagents/            # vendored runtime from clawagents_py
├── src/clinicalclaw/          # ClinicalClaw platform layer, demo modules, orchestration, and engine facade
└── tests/                     # regression and platform tests
```

## Runtime Migration Status

ClinicalClaw is in a compatibility-first migration toward a unified `clinicalclaw` runtime namespace.

What is already available:

- `clinicalclaw.engine` mirrors key `clawagents` runtime entry points
- `clinicalclaw.create_claw_agent` now re-exports the new engine facade
- `python -m clinicalclaw` and the `clinicalclaw` CLI script delegate to the existing runtime CLI
- ClinicalClaw-owned modules such as the scenario runtime and console agent now import from `clinicalclaw.engine`

What remains intentionally unchanged in Phase 1:

- `src/clawagents` remains the real vendored runtime implementation
- the original `clawagents` CLI and gateway imports remain supported
- vendored runtime examples and broad upstream-style tests still target `clawagents`

This lets us dogfood the new namespace without dropping compatibility.

## Quick Start

### 1. Create a virtual environment

Recommended target: Python 3.12.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

### 2. Configure environment

```bash
cp .env.example .env
```

You only need live provider keys when you want real LLM execution. The local platform shell and many tests can run without them.

### 3. Start the server

```bash
clawagents --serve
```

or:

```bash
clinicalclaw --serve
```

Default local URL:

- `http://127.0.0.1:3000`

## Environment Overview

The canonical environment template is:

- [.env.example](/Users/qlan/Documents/Agent/ClinicalClaw/.env.example)

High-signal groups:

Core platform:

- `CLINICALCLAW_APP_NAME`
- `CLINICALCLAW_ENVIRONMENT`
- `CLINICALCLAW_HOST`
- `CLINICALCLAW_PORT`
- `CLINICALCLAW_DATABASE_PATH`
- `CLINICALCLAW_SCENARIO_DIR`
- `CLINICALCLAW_ARTIFACT_DIR`
- `CLINICALCLAW_NEURO_LONGITUDINAL_DATA_ROOT`

SMART on FHIR:

- `CLINICALCLAW_FHIR_BASE_URL`
- `CLINICALCLAW_FHIR_AUTHORIZE_URL`
- `CLINICALCLAW_FHIR_TOKEN_URL`
- `CLINICALCLAW_FHIR_CLIENT_ID`
- `CLINICALCLAW_FHIR_CLIENT_SECRET`
- `CLINICALCLAW_FHIR_REDIRECT_URI`
- `CLINICALCLAW_FHIR_SCOPE`
- `CLINICALCLAW_SMART_LAUNCHER_BASE_URL`

DICOMweb:

- `CLINICALCLAW_DICOMWEB_BASE_URL`
- `CLINICALCLAW_DICOMWEB_ACCESS_TOKEN`

LLM providers:

- `PROVIDER`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_BASE_URL`
- `OPENAI_API_VERSION`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`

Runtime behavior:

- `MAX_TOKENS`
- `TEMPERATURE`
- `CONTEXT_WINDOW`
- `STREAMING`
- `MAX_ITERATIONS`

Trajectory and learning:

- `CLAW_TRAJECTORY`
- `CLAW_RETHINK`
- `CLAW_LEARN`
- `CLAW_LEARN_MODEL`
- `CLAW_PREVIEW_CHARS`
- `CLAW_RESPONSE_CHARS`

Env overrides:

- `CLINICALCLAW_ENV_FILE`
- `CLAWAGENTS_ENV_FILE`

## Connectors and Integrations

ClinicalClaw currently exposes read-only connector abstractions:

- `EHRConnector`
- `ImagingConnector`

Implemented connector work:

- SMART on FHIR:
  - launch and callback handling
  - token exchange
  - local token persistence
  - sandbox read-path validation
- DICOMweb:
  - QIDO study / series / instance queries
  - WADO metadata and instance retrieval
  - Orthanc demo validation path

Relevant docs:

- [docs/smart-on-fhir.md](/Users/qlan/Documents/Agent/ClinicalClaw/docs/smart-on-fhir.md)
- [docs/dicomweb.md](/Users/qlan/Documents/Agent/ClinicalClaw/docs/dicomweb.md)
- [docs/connectors.md](/Users/qlan/Documents/Agent/ClinicalClaw/docs/connectors.md)
- [docs/workflow-engine.md](/Users/qlan/Documents/Agent/ClinicalClaw/docs/workflow-engine.md)
- [docs/workflow-families.md](/Users/qlan/Documents/Agent/ClinicalClaw/docs/workflow-families.md)
- [docs/neuro-environment.md](/Users/qlan/Documents/Agent/ClinicalClaw/docs/neuro-environment.md)

## Real Local Neuro Demo

The most polished current single-case demo is the neuro longitudinal module.

When `CLINICALCLAW_NEURO_LONGITUDINAL_DATA_ROOT` points at a local PROTEAS dataset root, `/demo` switches from the fallback mock case to a real local longitudinal review. The current workflow uses:

- DICOM series discovery for longitudinal MRI follow-up
- radiomics-backed `T1C` tumor burden as the primary quantitative trend
- radiotherapy event alignment on the clinical timeline
- compact SVG visualizations for trend, timeline, and key comparisons
- a concise neuro-oncology brief suitable for demo presentation and review

This dataset path is intentionally local-only and must not be committed.

## Neuro Ingest Direction

The platform now includes a first neuro-oriented raw ingest scenario:

- `t1_raw_ingest`
  - scans raw DICOM exports
  - inventories series headers without touching pixel payloads
  - ranks likely T1 structural candidates
  - prepares reviewable `dcm2niix` conversion plans
  - emits a reproducible and schedulable pipeline manifest with stable run ids and resume commands

This is meant to be the bridge between PACS-style raw exports and downstream T1-focused tooling such as MONAI, DeepPrep, or FreeSurfer-class pipelines.

## Persistence, Review, and Memory

Default local state path:

- `.clinicalclaw/state.db`

The platform currently persists:

- task runs
- artifacts
- access events
- SMART launch sessions
- SMART token states
- run memories

Review behavior:

- strict task transitions
- explicit `in_review`, `approved`, `rejected`, `filed`
- synchronized artifact state
- auditable review events

Relevant docs:

- [docs/persistence.md](/Users/qlan/Documents/Agent/ClinicalClaw/docs/persistence.md)
- [docs/review-queue.md](/Users/qlan/Documents/Agent/ClinicalClaw/docs/review-queue.md)

## Agent and Skill Layer

The current console uses a real streamed agent path plus workflow routing.

Runtime entry points now available:

- `from clinicalclaw import create_claw_agent`
- `from clinicalclaw.engine import create_claw_agent`
- `python -m clinicalclaw`
- `clinicalclaw --serve`

Current workflow router destinations:

- `general_chat`
- `findings_closure`
- `queue_triage`
- `missed_diagnosis_detection`
- `neuro_longitudinal`
- `radiation_safety_monitor`

Reusable workflow engine work now in progress:

- engine models and loader:
  - [src/clinicalclaw/workflow_engine.py](/Users/qlan/Documents/Agent/ClinicalClaw/src/clinicalclaw/workflow_engine.py)
- initial workflow library:
  - [workflows/](/Users/qlan/Documents/Agent/ClinicalClaw/workflows)
- yaml + md family guidance:
  - [workflows/families](/Users/qlan/Documents/Agent/ClinicalClaw/workflows/families)
- executable families:
  - [src/clinicalclaw/workflow_families/findings_closure.py](/Users/qlan/Documents/Agent/ClinicalClaw/src/clinicalclaw/workflow_families/findings_closure.py)
  - [src/clinicalclaw/workflow_families/queue_triage.py](/Users/qlan/Documents/Agent/ClinicalClaw/src/clinicalclaw/workflow_families/queue_triage.py)
  - [src/clinicalclaw/workflow_families/missed_diagnosis.py](/Users/qlan/Documents/Agent/ClinicalClaw/src/clinicalclaw/workflow_families/missed_diagnosis.py)
  - [src/clinicalclaw/workflow_families/screening_gap.py](/Users/qlan/Documents/Agent/ClinicalClaw/src/clinicalclaw/workflow_families/screening_gap.py)
- first end-to-end findings module:
  - [src/clinicalclaw/findings_closure.py](/Users/qlan/Documents/Agent/ClinicalClaw/src/clinicalclaw/findings_closure.py)
  - [src/clinicalclaw/ui/findings/index.html](/Users/qlan/Documents/Agent/ClinicalClaw/src/clinicalclaw/ui/findings/index.html)
- queue triage local module foundation:
  - [src/clinicalclaw/queue_triage.py](/Users/qlan/Documents/Agent/ClinicalClaw/src/clinicalclaw/queue_triage.py)
- missed diagnosis local module foundation:
  - [src/clinicalclaw/missed_diagnosis.py](/Users/qlan/Documents/Agent/ClinicalClaw/src/clinicalclaw/missed_diagnosis.py)
- screening gap local module foundation:
  - [src/clinicalclaw/screening_gap.py](/Users/qlan/Documents/Agent/ClinicalClaw/src/clinicalclaw/screening_gap.py)

Presentation skills:

- [skills/clinical_report_presentation/SKILL.md](/Users/qlan/Documents/Agent/ClinicalClaw/skills/clinical_report_presentation/SKILL.md)
- [skills/findings_brief_presenter/SKILL.md](/Users/qlan/Documents/Agent/ClinicalClaw/skills/findings_brief_presenter/SKILL.md)
- [skills/queue_triage_presenter/SKILL.md](/Users/qlan/Documents/Agent/ClinicalClaw/skills/queue_triage_presenter/SKILL.md)
- [skills/missed_diagnosis_presenter/SKILL.md](/Users/qlan/Documents/Agent/ClinicalClaw/skills/missed_diagnosis_presenter/SKILL.md)
- [skills/screening_gap_presenter/SKILL.md](/Users/qlan/Documents/Agent/ClinicalClaw/skills/screening_gap_presenter/SKILL.md)
- [skills/neuro_report_presenter/SKILL.md](/Users/qlan/Documents/Agent/ClinicalClaw/skills/neuro_report_presenter/SKILL.md)
- [skills/neuro_report_generator/SKILL.md](/Users/qlan/Documents/Agent/ClinicalClaw/skills/neuro_report_generator/SKILL.md)
- [skills/neuro_visualization_presenter/SKILL.md](/Users/qlan/Documents/Agent/ClinicalClaw/skills/neuro_visualization_presenter/SKILL.md)
- [skills/safety_brief_presenter/SKILL.md](/Users/qlan/Documents/Agent/ClinicalClaw/skills/safety_brief_presenter/SKILL.md)

These skills are used to:

- keep final answers clinician-facing
- avoid exposing tool names and routing details
- stabilize report structure by workflow

## Example Scripts

SMART sandbox entry:

- [examples/09_smart_sandbox_entry.py](/Users/qlan/Documents/Agent/ClinicalClaw/examples/09_smart_sandbox_entry.py)

DICOMweb sandbox entry:

- [examples/10_dicomweb_sandbox_entry.py](/Users/qlan/Documents/Agent/ClinicalClaw/examples/10_dicomweb_sandbox_entry.py)

## Testing

Run the full test suite:

```bash
.venv/bin/python -m pytest -q
```

The latest validated state in local development has included the new console agent, demo workspace, safety monitor, and gateway tests.

## Security and Repository Rules

Keep these out of git:

- `.env`
- API keys
- local SQLite state
- local case data
- non-public planning or hospital documents

The repository should contain:

- code
- tests
- documentation
- safe templates such as `.env.example`

## Documentation Policy

This repository now treats docs as part of the product surface.

Before each future push:

- update [README.md](/Users/qlan/Documents/Agent/ClinicalClaw/README.md) if the visible project scope changed
- update [docs/current-state.md](/Users/qlan/Documents/Agent/ClinicalClaw/docs/current-state.md) with the latest product and engineering snapshot
- update [docs/changelog.md](/Users/qlan/Documents/Agent/ClinicalClaw/docs/changelog.md) with a short dated summary

## Current State and Changelog

- [docs/current-state.md](/Users/qlan/Documents/Agent/ClinicalClaw/docs/current-state.md)
- [docs/changelog.md](/Users/qlan/Documents/Agent/ClinicalClaw/docs/changelog.md)

## Upstream Base

This repository includes code copied from [x1jiang/clawagents_py](https://github.com/x1jiang/clawagents_py). The runtime remains in `src/clawagents` so ClinicalClaw can reuse its gateway, queueing, tool registry, sandbox, and agent loop while layering clinical workflow concerns in `src/clinicalclaw`.
