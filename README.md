# ClinicalClaw

ClinicalClaw is a modular clinical AI execution and integration platform for hospital workflows. This repository currently vendors `clawagents_py` as the agent runtime foundation and adds the Week 1 platform shell required for:

- platform API scaffolding
- scenario definitions
- policy and tool allowlists
- audit, task, artifact, and case model placeholders
- environment documentation for local development and future open source release

## Current Scope

Week 1 targets a runnable shell platform rather than a completed clinical product. The shell includes:

- a FastAPI app under `src/clinicalclaw`
- vendored `clawagents` runtime under `src/clawagents`
- two scenario drafts in `scenarios/`
- in-memory models for cases, tasks, artifacts, and access events
- a policy preview layer for controlled tool execution

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
clinicalclaw-api
```

Default URL: `http://127.0.0.1:8000`

Useful endpoints:

- `GET /health`
- `GET /v1/scenarios`
- `GET /v1/policies`
- `GET /v1/cases`
- `GET /v1/tasks`
- `POST /v1/tasks`

## Scenarios

The initial scenario drafts are:

- `diagnostic_prep`: pre-visit imaging and chart briefing
- `imaging_qc`: imaging quality control and reproducible batch analysis

These are draft workflow specs, not production clinical logic.

## Upstream Base

This repository includes code copied from [x1jiang/clawagents_py](https://github.com/x1jiang/clawagents_py). The runtime remains in `src/clawagents` so we can reuse its gateway, queueing, tool registry, sandbox, and agent loop while layering hospital-specific platform concerns in `src/clinicalclaw`.

## Next Build Targets

- SMART on FHIR launch and patient-context fetch
- DICOMweb QIDO/WADO connectors
- persistent storage for tasks, artifacts, and access events
- approval workflow and audit export
