# Data Contracts V1

This document defines the minimum stable platform entities for the Week 1 shell. These are internal contracts, not final database schemas.

## Design Rules

- Keep the number of first-class entities small.
- Favor fields that map cleanly to FHIR and DICOM later.
- Default to read-only external access and explicit review gates.
- Avoid embedding connector-specific payloads directly into top-level records.

## Core Entities

### `CaseRecord`

Represents the platform's working container for one clinical or research workflow context.

Required meaning:

- one case may reference one patient and zero or one current encounter
- one case may drive multiple scenario runs over time
- case state is independent from agent execution state

Key mappings:

- `external_patient_id` -> future `FHIR Patient.id`
- `encounter_id` -> future `FHIR Encounter.id`
- `external_references[]` -> future links to `Patient`, `Encounter`, `ImagingStudy`, `DiagnosticReport`

### `TaskRunRecord`

Represents one scenario execution request.

Required meaning:

- exactly one `scenario_id`
- one policy snapshot copied from the scenario at submission time
- execution and review state live here

Key mappings:

- `status` -> future `FHIR Task.status`
- `input_references[]` -> future `Task.input`
- `artifact_ids[]` -> links to generated outputs

### `ArtifactRecord`

Represents any generated or retrieved file-like output.

Required meaning:

- artifacts are reviewable deliverables or inputs persisted for lineage
- artifact type is storage-oriented, not clinical-meaning-oriented

Key mappings:

- `target_mappings[]` -> future `FHIR DocumentReference`, `DiagnosticReport`, `Observation`, or internal objects

### `AccessEventRecord`

Represents every external-system touch or sensitive platform access.

Required meaning:

- one record per meaningful access action
- outcome must be explicit: `pending`, `success`, `denied`, `failed`

Key mappings:

- later maps to `FHIR AuditEvent`
- `system`, `resource_type`, `resource_id`, `actor`, and `outcome` are the minimum audit fields

## Known Assumptions

- No automatic clinical write-back in Week 1.
- Human review is mandatory for both initial scenarios.
- Imaging access is read-only unless explicitly upgraded later.
- Patient-facing actions are out of scope.

## Known Open Questions

- Whether `CaseRecord` should later support multiple encounters per case.
- Whether artifact storage should distinguish source artifacts from generated artifacts as a top-level field.
- Whether audit export should be real-time or batch.
