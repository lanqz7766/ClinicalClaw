# Connector Layer

## Current Definition

ClinicalClaw now defines two read-only connector interfaces:

- `EHRConnector`
  - `get_launch_context`
  - `fetch_patient`
  - `fetch_encounter`
  - `fetch_patient_chart`
- `ImagingConnector`
  - `search_studies`
  - `get_study_metadata`
  - `get_series_metadata`

## Modes

- `mock`
  - fully local synthetic responses
  - default for stable Week 1 development
- `sandbox`
  - intended for standards-compliant test endpoints
  - currently uses the same HTTP-capable code path as live mode, but depends on configured base URLs and tokens
- `live`
  - reserved for later real integration work

## Current Implementations

- `SmartFHIRConnector`
  - mock chart bundle generation
  - HTTP skeleton for FHIR `Patient`, `Encounter`, `DiagnosticReport`, and `ImagingStudy`
- `DICOMWebConnector`
  - mock study search and metadata
  - HTTP skeleton for QIDO-style study queries and metadata reads

## Current Scope

- read-only only
- no write-back
- no token exchange workflow yet
- no retry policy or connector-specific observability yet

## Why This Is Enough For Now

This layer gives the platform a stable internal contract before real EPIC or PACS integration starts. The scenario runtime can now consume normalized connector outputs without coupling directly to FHIR or DICOMweb payloads.
