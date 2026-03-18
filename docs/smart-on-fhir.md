# SMART on FHIR Sandbox-Ready Flow

## Current Scope

ClinicalClaw now supports the minimum internal structure needed to move from mock-only behavior to sandbox-ready integration:

1. discover SMART endpoints
2. build an authorization URL
3. exchange an authorization code for a token set
4. use the resulting token for read-only FHIR requests

## Config Surface

- `CLINICALCLAW_FHIR_BASE_URL`
- `CLINICALCLAW_FHIR_AUTHORIZE_URL`
- `CLINICALCLAW_FHIR_TOKEN_URL`
- `CLINICALCLAW_FHIR_CLIENT_ID`
- `CLINICALCLAW_FHIR_CLIENT_SECRET`
- `CLINICALCLAW_FHIR_REDIRECT_URI`
- `CLINICALCLAW_FHIR_SCOPE`
- `CLINICALCLAW_FHIR_ACCESS_TOKEN`

## Internal Types

- `SmartEndpoints`
- `SmartLaunchRequest`
- `SmartTokenSet`
- `LaunchContext`

## Minimum Read Flow

After token exchange, the connector can read:

- `Patient/{id}`
- `Encounter/{id}`
- `DiagnosticReport?patient={id}`
- `ImagingStudy?patient={id}`

and normalize them into a `PatientChartBundle`.

## What Is Still Missing

- PKCE helper generation
- automatic refresh-token handling
- SMART capability validation
- Epic-specific launch peculiarities
- persistence of token state
- secure secret storage
