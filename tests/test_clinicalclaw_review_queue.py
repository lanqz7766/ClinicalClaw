from pathlib import Path

from clinicalclaw.config import ClinicalClawSettings
from clinicalclaw.execution import ClinicalClawService
from clinicalclaw.models import ArtifactRecord, ArtifactType
from clinicalclaw.store import SQLiteStore


def _settings(tmp_path: Path) -> ClinicalClawSettings:
    return ClinicalClawSettings(
        CLINICALCLAW_DATABASE_PATH=str(tmp_path / "state.db"),
        CLINICALCLAW_FHIR_CLIENT_ID="client-123",
        CLINICALCLAW_FHIR_REDIRECT_URI="http://localhost:8765/callback",
    )


def _make_service(tmp_path: Path) -> ClinicalClawService:
    return ClinicalClawService(settings=_settings(tmp_path), store=SQLiteStore(str(tmp_path / "state.db")))


def test_review_queue_lists_in_review_tasks(tmp_path):
    service = _make_service(tmp_path)
    queue = service.list_review_queue()
    assert len(queue) >= 1
    assert all(task.status.value == "in_review" for task in queue)


def test_approve_and_file_task_updates_artifacts(tmp_path):
    service = _make_service(tmp_path)
    queue = service.list_review_queue()
    task = queue[0]
    artifact = service.store.add_artifact(
        ArtifactRecord(
            task_run_id=task.id,
            artifact_type=ArtifactType.json,
            title="review-payload",
            path=".clinicalclaw/artifacts/review.json",
        )
    )

    approved = service.approve_task(task.id, actor="reviewer-1", note="Looks good")
    assert approved.status.value == "approved"

    assert service.store.artifacts[artifact.id].status.value == "approved"

    filed = service.file_task(task.id, actor="reviewer-1", note="Filed to chart package")
    assert filed.status.value == "filed"

    assert service.store.artifacts[artifact.id].status.value == "exported"


def test_invalid_transition_raises(tmp_path):
    service = _make_service(tmp_path)
    queue = service.list_review_queue()
    task = queue[0]

    service.reject_task(task.id, actor="reviewer-1", note="Not acceptable yet")

    try:
        service.file_task(task.id, actor="reviewer-1")
    except ValueError as exc:
        assert "Invalid task transition" in str(exc)
    else:
        raise AssertionError("Expected invalid transition to raise ValueError")
