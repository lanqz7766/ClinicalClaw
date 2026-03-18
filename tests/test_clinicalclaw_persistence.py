from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from clinicalclaw.config import ClinicalClawSettings
from clinicalclaw.connectors.base import SmartTokenSet
from clinicalclaw.execution import ClinicalClawService
from clinicalclaw.models import MemoryOutcome, RunMemoryRecord, SmartTokenStateRecord
from clinicalclaw.store import SQLiteStore


def _settings(tmp_path: Path) -> ClinicalClawSettings:
    return ClinicalClawSettings(
        CLINICALCLAW_DATABASE_PATH=str(tmp_path / "state.db"),
        CLINICALCLAW_MEMORY_HISTORY_LIMIT=5,
        CLINICALCLAW_EHR_CONNECTOR_MODE="mock",
        CLINICALCLAW_IMAGING_CONNECTOR_MODE="mock",
        CLINICALCLAW_FHIR_CLIENT_ID="client-123",
        CLINICALCLAW_FHIR_REDIRECT_URI="http://localhost:8765/callback",
    )


def test_sqlite_store_persists_bootstrap_state(tmp_path):
    store = SQLiteStore(str(tmp_path / "state.db"))
    assert store.cases == {}

    store2 = SQLiteStore(str(tmp_path / "state.db"))
    assert store2.cases == {}


@pytest.mark.asyncio
async def test_service_records_run_memory_on_success(tmp_path):
    settings = _settings(tmp_path)
    service = ClinicalClawService(settings=settings)
    scenario = service.get_scenario("diagnostic_prep")
    assert scenario is not None

    fake_result = MagicMock(status="completed", result="review-ready summary", iterations=2)
    with pytest.MonkeyPatch.context() as mp:
        fake_agent = MagicMock()
        fake_agent.invoke = AsyncMock(return_value=fake_result)
        mp.setattr("clinicalclaw.execution.build_agent_for_scenario", lambda *args, **kwargs: fake_agent)
        result = await service.invoke_scenario(
            task="prepare brief",
            scenario_id="diagnostic_prep",
            llm=MagicMock(),
            requested_by="tester",
            external_patient_id="patient-123",
        )

    assert result.task_run_id
    memories = service.store.list_run_memories("diagnostic_prep", limit=5)
    assert len(memories) >= 1
    assert memories[0].outcome == "success"
    assert "completed" in memories[0].summary


@pytest.mark.asyncio
async def test_service_injects_recent_memory_into_prompt(tmp_path):
    settings = _settings(tmp_path)
    service = ClinicalClawService(settings=settings)
    service.store.add_run_memory(
        RunMemoryRecord(
            scenario_id="diagnostic_prep",
            outcome=MemoryOutcome.failure,
            summary="Previous run failed because the patient context was missing.",
            guidance="Require patient context before starting connector reads.",
            content="No patient identifier was available.",
        )
    )
    scenario = service.get_scenario("diagnostic_prep")
    assert scenario is not None

    prompt = service.build_prompt(
        "prepare brief",
        scenario,
        memory_context=service.build_memory_context("diagnostic_prep"),
    )

    assert "Relevant prior run memory" in prompt
    assert "Require patient context before starting connector reads." in prompt


@pytest.mark.asyncio
async def test_smart_launch_session_and_token_state_persist(tmp_path):
    settings = _settings(tmp_path)
    service = ClinicalClawService(settings=settings)

    launch_session = await service.begin_smart_launch(
        iss="https://sandbox.example.org",
        launch="launch-123",
        state="state-123",
    )
    token_state, launch_context = await service.complete_smart_launch(
        session_id=launch_session.id,
        callback_url="http://localhost:8765/callback?code=abc123&state=state-123&iss=https%3A%2F%2Fsandbox.example.org",
    )

    reloaded = SQLiteStore(str(tmp_path / "state.db"))
    assert reloaded.get_smart_launch_session(launch_session.id) is not None
    assert reloaded.list_smart_token_states(limit=1)[0].id == token_state.id
    assert launch_context.iss == "https://sandbox.example.org"


@pytest.mark.asyncio
async def test_complete_smart_launch_records_success_memory(tmp_path):
    settings = _settings(tmp_path)
    service = ClinicalClawService(settings=settings)

    launch_session = await service.begin_smart_launch(
        iss="https://sandbox.example.org",
        launch="launch-123",
        state="state-123",
    )
    await service.complete_smart_launch(
        session_id=launch_session.id,
        callback_url="http://localhost:8765/callback?code=abc123&state=state-123&iss=https%3A%2F%2Fsandbox.example.org",
    )

    memories = service.store.list_run_memories(service.SMART_LIVE_LAUNCH_MEMORY_ID, limit=5)
    assert len(memories) >= 1
    assert memories[0].outcome == MemoryOutcome.success
    assert "SMART launch completed" in memories[0].summary


@pytest.mark.asyncio
async def test_validate_smart_read_records_failure_memory(tmp_path):
    settings = _settings(tmp_path)
    service = ClinicalClawService(settings=settings)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            service.connectors.ehr,
            "fetch_patient_chart",
            AsyncMock(side_effect=RuntimeError("sandbox read exploded")),
        )
        with pytest.raises(RuntimeError, match="sandbox read exploded"):
            await service.validate_smart_read(
                patient_id="patient-123",
                encounter_id="enc-123",
                iss="https://sandbox.example.org",
            )

    memories = service.store.list_run_memories(service.SMART_LIVE_READ_MEMORY_ID, limit=5)
    assert len(memories) >= 1
    assert memories[0].outcome == MemoryOutcome.failure
    assert "sandbox read exploded" in memories[0].content


@pytest.mark.asyncio
async def test_scenario_prompt_includes_smart_live_memory(tmp_path):
    settings = _settings(tmp_path)
    service = ClinicalClawService(settings=settings)
    service.store.add_run_memory(
        RunMemoryRecord(
            scenario_id=service.SMART_LIVE_READ_MEMORY_ID,
            outcome=MemoryOutcome.success,
            summary="SMART live read succeeded for patient patient-123.",
            guidance="Reuse the validated SMART issuer before falling back to mock data.",
            content="diagnostic_reports=3",
        )
    )

    scenario = service.get_scenario("diagnostic_prep")
    assert scenario is not None
    prompt = service.build_prompt(
        "prepare brief",
        scenario,
        memory_context=service.build_memory_context("diagnostic_prep") + service.build_integration_memory_context(scenario),
    )

    assert "Relevant SMART live integration memory" in prompt
    assert "Reuse the validated SMART issuer" in prompt


@pytest.mark.asyncio
async def test_ensure_active_smart_token_refreshes_expired_token(tmp_path):
    settings = ClinicalClawSettings(
        CLINICALCLAW_DATABASE_PATH=str(tmp_path / "state.db"),
        CLINICALCLAW_MEMORY_HISTORY_LIMIT=5,
        CLINICALCLAW_EHR_CONNECTOR_MODE="sandbox",
        CLINICALCLAW_IMAGING_CONNECTOR_MODE="mock",
        CLINICALCLAW_FHIR_BASE_URL="https://sandbox.example.org",
        CLINICALCLAW_FHIR_CLIENT_ID="client-123",
        CLINICALCLAW_FHIR_REDIRECT_URI="http://localhost:8765/callback",
    )
    service = ClinicalClawService(settings=settings)
    expired = service.store.save_smart_token_state(
        SmartTokenStateRecord(
            session_id="launch-123",
            iss="https://sandbox.example.org",
            access_token="expired-access-token",
            refresh_token="refresh-123",
            scope="launch/patient patient/*.read",
            expires_in=1,
            metadata={"mode": "sandbox"},
        )
    )
    expired.created_at = expired.created_at.replace(year=2024)
    service.store.save_smart_token_state(expired)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            service.connectors.ehr,
            "refresh_access_token",
            AsyncMock(
                return_value=SmartTokenSet(
                    access_token="refreshed-access-token",
                    refresh_token="refresh-456",
                    expires_in=3600,
                    scope="launch/patient patient/*.read",
                    patient_id="patient-123",
                    metadata={"mode": "sandbox"},
                )
            ),
        )
        refreshed = await service.ensure_active_smart_token(iss="https://sandbox.example.org")

    assert refreshed is not None
    assert refreshed.access_token == "refreshed-access-token"
    assert service.connectors.ehr.access_token == "refreshed-access-token"
    memories = service.store.list_run_memories(service.SMART_LIVE_TOKEN_MEMORY_ID, limit=5)
    assert len(memories) >= 1
    assert memories[0].outcome == MemoryOutcome.success
