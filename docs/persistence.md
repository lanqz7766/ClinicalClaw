# Persistence Layer

## Current Scope

ClinicalClaw now supports a local SQLite persistence layer for development and sandbox integration.

Default path:

- `.clinicalclaw/state.db`

## Persisted State

- `CaseRecord`
- `TaskRunRecord`
- `ArtifactRecord`
- `AccessEventRecord`
- `RunMemoryRecord`
- `SmartLaunchSessionRecord`
- `SmartTokenStateRecord`

## Why This Matters

This is the first step from a stateless shell toward a recoverable platform:

- task and audit history survive restarts
- SMART launch sessions and token state can be resumed locally
- prior scenario failures and successes can guide later runs

## Run Memory

Each scenario run now writes a memory record on success or failure. These records are reused as lightweight guidance in future prompts for the same scenario.

Current behavior:

- success memory stores a short completion summary and clipped result content
- failure memory stores the exception type and clipped error content
- the latest memories are injected into future scenario prompts

## Security Note

Token state is currently stored in the local SQLite database for development convenience. This is acceptable for local sandbox work but not sufficient for production. Production work should move token storage to a hardened secret-management path.
