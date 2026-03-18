# ClinicalClaw

ClinicalClaw is a modular clinical AI execution and integration platform for hospital workflows. This repository currently vendors `clawagents_py` as the agent runtime foundation and adds the Week 1 platform shell required for:

- scenario definitions
- policy and tool allowlists
- audit, task, artifact, and case model placeholders
- environment documentation for local development and future open source release

## Current Scope

Week 1 targets a runnable shell platform rather than a completed clinical product. The shell includes:

- vendored `clawagents` runtime under `src/clawagents`
- two scenario drafts in `scenarios/`
- in-memory models for cases, tasks, artifacts, and access events
- a policy preview layer for controlled tool execution
- internal platform modules under `src/clinicalclaw`

## Repository Layout

```text
.
├── docs/                      # environment and planning docs
├── scenarios/                 # scenario specifications
├── src/clawagents/            # vendored runtime from clawagents_py
├── src/clinicalclaw/          # ClinicalClaw platform shell
└── tests/                     # upstream and platform tests
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

Fill in provider settings only when you want live LLM execution. The platform shell runs without API keys.

### Environment reference

ClinicalClaw keeps most runtime configuration in `.env`. The canonical template lives in [.env.example](/Users/qlan/Documents/Agent/ClinicalClaw/.env.example).

Core ClinicalClaw settings:

- `CLINICALCLAW_APP_NAME`
- `CLINICALCLAW_ENVIRONMENT`
- `CLINICALCLAW_HOST`
- `CLINICALCLAW_PORT`
- `CLINICALCLAW_API_PREFIX`
- `CLINICALCLAW_DATABASE_PATH`
- `CLINICALCLAW_MEMORY_HISTORY_LIMIT`
- `CLINICALCLAW_CONNECTOR_TIMEOUT_S`
- `CLINICALCLAW_EHR_CONNECTOR_MODE`
- `CLINICALCLAW_IMAGING_CONNECTOR_MODE`
- `CLINICALCLAW_SCENARIO_DIR`
- `CLINICALCLAW_ARTIFACT_DIR`

SMART on FHIR settings:

- `CLINICALCLAW_FHIR_BASE_URL`
- `CLINICALCLAW_FHIR_ACCESS_TOKEN`
- `CLINICALCLAW_FHIR_AUTHORIZE_URL`
- `CLINICALCLAW_FHIR_TOKEN_URL`
- `CLINICALCLAW_FHIR_CLIENT_ID`
- `CLINICALCLAW_FHIR_CLIENT_SECRET`
- `CLINICALCLAW_FHIR_REDIRECT_URI`
- `CLINICALCLAW_FHIR_SCOPE`
- `CLINICALCLAW_SMART_LAUNCHER_BASE_URL`
- `CLINICALCLAW_SMART_LAUNCHER_FHIR_VERSION`
- `CLINICALCLAW_SMART_LAUNCHER_LAUNCH_TYPE`
- `CLINICALCLAW_SMART_LAUNCHER_PATIENT_ID`
- `CLINICALCLAW_SMART_LAUNCHER_PROVIDER_ID`
- `CLINICALCLAW_SMART_LAUNCHER_ENCOUNTER_ID`
- `CLINICALCLAW_SMART_LAUNCHER_SKIP_LOGIN`
- `CLINICALCLAW_SMART_LAUNCHER_SKIP_AUTH`
- `CLINICALCLAW_SMART_LAUNCHER_CLIENT_TYPE`
- `CLINICALCLAW_SMART_LAUNCHER_PKCE_MODE`
- `CLINICALCLAW_SMART_LAUNCHER_AUTO_CALLBACK`

DICOMweb settings:

- `CLINICALCLAW_DICOMWEB_BASE_URL`
- `CLINICALCLAW_DICOMWEB_ACCESS_TOKEN`

LLM provider settings:

- `PROVIDER`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_BASE_URL`
- `OPENAI_API_VERSION`
- `OPENAI_API_TYPE`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`
- `MAX_TOKENS`
- `TEMPERATURE`
- `CONTEXT_WINDOW`
- `STREAMING`
- `MAX_ITERATIONS`

Trajectory and PTRL settings:

- `CLAW_TRAJECTORY`
- `CLAW_RETHINK`
- `CLAW_LEARN`
- `CLAW_LEARN_MODEL`
- `CLAW_PREVIEW_CHARS`
- `CLAW_RESPONSE_CHARS`
- `CLAW_TIMEOUT`

Gateway and channel settings:

- `GATEWAY_API_KEY`
- `GATEWAY_CORS_ORIGINS`
- `TELEGRAM_BOT_TOKEN`
- `WHATSAPP_AUTH_DIR`
- `WHATSAPP_API_URL`
- `WHATSAPP_API_TOKEN`
- `WHATSAPP_PHONE_ID`
- `SIGNAL_ACCOUNT`
- `SIGNAL_CLI_BIN`
- `CHANNEL_DEBOUNCE_MS`

Env file overrides:

- `CLINICALCLAW_ENV_FILE`
- `CLAWAGENTS_ENV_FILE`

`CLAWAGENTS_ENV_FILE` is useful in CI, Docker, or multi-project workspaces when you want the gateway runtime to load a specific `.env` file instead of the current directory default.

### 3. Start the platform API

```bash
clawagents --serve
```

Default gateway URL: `http://127.0.0.1:3000`

Useful endpoints:

- `GET /health`
- `GET /queue`
- `POST /chat`
- `POST /chat/stream`
- `WS /ws`

### Optional Scenario Mode

The external API surface stays the same, but `POST /chat`, `POST /chat/stream`, and `WS /ws` now accept an optional scenario selector:

```json
{
  "task": "Prepare a pre-visit brief for the current imaging case",
  "scenario_id": "diagnostic_prep",
  "requested_by": "local-dev"
}
```

If `scenario_id` is omitted, the gateway behaves like plain upstream `clawagents`.

## Scenarios

The initial scenario drafts are:

- `diagnostic_prep`: pre-visit imaging and chart briefing
- `imaging_qc`: imaging quality control and reproducible batch analysis

These are draft workflow specs, not production clinical logic.

## Connector Layer

ClinicalClaw now includes a read-only connector abstraction:

- `EHRConnector`
- `ImagingConnector`

Default mode is `mock`, which gives stable local development without requiring real FHIR or DICOMweb credentials. The current SMART on FHIR layer includes a minimal read-only skeleton for:

- launch context
- patient fetch
- encounter fetch
- chart bundle assembly

## Persistence And Memory

ClinicalClaw now persists local development state in SQLite by default:

- tasks
- artifacts
- access events
- SMART launch sessions
- SMART token states
- run memories for prior success/failure guidance

Default state path: `.clinicalclaw/state.db`

## Review Workflow

ClinicalClaw now includes a strict review queue and task state machine:

- `in_review`
- `approved`
- `rejected`
- `filed`

The queue is backed by persisted `TaskRunRecord` state and synchronized artifact statuses.

## SMART Sandbox Entry

For local SMART sandbox bring-up, see:

- [examples/09_smart_sandbox_entry.py](/Users/qlan/Documents/Agent/ClinicalClaw/examples/09_smart_sandbox_entry.py)

For local DICOMweb sandbox validation, see:

- [examples/10_dicomweb_sandbox_entry.py](/Users/qlan/Documents/Agent/ClinicalClaw/examples/10_dicomweb_sandbox_entry.py)

## Upstream Base

This repository includes code copied from [x1jiang/clawagents_py](https://github.com/x1jiang/clawagents_py). The runtime remains in `src/clawagents` so we can reuse its gateway, queueing, tool registry, sandbox, and agent loop while layering hospital-specific platform concerns in `src/clinicalclaw`.

## Next Build Targets

- SMART on FHIR launch and patient-context fetch
- DICOMweb QIDO/WADO connectors
- persistent storage for tasks, artifacts, and access events
- approval workflow and audit export
