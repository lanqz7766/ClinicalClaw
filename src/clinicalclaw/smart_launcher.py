from __future__ import annotations

import base64
import json
from typing import Literal
from urllib.parse import parse_qs
from urllib.parse import urlencode
from urllib.parse import urlparse
from urllib.parse import urlunparse

import httpx


LaunchType = Literal[
    "provider-ehr",
    "patient-portal",
    "provider-standalone",
    "patient-standalone",
    "backend-service",
]
ClientType = Literal[
    "public",
    "confidential-symmetric",
    "confidential-asymmetric",
    "backend-service",
]
PKCEMode = Literal["none", "auto", "always"]

_LAUNCH_TYPES = [
    "provider-ehr",
    "patient-portal",
    "provider-standalone",
    "patient-standalone",
    "backend-service",
]
_CLIENT_TYPES = [
    "public",
    "confidential-symmetric",
    "confidential-asymmetric",
    "backend-service",
]
_PKCE_MODES = ["none", "auto", "always"]


def build_smart_launcher_sim_token(
    *,
    launch_type: LaunchType,
    patient_id: str = "",
    provider_id: str = "",
    encounter_id: str = "AUTO",
    skip_login: bool = True,
    skip_auth: bool = True,
    sim_ehr: bool = False,
    scope: str = "",
    redirect_uri: str = "",
    client_id: str = "",
    client_secret: str = "",
    auth_error: str = "",
    jwks_url: str = "",
    jwks: str = "",
    client_type: ClientType = "public",
    pkce: PKCEMode = "always",
    fhir_server: str = "",
) -> str:
    try:
        launch_index = _LAUNCH_TYPES.index(launch_type)
    except ValueError as exc:
        raise ValueError(f"Unsupported SMART launcher launch_type: {launch_type}") from exc

    try:
        client_type_index = _CLIENT_TYPES.index(client_type)
    except ValueError as exc:
        raise ValueError(f"Unsupported SMART launcher client_type: {client_type}") from exc

    try:
        pkce_index = _PKCE_MODES.index(pkce)
    except ValueError as exc:
        raise ValueError(f"Unsupported SMART launcher pkce mode: {pkce}") from exc

    payload = [
        launch_index,
        patient_id,
        provider_id,
        encounter_id,
        1 if skip_login else 0,
        1 if skip_auth else 0,
        1 if sim_ehr and "standalone" not in launch_type else 0,
        scope,
        redirect_uri,
        client_id,
        client_secret,
        auth_error,
        jwks_url,
        jwks,
        client_type_index,
        pkce_index,
        fhir_server,
    ]
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def build_smart_launcher_sim_issuer(
    *,
    launcher_base_url: str,
    fhir_version: str = "r4",
    launch_type: LaunchType = "patient-standalone",
    patient_id: str = "",
    provider_id: str = "",
    encounter_id: str = "AUTO",
    skip_login: bool = True,
    skip_auth: bool = True,
    sim_ehr: bool = False,
    scope: str = "",
    redirect_uri: str = "",
    client_id: str = "",
    client_secret: str = "",
    auth_error: str = "",
    jwks_url: str = "",
    jwks: str = "",
    client_type: ClientType = "public",
    pkce: PKCEMode = "always",
    fhir_server: str = "",
) -> str:
    base = launcher_base_url.rstrip("/")
    if not base:
        raise ValueError("SMART launcher base URL is required")

    token = build_smart_launcher_sim_token(
        launch_type=launch_type,
        patient_id=patient_id,
        provider_id=provider_id,
        encounter_id=encounter_id,
        skip_login=skip_login,
        skip_auth=skip_auth,
        sim_ehr=sim_ehr,
        scope=scope,
        redirect_uri=redirect_uri,
        client_id=client_id,
        client_secret=client_secret,
        auth_error=auth_error,
        jwks_url=jwks_url,
        jwks=jwks,
        client_type=client_type,
        pkce=pkce,
        fhir_server=fhir_server,
    )
    return f"{base}/v/{fhir_version}/sim/{token}/fhir"


def build_authorize_bypass_url(
    authorize_url: str,
    *,
    login_success: bool = True,
    auth_success: bool = True,
    patient_id: str = "",
    provider_id: str = "",
) -> str:
    parsed = urlparse(authorize_url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query["login_success"] = ["1" if login_success else "0"]
    query["auth_success"] = ["1" if auth_success else "0"]
    if patient_id:
        query["patient"] = [patient_id]
    if provider_id:
        query["provider"] = [provider_id]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


async def complete_demo_authorize_redirect(
    authorize_url: str,
    *,
    patient_id: str = "",
    provider_id: str = "",
    timeout_s: float = 15.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    bypass_url = build_authorize_bypass_url(
        authorize_url,
        patient_id=patient_id,
        provider_id=provider_id,
    )
    async with httpx.AsyncClient(
        follow_redirects=False,
        timeout=timeout_s,
        transport=transport,
    ) as client:
        response = await client.get(bypass_url)

    if response.status_code not in {301, 302, 303, 307, 308}:
        raise ValueError(
            f"Expected SMART sandbox authorize redirect, got {response.status_code}: {response.text}"
        )

    callback_url = response.headers.get("location", "")
    if not callback_url:
        raise ValueError("SMART sandbox redirect did not include a callback location")
    return callback_url
