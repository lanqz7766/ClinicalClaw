# Week 1 Deliverables

## Goal

Build a runnable shell platform plus two scenario drafts.

## Implemented Shell Scope

- vendored `clawagents` runtime copied into the repository
- `clinicalclaw` platform package with:
  - application config
  - API shell
  - in-memory data models
  - scenario loader
  - runtime policy wrapper
- scenario drafts:
  - `diagnostic_prep`
  - `imaging_qc`

## Next Engineering Steps

1. Add SMART on FHIR launch handling and patient-context ingestion.
2. Add DICOMweb query and retrieval connectors.
3. Persist tasks, artifacts, and access events in a database.
4. Add review queue and approval transitions.
5. Attach audit and provenance exporters.
