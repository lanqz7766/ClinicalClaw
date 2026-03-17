from fastapi.testclient import TestClient

from clinicalclaw.api import create_app


client = TestClient(create_app())


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["scenario_count"] >= 2


def test_list_scenarios():
    response = client.get("/v1/scenarios")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 2
    assert {item["id"] for item in payload} >= {"diagnostic_prep", "imaging_qc"}


def test_create_task():
    response = client.post(
        "/v1/tasks",
        json={
            "scenario_id": "diagnostic_prep",
            "requested_by": "week1-user",
            "external_patient_id": "patient-123",
            "note": "create draft shell task"
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["scenario_id"] == "diagnostic_prep"
    assert payload["requested_by"] == "week1-user"
