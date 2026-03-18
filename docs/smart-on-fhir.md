# SMART on FHIR Sandbox-Ready Flow

## Current Scope

ClinicalClaw now supports the minimum internal structure needed to move from mock-only behavior to sandbox-ready integration:

1. discover SMART endpoints
2. build an authorization URL
3. exchange an authorization code for a token set
4. use the resulting token for read-only FHIR requests

The current recommended local validation path is the public SMART Health IT Launcher sandbox:

- tutorial: https://docs.smarthealthit.org/tutorials/javascript/
- live SMART config: https://launch.smarthealthit.org/v/r4/fhir/.well-known/smart-configuration

The SMART tutorial explicitly calls the launcher the easiest sandbox to try and notes that it does not require app registration for this purpose.

## Config Surface

- `CLINICALCLAW_FHIR_BASE_URL`
- `CLINICALCLAW_FHIR_AUTHORIZE_URL`
- `CLINICALCLAW_FHIR_TOKEN_URL`
- `CLINICALCLAW_FHIR_CLIENT_ID`
- `CLINICALCLAW_FHIR_CLIENT_SECRET`
- `CLINICALCLAW_FHIR_REDIRECT_URI`
- `CLINICALCLAW_FHIR_SCOPE`
- `CLINICALCLAW_FHIR_ACCESS_TOKEN`
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

## Internal Types

- `SmartEndpoints`
- `SmartLaunchRequest`
- `SmartLaunchSession`
- `SmartCallbackParams`
- `SmartTokenSet`
- `LaunchContext`

## Minimum Read Flow

After token exchange, the connector can read:

- `Patient/{id}`
- `Encounter/{id}`
- `DiagnosticReport?patient={id}`
- `ImagingStudy?patient={id}`

and normalize them into a `PatientChartBundle`.

For local development, the example script can auto-complete the SMART Launcher redirect flow without opening a browser by calling the authorize URL with demo `login_success` and `auth_success` parameters and then persisting the resulting callback into SQLite.

ClinicalClaw now also records SMART live integration outcomes into run memory:

- launch/token success or failure under `smart_live_launch_validation`
- read-path success or failure under `smart_live_read_validation`
- token refresh success or failure under `smart_live_token_validation`

These memories can be injected into later scenario prompts when EHR read access is enabled, so validated SMART behavior and recent failures influence future scenario execution.

## What Is Still Missing

- real Epic sandbox credentials and registration
- production-grade refresh-token lifecycle policy
- Epic-specific launch peculiarities
- secure secret storage
