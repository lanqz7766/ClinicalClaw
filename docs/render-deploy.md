# Deploy To Render

This repository now includes a Render Blueprint at [render.yaml](/Users/qlan/Documents/Agent/ClinicalClaw/render.yaml).

Render's official docs say:

- web services should bind to `0.0.0.0` on the `PORT` environment variable
- each web service gets a public `onrender.com` hostname
- Blueprints can define `buildCommand`, `startCommand`, and `healthCheckPath`

Sources:

- [Render Web Services](https://render.com/docs/web-services)
- [Render Health Checks](https://render.com/docs/health-checks)
- [Render Blueprint YAML Reference](https://render.com/docs/blueprint-spec)
- [Render Environment Variables](https://render.com/docs/environment-variables)

## What This Blueprint Does

- installs the app with `pip install -e ".[all]"`
- starts the server with:
  - `clinicalclaw --serve --port ${PORT:-10000}`
- uses `/health` as the Render health check
- keeps the demo in mock connector mode so it can come up without FHIR or PACS credentials

## What You Need Before Deploying

- the repository pushed to GitHub
- a Render account
- at least one model provider key:
  - `OPENAI_API_KEY`
  - or `GEMINI_API_KEY`
  - or `ANTHROPIC_API_KEY`

Without a provider key, the app can start only if the chosen routes never invoke the LLM. For the actual interactive demo, set one provider key.

## Fastest Deployment Path

1. Push your current branch to GitHub.
2. In Render, click `New` -> `Blueprint`.
3. Connect the GitHub repo `lanqz7766/ClinicalClaw`.
4. Render will detect [render.yaml](/Users/qlan/Documents/Agent/ClinicalClaw/render.yaml).
5. In the environment variable screen, set:
   - `PROVIDER=gemini` and `GEMINI_API_KEY=...`
   - or `PROVIDER=openai` and `OPENAI_API_KEY=...`
6. Create the service.
7. Wait for the deploy to finish.
8. Open:
   - `https://<your-service>.onrender.com/demo`

## Recommended First Env Setup

If you want the least-friction first deploy:

- `PROVIDER=gemini`
- `GEMINI_API_KEY=...`

You can leave model fields unset unless you want to override defaults.

## Optional Hardening

- Set `GATEWAY_API_KEY` if you want Bearer protection on the main `/chat` and `/chat/stream` endpoints.
- Add a custom domain in Render after the first successful deploy.

## Important Caveat

The current demo UI itself is public once deployed. `GATEWAY_API_KEY` does not add a login screen to `/demo`.

If you want the whole demo page protected before sharing broadly, the next step is to add lightweight app-level auth in front of the demo routes.
