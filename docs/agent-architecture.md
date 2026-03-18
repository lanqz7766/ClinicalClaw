# Current Agent Architecture

## Runtime Shape

ClinicalClaw currently runs with two execution paths on top of the vendored `clawagents` runtime:

1. Generic gateway agent
   - used when the caller sends only `task`
   - behavior is the same as upstream `clawagents`

2. Scenario-controlled ClinicalClaw agent
   - used when the caller sends `task` plus `scenario_id`
   - built from the same runtime, but wrapped with scenario policy, review constraints, and task bookkeeping

## Current Roles

### Gateway agent

- entrypoint: `POST /chat`, `POST /chat/stream`, `WS /ws`
- responsibility: accept tasks, run the default agent loop, stream progress

### Scenario runtime wrapper

- entrypoint: `clinicalclaw.execution.ClinicalClawService`
- responsibility:
  - load scenario definitions
  - load normalized connectors
  - persist local execution state
  - create a `TaskRunRecord`
  - enforce tool policy
  - collect read-only connector context
  - inject recent run memory
  - inject scenario instructions into the prompt
  - mark the run as `in_review` when human review is required
  - create placeholder artifact records and access events

### Scenario-specific agent

- current scenario set:
  - `diagnostic_prep`
  - `imaging_qc`
- current control surface:
  - tool allowlist and blocklist
  - read-only connector inputs
  - connector permission summary in prompt
  - review gate in prompt and task state
  - max iteration limit per scenario

## What It Can Do Now

- run the original `clawagents` gateway unchanged for generic tasks
- accept an optional `scenario_id` without changing the endpoint surface
- load two structured scenario specs
- create internal task, artifact, and access-event records in memory
- enforce scenario tool restrictions during execution
- keep scenario runs review-gated by default
- support SMART on FHIR sandbox-ready launch and read skeletons
- support DICOMweb sandbox-ready QIDO/WADO read skeletons

## What Is Missing

- no verified Epic sandbox registration or live SMART callback deployment yet
- no PACS vendor validation for DICOMweb interoperability yet
- no database persistence yet
- no actual approval queue UI or API yet
- no write-back pipeline yet
- no dedicated sub-agent split such as orchestrator / EHR agent / imaging agent / safety agent
- no containerized execution boundary for imaging compute yet

## Practical Interpretation

Right now the system is a controlled shell platform with one real runtime and two scenario-controlled operating modes. It is not yet a hospital-integrated multi-agent system. The next step is to add concrete connectors and then split scenario execution into dedicated sub-agents only when the connectors and audit path are stable.
