from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


def _build_client():
    from clawagents.gateway.server import create_app

    app, _, _ = create_app()
    return TestClient(app)


def test_chat_without_scenario_uses_default_gateway_path():
    fake_result = MagicMock(status="completed", result="plain-output", iterations=2)

    with patch("clawagents.gateway.server.load_config", return_value=MagicMock()), \
         patch("clawagents.gateway.server.get_default_model", return_value="gpt-5-mini"), \
         patch("clawagents.gateway.server.create_provider", return_value=MagicMock(name="fake-llm")), \
         patch("clawagents.gateway.server.create_claw_agent") as create_agent, \
         patch("clawagents.gateway.server.enqueue_command_in_lane", new_callable=AsyncMock) as enqueue:
        create_agent.return_value.invoke = AsyncMock(return_value=fake_result)

        async def passthrough(_lane, fn):
            return await fn()

        enqueue.side_effect = passthrough

        client = _build_client()
        response = client.post("/chat", json={"task": "hello"})

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["result"] == "plain-output"
        create_agent.assert_called_once()


def test_chat_with_scenario_routes_to_clinicalclaw_service():
    fake_agent_result = MagicMock(status="completed", result="scenario-output", iterations=4)
    fake_scenario_result = MagicMock(
        scenario=MagicMock(id="diagnostic_prep"),
        task_run_id="task_123",
        review_required=True,
        artifact_ids=["artifact_1"],
        access_event_ids=["access_1"],
        result=fake_agent_result,
    )

    with patch("clawagents.gateway.server.load_config", return_value=MagicMock()), \
         patch("clawagents.gateway.server.get_default_model", return_value="gpt-5-mini"), \
         patch("clawagents.gateway.server.create_provider", return_value=MagicMock(name="fake-llm")), \
         patch("clawagents.gateway.server.enqueue_command_in_lane", new_callable=AsyncMock) as enqueue, \
         patch("clawagents.gateway.server.ClinicalClawService") as service_cls:
        service = service_cls.return_value
        service.scenario_map = {"diagnostic_prep": MagicMock()}
        service.get_scenario.return_value = MagicMock()
        service.invoke_scenario = AsyncMock(return_value=fake_scenario_result)

        async def passthrough(_lane, fn):
            return await fn()

        enqueue.side_effect = passthrough

        client = _build_client()
        response = client.post(
            "/chat",
            json={
                "task": "prepare chart brief",
                "scenario_id": "diagnostic_prep",
                "requested_by": "tester",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["scenario_id"] == "diagnostic_prep"
        assert payload["task_run_id"] == "task_123"
        assert payload["review_required"] is True
        assert payload["result"] == "scenario-output"
        service.invoke_scenario.assert_called_once()


def test_chat_with_scenario_reauth_required_returns_structured_payload():
    fake_agent_result = MagicMock(
        status="reauth_required",
        result={
            "status": "reauth_required",
            "reason": "SMART token expired and no refresh_token is available.",
            "action": "launch SMART auth",
        },
        iterations=0,
    )
    fake_scenario_result = MagicMock(
        scenario=MagicMock(id="diagnostic_prep"),
        task_run_id="task_reauth",
        review_required=True,
        artifact_ids=[],
        access_event_ids=["access_1"],
        result=fake_agent_result,
    )

    with patch("clawagents.gateway.server.load_config", return_value=MagicMock()), \
         patch("clawagents.gateway.server.get_default_model", return_value="gpt-5-mini"), \
         patch("clawagents.gateway.server.create_provider", return_value=MagicMock(name="fake-llm")), \
         patch("clawagents.gateway.server.enqueue_command_in_lane", new_callable=AsyncMock) as enqueue, \
         patch("clawagents.gateway.server.ClinicalClawService") as service_cls:
        service = service_cls.return_value
        service.scenario_map = {"diagnostic_prep": MagicMock()}
        service.get_scenario.return_value = MagicMock()
        service.invoke_scenario = AsyncMock(return_value=fake_scenario_result)

        async def passthrough(_lane, fn):
            return await fn()

        enqueue.side_effect = passthrough

        client = _build_client()
        response = client.post(
            "/chat",
            json={
                "task": "prepare chart brief",
                "scenario_id": "diagnostic_prep",
                "requested_by": "tester",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is False
        assert payload["status"] == "reauth_required"
        assert payload["result"]["action"] == "launch SMART auth"


def test_queue_routes_expose_workspace_and_case():
    with patch("clawagents.gateway.server.load_config", return_value=MagicMock()), \
         patch("clawagents.gateway.server.get_default_model", return_value="gpt-5-mini"), \
         patch("clawagents.gateway.server.create_provider", return_value=MagicMock(name="fake-llm")):
        client = _build_client()

        queue_page = client.get("/queue-demo")
        assert queue_page.status_code == 200
        assert "Queue Triage" in queue_page.text

        workspace_response = client.get("/api/queue/workspace")
        assert workspace_response.status_code == 200
        payload = workspace_response.json()
        assert payload["default_case_id"]
        assert payload["workspace"]["title"]

        case_response = client.get(f"/api/queue/cases/{payload['default_case_id']}")
        assert case_response.status_code == 200
        assert case_response.json()["workflow_id"] in {"high_risk_referral_triage", "post_discharge_followup"}


def test_queue_routes_cover_rerun_review_explain_and_errors():
    with patch("clawagents.gateway.server.load_config", return_value=MagicMock()), \
         patch("clawagents.gateway.server.get_default_model", return_value="gpt-5-mini"), \
         patch("clawagents.gateway.server.create_provider", return_value=MagicMock(name="fake-llm")):
        client = _build_client()

        rerun_response = client.post("/api/queue/rerun", json={"case_id": "triage_case_001"})
        assert rerun_response.status_code == 200
        assert rerun_response.json()["workflow_id"] in {"high_risk_referral_triage", "post_discharge_followup"}

        review_response = client.post(
            "/api/queue/review",
            json={"case_id": "triage_case_001", "action": "approve", "comment": "Fast-track confirmed."},
        )
        assert review_response.status_code == 200
        assert review_response.json()["review"]["status"] == "approve"

        explain_response = client.post(
            "/api/queue/explain",
            json={"case_id": "triage_case_001", "question": "Why was this queued urgently?"},
        )
        assert explain_response.status_code == 200
        assert explain_response.json()["case_id"] == "triage_case_001"

        assert client.post("/api/queue/rerun", content="{").status_code == 400
        assert client.post("/api/queue/review", json={"case_id": "triage_case_001"}).status_code == 400
        assert client.post("/api/queue/explain", json={"case_id": "triage_case_001"}).status_code == 400
        assert client.post("/api/queue/rerun", json={"case_id": "missing-case"}).status_code == 404


def test_diagnosis_routes_expose_workspace_and_case():
    with patch("clawagents.gateway.server.load_config", return_value=MagicMock()), \
         patch("clawagents.gateway.server.get_default_model", return_value="gpt-5-mini"), \
         patch("clawagents.gateway.server.create_provider", return_value=MagicMock(name="fake-llm")):
        client = _build_client()

        workspace_response = client.get("/api/diagnosis/workspace")
        assert workspace_response.status_code == 200
        payload = workspace_response.json()
        assert payload["default_case_id"]
        assert payload["workspace"]["title"]

        case_response = client.get(f"/api/diagnosis/cases/{payload['default_case_id']}")
        assert case_response.status_code == 200
        assert case_response.json()["workflow_id"] == "missed_vertebral_fracture_detection"


def test_diagnosis_routes_cover_rerun_review_explain_and_errors():
    with patch("clawagents.gateway.server.load_config", return_value=MagicMock()), \
         patch("clawagents.gateway.server.get_default_model", return_value="gpt-5-mini"), \
         patch("clawagents.gateway.server.create_provider", return_value=MagicMock(name="fake-llm")):
        client = _build_client()

        rerun_response = client.post("/api/diagnosis/rerun", json={"case_id": "md_case_001"})
        assert rerun_response.status_code == 200
        assert rerun_response.json()["workflow_id"] == "missed_vertebral_fracture_detection"

        review_response = client.post(
            "/api/diagnosis/review",
            json={"case_id": "md_case_001", "action": "approve", "comment": "Workup started."},
        )
        assert review_response.status_code == 200
        assert review_response.json()["review"]["status"] == "approve"

        explain_response = client.post(
            "/api/diagnosis/explain",
            json={"case_id": "md_case_001", "question": "Why was this escalated?"},
        )
        assert explain_response.status_code == 200
        assert explain_response.json()["workspace"]["id"] == "md_case_001"

        assert client.post("/api/diagnosis/rerun", content="{").status_code == 400
        assert client.post("/api/diagnosis/review", json={"case_id": "md_case_001"}).status_code == 400
        assert client.post("/api/diagnosis/explain", json={"case_id": "md_case_001"}).status_code == 400
        assert client.post("/api/diagnosis/rerun", json={"case_id": "missing-case"}).status_code == 404


def test_screening_routes_expose_workspace_and_case():
    with patch("clawagents.gateway.server.load_config", return_value=MagicMock()), \
         patch("clawagents.gateway.server.get_default_model", return_value="gpt-5-mini"), \
         patch("clawagents.gateway.server.create_provider", return_value=MagicMock(name="fake-llm")):
        client = _build_client()

        workspace_response = client.get("/api/screening/workspace")
        assert workspace_response.status_code == 200
        payload = workspace_response.json()
        assert payload["default_case_id"]
        assert payload["workspace"]["title"]

        case_response = client.get(f"/api/screening/cases/{payload['default_case_id']}")
        assert case_response.status_code == 200
        assert case_response.json()["workflow_id"] == "screening_gap_positive_fit_followup"


def test_screening_routes_cover_rerun_review_explain_and_errors():
    with patch("clawagents.gateway.server.load_config", return_value=MagicMock()), \
         patch("clawagents.gateway.server.get_default_model", return_value="gpt-5-mini"), \
         patch("clawagents.gateway.server.create_provider", return_value=MagicMock(name="fake-llm")):
        client = _build_client()

        rerun_response = client.post("/api/screening/rerun", json={"case_id": "sg_case_001"})
        assert rerun_response.status_code == 200
        assert rerun_response.json()["workflow_id"] == "screening_gap_positive_fit_followup"

        review_response = client.post(
            "/api/screening/review",
            json={"case_id": "sg_case_001", "action": "approve", "comment": "Navigator outreach started."},
        )
        assert review_response.status_code == 200
        assert review_response.json()["review"]["status"] == "approve"

        explain_response = client.post(
            "/api/screening/explain",
            json={"case_id": "sg_case_001", "question": "Why is this gap still open?"},
        )
        assert explain_response.status_code == 200
        assert explain_response.json()["workspace"]["id"] == "sg_case_001"

        assert client.post("/api/screening/rerun", content="{").status_code == 400
        assert client.post("/api/screening/review", json={"case_id": "sg_case_001"}).status_code == 400
        assert client.post("/api/screening/explain", json={"case_id": "sg_case_001"}).status_code == 400
        assert client.post("/api/screening/rerun", json={"case_id": "missing-case"}).status_code == 404
