from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import urlencode
from urllib.parse import parse_qs, urlparse
from typing import Any

import httpx

from clinicalclaw.connectors.base import (
    ConnectorError,
    ConnectorMode,
    EncounterSummary,
    LaunchContext,
    PatientChartBundle,
    PatientSummary,
    ResourceReference,
    SmartCallbackParams,
    SmartEndpoints,
    SmartLaunchRequest,
    SmartLaunchSession,
    SmartTokenSet,
)


class SmartFHIRConnector:
    connector_name = "smart_fhir"

    def __init__(
        self,
        *,
        mode: ConnectorMode,
        base_url: str = "",
        access_token: str = "",
        authorize_url: str = "",
        token_url: str = "",
        client_id: str = "",
        client_secret: str = "",
        redirect_uri: str = "",
        scope: str = "launch/patient patient/*.read encounter/*.read openid fhirUser",
        timeout_s: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.mode = mode
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.authorize_url = authorize_url
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scope = scope
        self.timeout_s = timeout_s
        self.transport = transport

    async def discover_endpoints(self, iss: str | None = None) -> SmartEndpoints:
        resolved_iss = (iss or self.base_url or "https://mock-fhir.example.org/fhir/R4").rstrip("/")
        if self.mode == ConnectorMode.mock:
            return SmartEndpoints(
                iss=resolved_iss,
                authorize_url=self.authorize_url or "https://mock-fhir.example.org/oauth2/authorize",
                token_url=self.token_url or "https://mock-fhir.example.org/oauth2/token",
                capabilities=["launch-ehr", "launch-standalone", "client-public"],
                metadata={"mode": self.mode.value},
            )

        if self.authorize_url and self.token_url:
            return SmartEndpoints(
                iss=resolved_iss,
                authorize_url=self.authorize_url,
                token_url=self.token_url,
                capabilities=["configured-endpoints"],
                metadata={"mode": self.mode.value, "source": "settings"},
            )

        payload = await self._get_json(".well-known/smart-configuration", iss_override=resolved_iss)
        return SmartEndpoints(
            iss=resolved_iss,
            authorize_url=payload.get("authorization_endpoint", ""),
            token_url=payload.get("token_endpoint", ""),
            introspection_url=payload.get("introspection_endpoint"),
            revocation_url=payload.get("revocation_endpoint"),
            capabilities=payload.get("capabilities", []),
            metadata={"mode": self.mode.value, "source": "smart-configuration"},
        )

    async def validate_capabilities(self, required: list[str], iss: str | None = None) -> list[str]:
        endpoints = await self.discover_endpoints(iss)
        if self.mode != ConnectorMode.mock and endpoints.metadata.get("source") == "settings":
            return []
        missing = [capability for capability in required if capability not in endpoints.capabilities]
        return missing

    async def begin_sandbox_launch(
        self,
        *,
        iss: str,
        launch: str | None = None,
        patient_id: str | None = None,
        encounter_id: str | None = None,
        state: str | None = None,
    ) -> SmartLaunchSession:
        if not self.client_id:
            raise ConnectorError("FHIR client_id is not configured")
        if not self.redirect_uri:
            raise ConnectorError("FHIR redirect_uri is not configured")

        code_verifier, code_challenge = generate_pkce_pair()
        launch_request = SmartLaunchRequest(
            iss=iss,
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            scope=self.scope,
            launch=launch,
            patient_id=patient_id,
            encounter_id=encounter_id,
            state=state or secrets.token_urlsafe(24),
            code_challenge=code_challenge,
            metadata={"mode": self.mode.value},
        )
        endpoints = await self.discover_endpoints(iss)
        authorize_url = await self.build_authorize_url(launch_request)
        return SmartLaunchSession(
            request=launch_request,
            endpoints=endpoints,
            state=launch_request.state,
            code_verifier=code_verifier,
            authorize_url=authorize_url,
            metadata={"mode": self.mode.value},
        )

    def parse_callback(self, callback_url: str) -> SmartCallbackParams:
        parsed = urlparse(callback_url)
        query = parse_qs(parsed.query)
        return SmartCallbackParams(
            code=_first(query, "code"),
            state=_first(query, "state"),
            iss=_first(query, "iss"),
            launch=_first(query, "launch"),
            error=_first(query, "error"),
            error_description=_first(query, "error_description"),
            patient_id=_first(query, "patient"),
            encounter_id=_first(query, "encounter"),
            metadata={"raw_query": parsed.query},
        )

    async def complete_sandbox_launch(
        self,
        *,
        callback_url: str,
        session: SmartLaunchSession,
    ) -> tuple[SmartTokenSet, LaunchContext]:
        callback = self.parse_callback(callback_url)
        if callback.error:
            raise ConnectorError(
                f"SMART callback returned error: {callback.error} ({callback.error_description or 'no description'})"
            )
        if callback.state != session.state:
            raise ConnectorError("SMART callback state mismatch")
        if not callback.code:
            raise ConnectorError("SMART callback missing authorization code")

        token_set = await self.exchange_authorization_code(
            code=callback.code,
            redirect_uri=session.request.redirect_uri,
            client_id=session.request.client_id,
            code_verifier=session.code_verifier,
            iss=callback.iss or session.request.iss,
        )
        launch_context = await self.get_launch_context(
            iss=callback.iss or session.request.iss,
            launch=callback.launch or session.request.launch,
            patient_id=token_set.patient_id or callback.patient_id or session.request.patient_id,
            encounter_id=token_set.encounter_id or callback.encounter_id or session.request.encounter_id,
        )
        return token_set, launch_context

    async def build_authorize_url(self, request: SmartLaunchRequest) -> str:
        endpoints = await self.discover_endpoints(request.iss)
        query: dict[str, str] = {
            "response_type": "code",
            "client_id": request.client_id,
            "redirect_uri": request.redirect_uri,
            "scope": request.scope,
            "aud": request.aud or request.iss,
        }
        if request.launch:
            query["launch"] = request.launch
        if request.state:
            query["state"] = request.state
        if request.code_challenge:
            query["code_challenge"] = request.code_challenge
            query["code_challenge_method"] = request.code_challenge_method
        return f"{endpoints.authorize_url}?{urlencode(query)}"

    async def exchange_authorization_code(
        self,
        *,
        code: str,
        redirect_uri: str | None = None,
        client_id: str | None = None,
        code_verifier: str | None = None,
        iss: str | None = None,
    ) -> SmartTokenSet:
        if self.mode == ConnectorMode.mock:
            token_set = SmartTokenSet(
                access_token="mock-access-token",
                token_type="Bearer",
                expires_in=3600,
                scope=self.scope,
                refresh_token="mock-refresh-token",
                patient_id="mock-patient-001",
                encounter_id="mock-encounter-001",
                metadata={"mode": self.mode.value, "code": code},
            )
            self.access_token = token_set.access_token
            return token_set

        endpoints = await self.discover_endpoints(iss)
        payload: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri or self.redirect_uri,
            "client_id": client_id or self.client_id,
        }
        if code_verifier:
            payload["code_verifier"] = code_verifier
        if self.client_secret:
            payload["client_secret"] = self.client_secret

        token_payload = await self._post_form(endpoints.token_url, payload)
        token_set = SmartTokenSet(
            access_token=token_payload.get("access_token", ""),
            token_type=token_payload.get("token_type", "Bearer"),
            expires_in=token_payload.get("expires_in"),
            scope=token_payload.get("scope", self.scope),
            refresh_token=token_payload.get("refresh_token"),
            patient_id=token_payload.get("patient"),
            encounter_id=token_payload.get("encounter"),
            id_token=token_payload.get("id_token"),
            issued_token_type=token_payload.get("issued_token_type"),
            metadata={"mode": self.mode.value},
        )
        if not token_set.access_token:
            raise ConnectorError("Token exchange succeeded but no access_token was returned")
        self.access_token = token_set.access_token
        return token_set

    async def get_launch_context(
        self,
        *,
        iss: str | None = None,
        launch: str | None = None,
        patient_id: str | None = None,
        encounter_id: str | None = None,
    ) -> LaunchContext:
        if self.mode == ConnectorMode.mock:
            return LaunchContext(
                iss=iss or "https://mock-fhir.example.org/fhir/R4",
                launch=launch or "mock-launch-token",
                patient_id=patient_id or "mock-patient-001",
                encounter_id=encounter_id or "mock-encounter-001",
                scope=self.scope,
                metadata={"mode": self.mode.value},
            )

        return LaunchContext(
            iss=iss or self.base_url,
            launch=launch,
            patient_id=patient_id,
            encounter_id=encounter_id,
            scope=self.scope,
            metadata={"mode": self.mode.value},
        )

    async def refresh_access_token(
        self,
        *,
        refresh_token: str,
        scope: str | None = None,
        iss: str | None = None,
    ) -> SmartTokenSet:
        if not refresh_token:
            raise ConnectorError("SMART refresh token is required")

        if self.mode == ConnectorMode.mock:
            token_set = SmartTokenSet(
                access_token="mock-refreshed-access-token",
                token_type="Bearer",
                expires_in=3600,
                scope=scope or self.scope,
                refresh_token=refresh_token,
                patient_id="mock-patient-001",
                encounter_id="mock-encounter-001",
                metadata={"mode": self.mode.value, "refresh": "mock"},
            )
            self.access_token = token_set.access_token
            return token_set

        endpoints = await self.discover_endpoints(iss)
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
        }
        if scope or self.scope:
            payload["scope"] = scope or self.scope
        if self.client_secret:
            payload["client_secret"] = self.client_secret

        token_payload = await self._post_form(endpoints.token_url, payload)
        token_set = SmartTokenSet(
            access_token=token_payload.get("access_token", ""),
            token_type=token_payload.get("token_type", "Bearer"),
            expires_in=token_payload.get("expires_in"),
            scope=token_payload.get("scope", scope or self.scope),
            refresh_token=token_payload.get("refresh_token", refresh_token),
            patient_id=token_payload.get("patient"),
            encounter_id=token_payload.get("encounter"),
            id_token=token_payload.get("id_token"),
            issued_token_type=token_payload.get("issued_token_type"),
            metadata={"mode": self.mode.value, "refresh": "oauth2"},
        )
        if not token_set.access_token:
            raise ConnectorError("SMART refresh succeeded but no access_token was returned")
        self.access_token = token_set.access_token
        return token_set

    async def fetch_patient(self, patient_id: str) -> PatientSummary:
        if self.mode == ConnectorMode.mock:
            return PatientSummary(
                patient_id=patient_id,
                display_name="Demo, Patient",
                birth_date="1978-04-16",
                sex="female",
                mrn="MRN-CLINICALCLAW-001",
                metadata={"source": "mock"},
            )

        payload = await self._get_json(f"Patient/{patient_id}")
        names = payload.get("name", [])
        display_name = "Unknown Patient"
        if names:
            first = names[0]
            given = " ".join(first.get("given", []))
            family = first.get("family", "")
            display_name = ", ".join(part for part in [family, given] if part)
        return PatientSummary(
            patient_id=payload.get("id", patient_id),
            display_name=display_name,
            birth_date=payload.get("birthDate"),
            sex=payload.get("gender"),
            metadata={"source": self.mode.value},
        )

    async def fetch_encounter(self, encounter_id: str) -> EncounterSummary:
        if self.mode == ConnectorMode.mock:
            return EncounterSummary(
                encounter_id=encounter_id,
                status="in-progress",
                encounter_class="AMB",
                start="2026-03-18T09:00:00Z",
                metadata={"source": "mock"},
            )

        payload = await self._get_json(f"Encounter/{encounter_id}")
        encounter_class = None
        if isinstance(payload.get("class"), dict):
            encounter_class = payload["class"].get("code")
        period = payload.get("period", {})
        return EncounterSummary(
            encounter_id=payload.get("id", encounter_id),
            status=payload.get("status", "unknown"),
            encounter_class=encounter_class,
            start=period.get("start"),
            end=period.get("end"),
            metadata={"source": self.mode.value},
        )

    async def fetch_patient_chart(
        self,
        *,
        patient_id: str,
        encounter_id: str | None = None,
    ) -> PatientChartBundle:
        if self.mode == ConnectorMode.mock:
            return PatientChartBundle(
                patient=await self.fetch_patient(patient_id),
                encounter=await self.fetch_encounter(encounter_id or "mock-encounter-001"),
                diagnostic_reports=[
                    ResourceReference("DiagnosticReport", "dr-001", "Chest CT narrative"),
                    ResourceReference("DiagnosticReport", "dr-002", "Pulmonary follow-up report"),
                ],
                imaging_studies=[
                    ResourceReference("ImagingStudy", "img-001", "CT Chest without contrast"),
                    ResourceReference("ImagingStudy", "img-002", "Chest X-ray PA/LAT"),
                ],
                medications=["Lisinopril 10 mg daily", "Metformin 500 mg BID"],
                problems=["Hypertension", "Type 2 diabetes"],
                observations=["Latest A1c 6.9%", "Creatinine normal"],
                metadata={"mode": self.mode.value},
            )

        patient = await self.fetch_patient(patient_id)
        encounter = await self.fetch_encounter(encounter_id) if encounter_id else None
        reports = await self._search_resource_refs("DiagnosticReport", patient_id)
        imaging = await self._search_resource_refs("ImagingStudy", patient_id)

        return PatientChartBundle(
            patient=patient,
            encounter=encounter,
            diagnostic_reports=reports,
            imaging_studies=imaging,
            metadata={"mode": self.mode.value},
        )

    async def _search_resource_refs(self, resource_type: str, patient_id: str) -> list[ResourceReference]:
        payload = await self._get_json(f"{resource_type}?patient={patient_id}")
        entries = payload.get("entry", [])
        references: list[ResourceReference] = []
        for entry in entries:
            resource = entry.get("resource", {})
            references.append(
                ResourceReference(
                    resource_type=resource.get("resourceType", resource_type),
                    resource_id=resource.get("id", ""),
                    display=resource.get("status", ""),
                )
            )
        return references

    async def _get_json(self, path: str, iss_override: str | None = None) -> dict[str, Any]:
        request_base = (iss_override or self.base_url).rstrip("/")
        if not request_base:
            raise ConnectorError("FHIR base URL is not configured")

        headers = {"Accept": "application/fhir+json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        async with httpx.AsyncClient(
            timeout=self.timeout_s,
            headers=headers,
            transport=self.transport,
        ) as client:
            response = await client.get(f"{request_base}/{path.lstrip('/')}")
            response.raise_for_status()
            return response.json()

    async def _post_form(self, url: str, payload: dict[str, str]) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        async with httpx.AsyncClient(
            timeout=self.timeout_s,
            headers=headers,
            transport=self.transport,
        ) as client:
            response = await client.post(url, data=payload)
            response.raise_for_status()
            return response.json()


def generate_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def _first(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    if not values:
        return None
    return values[0]
