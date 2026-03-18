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
