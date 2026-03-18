import pytest

from clinicalclaw.config import ClinicalClawSettings
from clinicalclaw.connectors import build_connector_bundle
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
