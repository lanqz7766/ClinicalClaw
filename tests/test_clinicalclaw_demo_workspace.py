from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from clinicalclaw.demo_workspace import DemoWorkspaceStore, demo_workspace_store


def _build_client():
    from clawagents.gateway.server import create_app

    app, _, _ = create_app()
    return TestClient(app)


def test_demo_workspace_snapshot_has_longitudinal_case():
    store = DemoWorkspaceStore()
    payload = store.snapshot()

    assert payload["default_case_id"] == "oasis3-demo-hippocampus"
    assert payload["workspace"]["analysis"]["accelerated_decline"] is True
    assert len(payload["workspace"]["timeline"]) == 4


def test_demo_workspace_chat_updates_messages():
    store = DemoWorkspaceStore()
    response = store.chat(
        case_id="oasis3-demo-hippocampus",
        message="Generate the hippocampal atrophy report for this patient.",
    )

    assert "accelerated bilateral hippocampal decline" in response["assistant"]["content"]
    assert response["workspace"]["review"]["status"] == "in_review"


def test_demo_workspace_review_updates_status():
    store = DemoWorkspaceStore()
    workspace = store.review(
        case_id="oasis3-demo-hippocampus",
        action="approve",
        comment="Mock reviewer approved the longitudinal report.",
    )

    assert workspace["review"]["status"] == "approved"
    assert "approved" in workspace["review"]["comment"].lower()


def test_demo_routes_expose_workspace_and_chat():
    with patch("clawagents.gateway.server.load_config", return_value=MagicMock()), \
         patch("clawagents.gateway.server.get_default_model", return_value="gpt-5-mini"), \
         patch("clawagents.gateway.server.create_provider", return_value=MagicMock(name="fake-llm")):
        client = _build_client()

        console_response = client.get("/api/demo/console")
        assert console_response.status_code == 200
        assert console_response.json()["title"] == "ClinicalClaw Console"

        workspace_response = client.get("/api/demo/workspace")
        assert workspace_response.status_code == 200
        assert workspace_response.json()["workspace"]["patient"]["display_name"] == "Subject OAS3-1142"

        command_response = client.post(
            "/api/demo/command",
            json={"message": "Check whether this radiation incident should trigger an alert."},
        )
        assert command_response.status_code == 200
        assert command_response.json()["target_module"] == "safety"

        findings_command_response = client.post(
            "/api/demo/command",
            json={"message": "Does this critical potassium result need urgent escalation?"},
        )
        assert findings_command_response.status_code == 200
        assert findings_command_response.json()["target_module"] == "findings"

        queue_command_response = client.post(
            "/api/demo/command",
            json={"message": "Should this referral move into the urgent queue today?"},
        )
        assert queue_command_response.status_code == 200
        assert queue_command_response.json()["target_module"] == "queue"

        diagnosis_command_response = client.post(
            "/api/demo/command",
            json={"message": "Does this report suggest a missed vertebral fracture workup gap?"},
        )
        assert diagnosis_command_response.status_code == 200
        assert diagnosis_command_response.json()["target_module"] == "diagnosis"

        chat_response = client.post(
            "/api/demo/chat",
            json={
                "case_id": "oasis3-demo-hippocampus",
                "message": "Explain why this mock case is considered high risk.",
            },
        )
        assert chat_response.status_code == 200
        assert "trend-based warning" in chat_response.json()["assistant"]["content"]

        demo_page = client.get("/demo")
        assert demo_page.status_code == 200
        assert "General Clinical Command" in demo_page.text
        assert "Workflows" in demo_page.text
        assert "Findings Closure" in demo_page.text
        assert "Queue Triage" in demo_page.text
        assert "Missed Diagnosis Review" in demo_page.text
        assert "/findings-demo" in demo_page.text
