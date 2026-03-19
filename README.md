# ClinicalClaw

ClinicalClaw is a modular clinical AI execution and integration platform built on top of the vendored `clawagents` runtime. The project is no longer just a Week 1 shell. It now includes:

- the original `clawagents` gateway as the external API
- an internal ClinicalClaw orchestration layer
- scenario-controlled execution with review and audit state
- local SQLite persistence and run memory
- SMART on FHIR and DICOMweb sandbox validation paths
- a unified `/demo` console with real chat routing into workflow modules
- workflow-specific presentation skills for cleaner, clinician-facing output

## What It Is Today

The current repository is best understood as a clinical workflow platform prototype with working agent infrastructure and demo modules, not a production hospital deployment.

Current implemented areas:

- generic gateway chat via `POST /chat`, `POST /chat/stream`, and `WS /ws`
- scenario-controlled execution for:
  - `diagnostic_prep`
  - `imaging_qc`
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
- separate module pages instead of flattening everything into one screen

### 3. Demo Modules

Neuro longitudinal review:

- mounted inside `/demo`
- focuses on longitudinal hippocampal trend analysis
- includes a compact report layout, timeline, trend chart, and reviewer actions

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
├── src/clawagents/            # vendored runtime from clawagents_py
├── src/clinicalclaw/          # ClinicalClaw platform layer, demo modules, and orchestration
└── tests/                     # regression and platform tests
```

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

Current workflow router destinations:

- `general_chat`
- `neuro_longitudinal`
- `radiation_safety_monitor`

Presentation skills:

- [skills/clinical_report_presentation/SKILL.md](/Users/qlan/Documents/Agent/ClinicalClaw/skills/clinical_report_presentation/SKILL.md)
- [skills/neuro_report_presenter/SKILL.md](/Users/qlan/Documents/Agent/ClinicalClaw/skills/neuro_report_presenter/SKILL.md)
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
