import pytest

from clinicalclaw.config import ClinicalClawSettings
from clinicalclaw.connectors import build_connector_bundle
from clinicalclaw.connectors.base import ConnectorMode, SmartLaunchRequest
from clinicalclaw.connectors.fhir import SmartFHIRConnector
from clinicalclaw.execution import ClinicalClawService
from clinicalclaw.store import MemoryStore


@pytest.mark.asyncio
async def test_mock_fhir_connector_returns_chart_bundle():
    settings = ClinicalClawSettings()
    bundle = build_connector_bundle(settings)

    chart = await bundle.ehr.fetch_patient_chart(patient_id="patient-123")

    assert chart.patient.patient_id == "patient-123"
    assert len(chart.diagnostic_reports) >= 1
    assert "Hypertension" in chart.problems


@pytest.mark.asyncio
async def test_service_collects_connector_context_for_read_only_scenario():
    settings = ClinicalClawSettings()
    service = ClinicalClawService(settings=settings, store=MemoryStore())
    scenario = service.get_scenario("diagnostic_prep")
    assert scenario is not None

    task = service.store.create_task(
        service._create_task_request(
            scenario_id="diagnostic_prep",
            requested_by="tester",
            case_id=None,
            external_patient_id="patient-123",
            note=None,
        ),
        service.scenario_map,
    )

    context = await service.collect_connector_context(
        task_run_id=task.id,
        scenario=scenario,
        requested_by="tester",
        external_patient_id="patient-123",
    )

    assert "FHIR chart summary" in context
    assert "Imaging summary" in context
    assert len(service.store.tasks[task.id].access_event_ids) >= 2


@pytest.mark.asyncio
async def test_mock_smart_connector_builds_authorize_url():
    connector = SmartFHIRConnector(
        mode=ConnectorMode.mock,
        client_id="client-123",
        redirect_uri="http://localhost:8765/callback",
        scope="launch/patient patient/*.read",
    )
    url = await connector.build_authorize_url(
        SmartLaunchRequest(
            iss="https://sandbox.example.org/fhir/R4",
            launch="launch-token-1",
            client_id="client-123",
            redirect_uri="http://localhost:8765/callback",
            scope="launch/patient patient/*.read",
            state="state-xyz",
            code_challenge="challenge-abc",
        )
    )

    assert "response_type=code" in url
    assert "launch=launch-token-1" in url
    assert "state=state-xyz" in url
    assert "code_challenge=challenge-abc" in url


@pytest.mark.asyncio
async def test_sandbox_smart_connector_token_exchange_and_read_flow():
    def handler(request):
        if request.url.path == "/.well-known/smart-configuration":
            return httpx.Response(
                200,
                json={
                    "authorization_endpoint": "https://sandbox.example.org/oauth2/authorize",
                    "token_endpoint": "https://sandbox.example.org/oauth2/token",
                    "capabilities": ["launch-ehr", "client-public"],
                },
            )
        if request.url.path == "/oauth2/token":
            return httpx.Response(
                200,
                json={
                    "access_token": "sandbox-access-token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "launch/patient patient/*.read",
                    "patient": "sandbox-patient",
                    "encounter": "sandbox-encounter",
                },
            )
        if request.url.path == "/Patient/sandbox-patient":
            return httpx.Response(
                200,
                json={
                    "resourceType": "Patient",
                    "id": "sandbox-patient",
                    "name": [{"family": "Demo", "given": ["Alice"]}],
                    "birthDate": "1988-01-01",
                    "gender": "female",
                },
            )
        if request.url.path == "/Encounter/sandbox-encounter":
            return httpx.Response(
                200,
                json={
                    "resourceType": "Encounter",
                    "id": "sandbox-encounter",
                    "status": "in-progress",
                    "class": {"code": "AMB"},
                    "period": {"start": "2026-03-18T10:00:00Z"},
                },
            )
        if request.url.path == "/DiagnosticReport":
            return httpx.Response(
                200,
                json={
                    "entry": [
                        {"resource": {"resourceType": "DiagnosticReport", "id": "dr-100", "status": "final"}}
                    ]
                },
            )
        if request.url.path == "/ImagingStudy":
            return httpx.Response(
                200,
                json={
                    "entry": [
                        {"resource": {"resourceType": "ImagingStudy", "id": "img-100", "status": "available"}}
                    ]
                },
            )
        return httpx.Response(404, json={"error": "not found"})

    import httpx

    connector = SmartFHIRConnector(
        mode=ConnectorMode.sandbox,
        base_url="https://sandbox.example.org",
        client_id="client-123",
        redirect_uri="http://localhost:8765/callback",
        scope="launch/patient patient/*.read",
        transport=httpx.MockTransport(handler),
    )

    endpoints = await connector.discover_endpoints("https://sandbox.example.org")
    token_set = await connector.exchange_authorization_code(
        code="code-123",
        iss="https://sandbox.example.org",
    )
    chart = await connector.fetch_patient_chart(
        patient_id=token_set.patient_id or "sandbox-patient",
        encounter_id=token_set.encounter_id,
    )

    assert endpoints.authorize_url.endswith("/oauth2/authorize")
    assert token_set.access_token == "sandbox-access-token"
    assert chart.patient.display_name == "Demo, Alice"
    assert chart.encounter is not None
    assert chart.encounter.encounter_id == "sandbox-encounter"
    assert chart.diagnostic_reports[0].resource_id == "dr-100"
