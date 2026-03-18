from __future__ import annotations

import httpx
import pytest

import clinicalclaw.config as config_module
from clinicalclaw.config import ClinicalClawSettings
from clinicalclaw.config import load_settings
from clinicalclaw.smart_launcher import build_authorize_bypass_url
from clinicalclaw.smart_launcher import build_smart_launcher_sim_issuer
from clinicalclaw.smart_launcher import complete_demo_authorize_redirect


def test_build_smart_launcher_sim_issuer_contains_expected_path():
    issuer = build_smart_launcher_sim_issuer(
        launcher_base_url="https://launch.smarthealthit.org",
        fhir_version="r4",
        launch_type="patient-standalone",
        patient_id="patient-123",
        scope="launch/patient patient/*.read openid fhirUser",
        redirect_uri="http://127.0.0.1:8765/callback",
        client_id="clinicalclaw-local",
    )

    assert issuer.startswith("https://launch.smarthealthit.org/v/r4/sim/")
    assert issuer.endswith("/fhir")


def test_build_authorize_bypass_url_injects_demo_flags():
    url = build_authorize_bypass_url(
        "https://launch.smarthealthit.org/v/r4/auth/authorize?state=abc&scope=launch%2Fpatient",
        patient_id="patient-123",
    )

    assert "login_success=1" in url
    assert "auth_success=1" in url
    assert "patient=patient-123" in url


@pytest.mark.asyncio
async def test_complete_demo_authorize_redirect_returns_callback_url():
    expected = "http://127.0.0.1:8765/callback?code=code-123&state=state-123"

    def handler(request: httpx.Request) -> httpx.Response:
        assert "login_success=1" in str(request.url)
        return httpx.Response(302, headers={"location": expected})

    callback_url = await complete_demo_authorize_redirect(
        "https://launch.smarthealthit.org/v/r4/auth/authorize?state=state-123",
        patient_id="patient-123",
        transport=httpx.MockTransport(handler),
    )

    assert callback_url == expected


def test_clinicalclaw_settings_accepts_smart_launcher_env_fields():
    settings = ClinicalClawSettings(
        CLINICALCLAW_FHIR_CLIENT_ID="clinicalclaw-local",
        CLINICALCLAW_FHIR_REDIRECT_URI="http://127.0.0.1:8765/callback",
        CLINICALCLAW_FHIR_SCOPE="launch/patient patient/*.read openid fhirUser",
        CLINICALCLAW_SMART_LAUNCHER_BASE_URL="https://launch.smarthealthit.org",
        CLINICALCLAW_SMART_LAUNCHER_PATIENT_ID="patient-123",
    )

    assert settings.smart_launcher_base_url == "https://launch.smarthealthit.org"
    assert settings.smart_launcher_patient_id == "patient-123"


def test_load_settings_derives_fhir_base_url_from_smart_launcher(monkeypatch):
    monkeypatch.setenv("CLINICALCLAW_FHIR_CLIENT_ID", "clinicalclaw-local")
    monkeypatch.setenv("CLINICALCLAW_FHIR_REDIRECT_URI", "http://127.0.0.1:8765/callback")
    monkeypatch.setenv("CLINICALCLAW_FHIR_SCOPE", "launch/patient patient/*.read openid fhirUser")
    monkeypatch.setenv("CLINICALCLAW_SMART_LAUNCHER_BASE_URL", "https://launch.smarthealthit.org")
    monkeypatch.setenv("CLINICALCLAW_SMART_LAUNCHER_PATIENT_ID", "patient-123")
    monkeypatch.setenv("CLINICALCLAW_SMART_LAUNCHER_LAUNCH_TYPE", "patient-standalone")
    monkeypatch.delenv("CLINICALCLAW_FHIR_BASE_URL", raising=False)
    monkeypatch.setattr(config_module, "_loaded", True)
    monkeypatch.setattr(config_module, "_env_file", None)

    settings = load_settings()

    assert settings.fhir_base_url.startswith("https://launch.smarthealthit.org/v/r4/sim/")
    assert settings.fhir_base_url.endswith("/fhir")
