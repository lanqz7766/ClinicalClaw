# DICOMweb Sandbox-Ready Flow

## Current Scope

ClinicalClaw now supports the minimum internal structure needed to move DICOMweb from mock-only behavior to sandbox-ready read access:

1. QIDO-RS study search
2. QIDO-RS series search
3. QIDO-RS instance search
4. WADO-RS study and series metadata reads
5. WADO-RS single-instance retrieval

## Config Surface

- `CLINICALCLAW_DICOMWEB_BASE_URL`
- `CLINICALCLAW_DICOMWEB_ACCESS_TOKEN`
- `CLINICALCLAW_IMAGING_CONNECTOR_MODE`

## Internal Types

- `ImagingStudySummary`
- `SeriesSummary`
- `InstanceSummary`
- `StudyMetadata`
- `RetrievedObject`

## Minimum Read Flow

The connector can now perform:

- `GET /studies`
- `GET /studies/{study}/series`
- `GET /studies/{study}/series/{series}/instances`
- `GET /studies/{study}/metadata`
- `GET /studies/{study}/series/{series}/metadata`
- `GET /studies/{study}/series/{series}/instances/{instance}`

and normalize the results into internal summaries and metadata objects.

## What Is Still Missing

- rendered image retrieval
- multipart response handling for advanced WADO cases
- paging support for large QIDO result sets
- retry/backoff and connector observability
- PACS vendor-specific compatibility testing
