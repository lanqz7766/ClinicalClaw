# DICOMweb Sandbox-Ready Flow

## Current Scope

ClinicalClaw now supports the minimum internal structure needed to move DICOMweb from mock-only behavior to sandbox-ready read access:

1. QIDO-RS study search
2. QIDO-RS series search
3. QIDO-RS instance search
4. WADO-RS study and series metadata reads
5. WADO-RS single-instance retrieval

The current recommended public validation path is the Orthanc demo server:

- DICOMweb client demo: https://orthanc.uclouvain.be/demo/dicom-web/app/client/index.html
- live configured server list: https://orthanc.uclouvain.be/demo/dicom-web/servers?expand

At the time of validation, the demo reported its own public DICOMweb base URL as `https://orthanc.uclouvain.be/demo/dicom-web/`.

## Config Surface

- `CLINICALCLAW_DICOMWEB_BASE_URL`
- `CLINICALCLAW_DICOMWEB_ACCESS_TOKEN`
- `CLINICALCLAW_IMAGING_CONNECTOR_MODE`
- `CLINICALCLAW_DICOMWEB_SAMPLE_PATIENT_ID`

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

The local demo script now validates this flow end-to-end against Orthanc using a sample patient ID and the first discovered study/series/instance:

- [examples/10_dicomweb_sandbox_entry.py](/Users/qlan/Documents/Agent/ClinicalClaw/examples/10_dicomweb_sandbox_entry.py)

## What Is Still Missing

- rendered image retrieval
- multipart response handling for advanced WADO cases
- paging support for large QIDO result sets
- retry/backoff and connector observability
- PACS vendor-specific compatibility testing
