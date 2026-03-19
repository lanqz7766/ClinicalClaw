from unittest.mock import MagicMock, patch
from pathlib import Path

from fastapi.testclient import TestClient

from clinicalclaw.findings_closure import findings_closure_store
from clinicalclaw.workflow_engine import load_workflow_map


def _build_client():
    from clawagents.gateway.server import create_app

    app, _, _ = create_app()
    return TestClient(app)


def test_findings_store_seeds_realistic_cases():
    payload = findings_closure_store.snapshot()

    assert payload["default_case_id"] == "finding_case_001"
    assert len(payload["cases"]) >= 3
    assert payload["workspace"]["workflow_id"] == "critical_lab_escalation"
    assert payload["workspace"]["risk_tier"] == "urgent"


def test_findings_store_explain_and_review_update_workspace():
    response = findings_closure_store.explain("finding_case_001", "Why was this case flagged?")
    assert "critical" in response["answer"].lower() or "urgent" in response["answer"].lower()
    assert response["workspace"]["audit"][0]["title"] == "Findings explainer used"

    reviewed = findings_closure_store.review("finding_case_001", "approve", "Escalation path confirmed.")
    assert reviewed["review"]["status"] == "approve"
    assert reviewed["review"]["comment"] == "Escalation path confirmed."
    assert reviewed["audit"][0]["title"] == "Reviewer action: approve"
    assert reviewed["status_steps"][-1]["state"] == "done"


def test_actionable_radiology_findings_workflow_uses_compact_findings_brief_contract():
    workflow = load_workflow_map("workflows")["actionable_radiology_findings"]

    assert workflow.presentation.skill == "findings_brief_presenter"
    assert workflow.presentation.sections == [
        "Signal",
        "Closure Check",
        "Recommended Next Step",
        "Review Status",
    ]


def test_findings_brief_presenter_mentions_radiology_signal_and_timeframe_guidance():
    skill_text = Path("skills/findings_brief_presenter/SKILL.md").read_text(encoding="utf-8")

    assert "Radiology-Specific Guidance" in skill_text
    assert "`Signal`" in skill_text
    assert "`Closure Check`" in skill_text
    assert "`Recommended Next Step`" in skill_text
    assert "same day" in skill_text.lower()
    assert "short-interval follow-up" in skill_text.lower()
    assert "owner" in skill_text.lower()


def test_findings_store_rerun_preserves_review_and_refreshes_audit():
    findings_closure_store.review("finding_case_002", "acknowledged", "Navigator picked up the case.")

    rerun = findings_closure_store.rerun("finding_case_002")

    assert rerun["review"]["status"] == "acknowledged"
    assert rerun["audit"][0]["title"] == "Findings engine rerun"
    assert rerun["risk_label"] in {"Watch", "Alert", "Urgent"}


def test_findings_routes_expose_workspace_and_page():
    with patch("clawagents.gateway.server.load_config", return_value=MagicMock()), \
         patch("clawagents.gateway.server.get_default_model", return_value="gpt-5-mini"), \
         patch("clawagents.gateway.server.create_provider", return_value=MagicMock(name="fake-llm")):
        client = _build_client()

        workspace_response = client.get("/api/findings/workspace")
        assert workspace_response.status_code == 200
        assert workspace_response.json()["workspace"]["title"]

        rerun_response = client.post("/api/findings/rerun", json={"case_id": "finding_case_001"})
        assert rerun_response.status_code == 200
        assert rerun_response.json()["risk_label"] in {"Watch", "Alert", "Urgent"}

        explain_response = client.post(
            "/api/findings/explain",
            json={"case_id": "finding_case_001", "question": "Would this trigger an email alert?"},
        )
        assert explain_response.status_code == 200
        answer = explain_response.json()["answer"].lower()
        assert "notification" in answer or "sent" in answer or "draft" in answer

        page_response = client.get("/findings-demo")
        assert page_response.status_code == 200
        assert "Findings Closure" in page_response.text


def test_findings_routes_return_expected_400_and_404_errors():
    with patch("clawagents.gateway.server.load_config", return_value=MagicMock()), \
         patch("clawagents.gateway.server.get_default_model", return_value="gpt-5-mini"), \
         patch("clawagents.gateway.server.create_provider", return_value=MagicMock(name="fake-llm")):
        client = _build_client()

        unknown_case_response = client.get("/api/findings/cases/not-a-case")
        assert unknown_case_response.status_code == 404
        assert "Unknown findings case" in unknown_case_response.json()["error"]

        invalid_rerun = client.post("/api/findings/rerun", content="{")
        assert invalid_rerun.status_code == 400

        missing_review_fields = client.post("/api/findings/review", json={"case_id": "finding_case_001"})
        assert missing_review_fields.status_code == 400
        assert "case_id and action are required" in missing_review_fields.json()["error"]

        unknown_review_case = client.post(
            "/api/findings/review",
            json={"case_id": "not-a-case", "action": "approve"},
        )
        assert unknown_review_case.status_code == 404

        missing_explain_fields = client.post("/api/findings/explain", json={"case_id": "finding_case_001"})
        assert missing_explain_fields.status_code == 400
        assert "case_id and question are required" in missing_explain_fields.json()["error"]

        unknown_explain_case = client.post(
            "/api/findings/explain",
            json={"case_id": "not-a-case", "question": "Why?"},
        )
        assert unknown_explain_case.status_code == 404
