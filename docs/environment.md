# Environment Baseline

## Development Target

- Recommended Python: `3.12`
- Minimum supported Python: `3.10`
- Package manager: `pip`
- Virtual environment: `.venv`

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

## Runtime Entry Point

Use the vendored ClawAgents gateway as the current external interface:

```bash
clawagents --serve
```

Default endpoint: `http://127.0.0.1:3000`

## Runtime Requirements

- One of the supported model providers when live LLM execution is needed:
  - OpenAI
  - Gemini
  - Anthropic
- Local writable directory for artifacts:
  - default: `.clinicalclaw/artifacts`
- Scenario definition directory:
  - default: `scenarios/`

## Environment Variables

- `CLINICALCLAW_APP_NAME`
- `CLINICALCLAW_ENVIRONMENT`
- `CLINICALCLAW_HOST`
- `CLINICALCLAW_PORT`
- `CLINICALCLAW_API_PREFIX`
- `CLINICALCLAW_SCENARIO_DIR`
- `CLINICALCLAW_ARTIFACT_DIR`
- `CLINICALCLAW_ENV_FILE`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`

## SMART Launcher Sandbox

For local SMART validation without private credentials, ClinicalClaw can derive a SMART Health IT Launcher issuer URL from `.env` values. The minimum practical set is:

- `CLINICALCLAW_EHR_CONNECTOR_MODE=sandbox`
- `CLINICALCLAW_FHIR_CLIENT_ID=clinicalclaw-local`
- `CLINICALCLAW_FHIR_REDIRECT_URI=http://127.0.0.1:8765/callback`
- `CLINICALCLAW_FHIR_SCOPE=launch/patient patient/*.read openid fhirUser`
- `CLINICALCLAW_SMART_LAUNCHER_BASE_URL=https://launch.smarthealthit.org`
- `CLINICALCLAW_SMART_LAUNCHER_FHIR_VERSION=r4`
- `CLINICALCLAW_SMART_LAUNCHER_LAUNCH_TYPE=patient-standalone`
- `CLINICALCLAW_SMART_LAUNCHER_PATIENT_ID=ae8a896e-bbd9-4e1a-a732-1568df9d7527`
- `CLINICALCLAW_SMART_LAUNCHER_SKIP_LOGIN=true`
- `CLINICALCLAW_SMART_LAUNCHER_SKIP_AUTH=true`
- `CLINICALCLAW_SMART_LAUNCHER_AUTO_CALLBACK=true`

The launcher tutorial says this is the easiest sandbox to try and does not require app registration:

- https://docs.smarthealthit.org/tutorials/javascript/

## Open Source Notes

- Keep all secrets out of the repository and only load them from `.env` or the shell.
- The shell platform is intentionally runnable without provider keys so contributors can work on API, scenarios, and workflow models before external integrations are ready.
- The external API surface should stay aligned with the vendored `clawagents` gateway until a separate deployment requirement justifies a ClinicalClaw-specific API.
- Production deployment should split platform API, execution sandbox, and storage into separate services.
