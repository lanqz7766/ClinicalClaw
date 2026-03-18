from __future__ import annotations

import logging
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse

from clinicalclaw.config import ClinicalClawSettings
from clinicalclaw.connectors import ConnectorBundle
from clinicalclaw.connectors.base import ConnectorMode
from clinicalclaw.connectors.fhir import SmartFHIRConnector
from clinicalclaw.connectors.imaging import DICOMWebConnector
from clinicalclaw.execution import ClinicalClawService
from clinicalclaw.store import MemoryStore


def _build_refresh_capable_smart_app() -> tuple[FastAPI, dict[str, object]]:
    app = FastAPI()
    state: dict[str, object] = {
        "last_scope": "",
        "current_access_token": "access-1",
        "refresh_used": False,
    }

    @app.get("/fhir/.well-known/smart-configuration")
    async def smart_configuration():
        return {
            "authorization_endpoint": "http://smart.mock/auth/authorize",
            "token_endpoint": "http://smart.mock/auth/token",
            "capabilities": [
                "launch-ehr",
                "client-public",
                "permission-offline",
            ],
        }

    @app.get("/auth/authorize")
    async def authorize(request: Request):
        params = request.query_params
        state["last_scope"] = params.get("scope", "")
        redirect_uri = params["redirect_uri"]
        callback = (
            f"{redirect_uri}?code=code-123&state={params['state']}"
            "&iss=http%3A%2F%2Fsmart.mock%2Ffhir"
        )
        return RedirectResponse(callback, status_code=302)

    @app.post("/auth/token")
    async def token(request: Request):
        form = {key: values[0] for key, values in parse_qs((await request.body()).decode()).items()}
        if form["grant_type"] == "authorization_code":
            return {
                "access_token": "access-1",
                "refresh_token": "refresh-1",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": "launch openid fhirUser offline_access patient/*.read",
                "patient": "patient-123",
            }
        if form["grant_type"] == "refresh_token":
            state["refresh_used"] = True
            state["current_access_token"] = "access-2"
            return {
                "access_token": "access-2",
                "refresh_token": "refresh-2",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": form.get("scope", ""),
                "patient": "patient-123",
            }
        return JSONResponse({"error": "unsupported grant"}, status_code=400)

    def _auth_ok(request: Request) -> bool:
        return request.headers.get("authorization") == f"Bearer {state['current_access_token']}"

    @app.get("/fhir/Patient/patient-123")
    async def patient(request: Request):
        if not _auth_ok(request):
            return JSONResponse({"error": "invalid token"}, status_code=401)
        return {
            "resourceType": "Patient",
            "id": "patient-123",
            "name": [{"family": "Refresh", "given": ["Ready"]}],
            "birthDate": "1990-01-01",
            "gender": "female",
        }

    @app.get("/fhir/DiagnosticReport")
    async def diagnostic_report(request: Request, patient: str):
        if not _auth_ok(request):
            return JSONResponse({"error": "invalid token"}, status_code=401)
        return {
            "entry": [
                {"resource": {"resourceType": "DiagnosticReport", "id": f"dr-{patient}", "status": "final"}}
            ]
        }

    @app.get("/fhir/ImagingStudy")
    async def imaging_study(request: Request, patient: str):
        if not _auth_ok(request):
            return JSONResponse({"error": "invalid token"}, status_code=401)
        return {
            "entry": [
                {"resource": {"resourceType": "ImagingStudy", "id": f"img-{patient}", "status": "available"}}
            ]
        }

    return app, state


def _build_no_refresh_smart_app() -> FastAPI:
    app = FastAPI()

    @app.get("/fhir/.well-known/smart-configuration")
    async def smart_configuration():
        return {
            "authorization_endpoint": "http://smart.norefresh/auth/authorize",
            "token_endpoint": "http://smart.norefresh/auth/token",
            "capabilities": ["launch-ehr", "client-public"],
        }

    @app.get("/auth/authorize")
    async def authorize(request: Request):
        params = request.query_params
        callback = (
            f"{params['redirect_uri']}?code=code-123&state={params['state']}"
            "&iss=http%3A%2F%2Fsmart.norefresh%2Ffhir"
        )
        return RedirectResponse(callback, status_code=302)

    @app.post("/auth/token")
    async def token():
        return {
            "access_token": "access-1",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "launch openid fhirUser offline_access patient/*.read",
            "patient": "patient-123",
        }

    return app


@pytest.mark.asyncio
async def test_mock_smart_e2e_refresh_flow(caplog):
    app, state = _build_refresh_capable_smart_app()
    transport = httpx.ASGITransport(app=app)
    settings = ClinicalClawSettings(
        CLINICALCLAW_EHR_CONNECTOR_MODE="sandbox",
        CLINICALCLAW_FHIR_BASE_URL="http://smart.mock/fhir",
        CLINICALCLAW_FHIR_CLIENT_ID="mock-client",
        CLINICALCLAW_FHIR_REDIRECT_URI="http://client.local/callback",
        CLINICALCLAW_FHIR_SCOPE="launch openid fhirUser offline_access patient/*.read",
    )
    connectors = ConnectorBundle(
        ehr=SmartFHIRConnector(
            mode=ConnectorMode.sandbox,
            base_url=settings.fhir_base_url,
            client_id=settings.fhir_client_id,
            redirect_uri=settings.fhir_redirect_uri,
            scope=settings.fhir_scope,
            transport=transport,
        ),
        imaging=DICOMWebConnector(mode=ConnectorMode.mock),
    )
    service = ClinicalClawService(settings=settings, store=MemoryStore(), connectors=connectors)

    session = await service.begin_smart_launch(iss=settings.fhir_base_url)
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        response = await client.get(session.authorize_url)
    callback_url = response.headers["location"]
    token_state, _ = await service.complete_smart_launch(
        session_id=session.id,
        callback_url=callback_url,
    )

    assert token_state.refresh_token == "refresh-1"
    assert state["last_scope"] == "launch openid fhirUser offline_access patient/*.read"

    token_state.created_at = token_state.created_at.replace(year=2024)
    service.store.save_smart_token_state(token_state)

    with caplog.at_level(logging.INFO):
        chart = await service.validate_smart_read(
            patient_id="patient-123",
            iss=settings.fhir_base_url,
        )

    assert state["refresh_used"] is True
    refreshed = service.get_latest_smart_token_state(iss=settings.fhir_base_url)
    assert refreshed is not None
    assert refreshed.access_token == "access-2"
    assert chart.patient.patient_id == "patient-123"
    assert len(chart.diagnostic_reports) == 1
    assert len(chart.imaging_studies) == 1
    assert any("SMART token refresh succeeded" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_smart_launch_marks_no_refresh_capable_environment(caplog):
    app = _build_no_refresh_smart_app()
    transport = httpx.ASGITransport(app=app)
    settings = ClinicalClawSettings(
        CLINICALCLAW_EHR_CONNECTOR_MODE="sandbox",
        CLINICALCLAW_FHIR_BASE_URL="http://smart.norefresh/fhir",
        CLINICALCLAW_FHIR_CLIENT_ID="mock-client",
        CLINICALCLAW_FHIR_REDIRECT_URI="http://client.local/callback",
        CLINICALCLAW_FHIR_SCOPE="launch openid fhirUser offline_access patient/*.read",
    )
    connectors = ConnectorBundle(
        ehr=SmartFHIRConnector(
            mode=ConnectorMode.sandbox,
            base_url=settings.fhir_base_url,
            client_id=settings.fhir_client_id,
            redirect_uri=settings.fhir_redirect_uri,
            scope=settings.fhir_scope,
            transport=transport,
        ),
        imaging=DICOMWebConnector(mode=ConnectorMode.mock),
    )
    service = ClinicalClawService(settings=settings, store=MemoryStore(), connectors=connectors)

    session = await service.begin_smart_launch(iss=settings.fhir_base_url)
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        response = await client.get(session.authorize_url)

    with caplog.at_level(logging.WARNING):
        token_state, _ = await service.complete_smart_launch(
            session_id=session.id,
            callback_url=response.headers["location"],
        )

    assert token_state.refresh_token is None
    assert token_state.metadata["no_refresh_capable"] is True
    assert any("did not return refresh_token" in record.message for record in caplog.records)
