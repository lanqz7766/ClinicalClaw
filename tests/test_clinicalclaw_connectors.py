import httpx
import pytest

from clinicalclaw.config import ClinicalClawSettings
from clinicalclaw.connectors import build_connector_bundle
from clinicalclaw.connectors.base import ConnectorMode, SmartLaunchRequest
from clinicalclaw.connectors.fhir import SmartFHIRConnector, generate_pkce_pair
from clinicalclaw.connectors.imaging import DICOMWebConnector
from clinicalclaw.execution import ClinicalClawService
from clinicalclaw.store import MemoryStore


@pytest.mark.asyncio
async def test_mock_fhir_connector_returns_chart_bundle():
    settings = ClinicalClawSettings(
        CLINICALCLAW_EHR_CONNECTOR_MODE="mock",
        CLINICALCLAW_IMAGING_CONNECTOR_MODE="mock",
    )
    bundle = build_connector_bundle(settings)

    chart = await bundle.ehr.fetch_patient_chart(patient_id="patient-123")

    assert chart.patient.patient_id == "patient-123"
    assert len(chart.diagnostic_reports) >= 1
    assert "Hypertension" in chart.problems


@pytest.mark.asyncio
async def test_service_collects_connector_context_for_read_only_scenario():
    settings = ClinicalClawSettings(
        CLINICALCLAW_EHR_CONNECTOR_MODE="mock",
        CLINICALCLAW_IMAGING_CONNECTOR_MODE="mock",
    )
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


def test_pkce_pair_looks_valid():
    verifier, challenge = generate_pkce_pair()

    assert len(verifier) >= 43
    assert len(challenge) >= 43
    assert "=" not in challenge


@pytest.mark.asyncio
async def test_sandbox_smart_launch_session_and_callback_flow():
    def handler(request):
        if request.url.path == "/.well-known/smart-configuration":
            return httpx.Response(
                200,
                json={
                    "authorization_endpoint": "https://sandbox.example.org/oauth2/authorize",
                    "token_endpoint": "https://sandbox.example.org/oauth2/token",
                    "capabilities": ["launch-ehr", "launch-standalone", "client-public"],
                },
            )
        if request.url.path == "/oauth2/token":
            form = request.content.decode()
            assert "code_verifier=" in form
            return httpx.Response(
                200,
                json={
                    "access_token": "sandbox-access-token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "launch/patient patient/*.read",
                    "patient": "patient-xyz",
                    "encounter": "enc-xyz",
                },
            )
        return httpx.Response(404, json={"error": "not found"})

    connector = SmartFHIRConnector(
        mode=ConnectorMode.sandbox,
        base_url="https://sandbox.example.org",
        client_id="client-123",
        redirect_uri="http://localhost:8765/callback",
        scope="launch/patient patient/*.read",
        transport=httpx.MockTransport(handler),
    )

    session = await connector.begin_sandbox_launch(
        iss="https://sandbox.example.org",
        launch="launch-123",
        state="state-123",
    )
    token_set, launch_context = await connector.complete_sandbox_launch(
        callback_url="http://localhost:8765/callback?code=abc123&state=state-123&iss=https%3A%2F%2Fsandbox.example.org",
        session=session,
    )

    assert "launch=launch-123" in session.authorize_url
    assert token_set.patient_id == "patient-xyz"
    assert launch_context.patient_id == "patient-xyz"


@pytest.mark.asyncio
async def test_sandbox_smart_capability_validation():
    def handler(request):
        if request.url.path == "/.well-known/smart-configuration":
            return httpx.Response(
                200,
                json={
                    "authorization_endpoint": "https://sandbox.example.org/oauth2/authorize",
                    "token_endpoint": "https://sandbox.example.org/oauth2/token",
                    "capabilities": ["launch-standalone", "client-public"],
                },
            )
        return httpx.Response(404, json={"error": "not found"})

    connector = SmartFHIRConnector(
        mode=ConnectorMode.sandbox,
        base_url="https://sandbox.example.org",
        transport=httpx.MockTransport(handler),
    )
    missing = await connector.validate_capabilities(["launch-ehr", "client-public"], "https://sandbox.example.org")
    assert missing == ["launch-ehr"]


@pytest.mark.asyncio
async def test_sandbox_dicomweb_qido_and_wado_flow():
    def handler(request):
        if request.url.path == "/studies":
            return httpx.Response(
                200,
                json=[
                    {
                        "0020000D": {"Value": ["1.2.3.study"]},
                        "00100020": {"Value": ["patient-123"]},
                        "00080061": {"Value": ["CT"]},
                        "00081030": {"Value": ["CT Chest"]},
                        "00080020": {"Value": ["20260318"]},
                        "00201206": {"Value": [2]},
                    }
                ],
            )
        if request.url.path == "/studies/1.2.3.study/series":
            return httpx.Response(
                200,
                json=[
                    {
                        "0020000E": {"Value": ["1.2.3.series"]},
                        "00080060": {"Value": ["CT"]},
                        "0008103E": {"Value": ["Axial Lung"]},
                        "00201209": {"Value": [120]},
                    }
                ],
            )
        if request.url.path == "/studies/1.2.3.study/series/1.2.3.series/instances":
            return httpx.Response(
                200,
                json=[
                    {
                        "00080018": {"Value": ["1.2.3.instance"]},
                        "00200013": {"Value": [1]},
                    }
                ],
            )
        if request.url.path == "/studies/1.2.3.study/metadata":
            return httpx.Response(200, json=[{"mock": "study-metadata"}])
        if request.url.path == "/studies/1.2.3.study/series/1.2.3.series/metadata":
            return httpx.Response(200, json=[{"mock": "series-metadata"}])
        if request.url.path == "/studies/1.2.3.study/series/1.2.3.series/instances/1.2.3.instance":
            return httpx.Response(
                200,
                headers={"content-type": "application/dicom"},
                content=b"DICOM-BYTES",
            )
        return httpx.Response(404, json={"error": "not found"})

    connector = DICOMWebConnector(
        mode=ConnectorMode.sandbox,
        base_url="https://dicom.example.org",
        transport=httpx.MockTransport(handler),
    )

    studies = await connector.search_studies(patient_id="patient-123", modality="CT")
    series = await connector.search_series(study_instance_uid="1.2.3.study")
    instances = await connector.search_instances(
        study_instance_uid="1.2.3.study",
        series_instance_uid="1.2.3.series",
    )
    study_metadata = await connector.get_study_metadata("1.2.3.study")
    series_metadata = await connector.get_series_metadata(
        study_instance_uid="1.2.3.study",
        series_instance_uid="1.2.3.series",
    )
    retrieved = await connector.retrieve_instance(
        study_instance_uid="1.2.3.study",
        series_instance_uid="1.2.3.series",
        sop_instance_uid="1.2.3.instance",
    )

    assert studies[0].study_instance_uid == "1.2.3.study"
    assert series[0].series_instance_uid == "1.2.3.series"
    assert instances[0].sop_instance_uid == "1.2.3.instance"
    assert study_metadata.series[0]["mock"] == "study-metadata"
    assert series_metadata["metadata"][0]["mock"] == "series-metadata"
    assert retrieved.data == b"DICOM-BYTES"


@pytest.mark.asyncio
async def test_sandbox_dicomweb_retrieve_instance_supports_multipart():
    boundary = "test-boundary"
    multipart_body = (
        f"--{boundary}\r\n"
        "Content-Type: application/dicom\r\n"
        "MIME-Version: 1.0\r\n"
        "\r\n"
    ).encode() + b"DICOM-MULTIPART-BYTES\r\n" + f"--{boundary}--\r\n".encode()

    def handler(request):
        if request.url.path == "/studies/1.2.3.study/series/1.2.3.series/instances/1.2.3.instance":
            assert request.headers["accept"].startswith("multipart/related")
            return httpx.Response(
                200,
                headers={"content-type": f'multipart/related; type="application/dicom"; boundary={boundary}'},
                content=multipart_body,
            )
        return httpx.Response(404, json={"error": "not found"})

    connector = DICOMWebConnector(
        mode=ConnectorMode.sandbox,
        base_url="https://dicom.example.org",
        transport=httpx.MockTransport(handler),
    )

    retrieved = await connector.retrieve_instance(
        study_instance_uid="1.2.3.study",
        series_instance_uid="1.2.3.series",
        sop_instance_uid="1.2.3.instance",
    )

    assert retrieved.content_type == "application/dicom"
    assert retrieved.data == b"DICOM-MULTIPART-BYTES"
