from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from clinicalclaw.console_agent import SKILLS_DIR, build_console_agent, build_routed_task, route_with_llm
from clawagents.providers.llm import LLMMessage, LLMProvider, LLMResponse


class FakeRouterLLM(LLMProvider):
    name = "fake-router"

    async def chat(self, messages: list[LLMMessage], on_chunk=None, cancel_event=None, tools=None):
        return LLMResponse(
            content=(
                '{"workflow_id":"radiation_safety_monitor","confidence":0.93,'
                '"reason":"The request asks about a radiation incident alert.",'
                '"next_action":"Open safety and inspect the local case library."}'
            ),
            model="fake-router-model",
            tokens_used=42,
        )


class LowConfidenceRouterLLM(LLMProvider):
    name = "low-confidence-router"

    async def chat(self, messages: list[LLMMessage], on_chunk=None, cancel_event=None, tools=None):
        return LLMResponse(
            content=(
                '{"workflow_id":"neuro_longitudinal","confidence":0.42,'
                '"reason":"This might be a neuro longitudinal request, but the intent is not fully explicit.",'
                '"next_action":"Suggest the neuro module but stay in general chat.",'
                '"alternatives":["general_chat","radiation_safety_monitor"]}'
            ),
            model="fake-router-model",
            tokens_used=38,
        )


class BrokenRouterLLM(LLMProvider):
    name = "broken-router"

    async def chat(self, messages: list[LLMMessage], on_chunk=None, cancel_event=None, tools=None):
        raise RuntimeError("router unavailable")


def _build_client():
    from clawagents.gateway.server import create_app

    app, _, _ = create_app()
    return TestClient(app)


def test_route_with_llm_uses_structured_json():
    payload = __import__("asyncio").run(
        route_with_llm(FakeRouterLLM(), "Check whether this radiation incident should trigger an alert.")
    )

    assert payload["workflow_id"] == "radiation_safety_monitor"
    assert payload["target_module"] == "safety"
    assert payload["fallback"] is False


def test_route_with_llm_stays_home_when_confidence_is_low():
    payload = __import__("asyncio").run(
        route_with_llm(LowConfidenceRouterLLM(), "Review this clinical case for me.")
    )

    assert payload["workflow_id"] == "neuro_longitudinal"
    assert payload["target_module"] == "home"
    assert payload["suggested_module"] == "neuro"


def test_route_with_llm_falls_back_to_queue_when_llm_fails():
    payload = __import__("asyncio").run(
        route_with_llm(BrokenRouterLLM(), "Should this referral move into the urgent queue today?")
    )

    assert payload["workflow_id"] == "queue_triage"
    assert payload["target_module"] == "queue"
    assert payload["fallback"] is True


def test_route_with_llm_falls_back_to_diagnosis_when_llm_fails():
    payload = __import__("asyncio").run(
        route_with_llm(BrokenRouterLLM(), "Does this report suggest a missed vertebral fracture workup gap?")
    )

    assert payload["workflow_id"] == "missed_diagnosis_detection"
    assert payload["target_module"] == "diagnosis"
    assert payload["fallback"] is True


def test_route_with_llm_falls_back_to_screening_when_llm_fails():
    payload = __import__("asyncio").run(
        route_with_llm(BrokenRouterLLM(), "Does this positive FIT still need colonoscopy follow-up?")
    )

    assert payload["workflow_id"] == "screening_gap_closure"
    assert payload["target_module"] == "screening"
    assert payload["fallback"] is True


def test_build_routed_task_mentions_selected_workflow():
    task = build_routed_task(
        {"workflow_id": "neuro_longitudinal"},
        "Review the longitudinal MRI trend.",
    )

    assert "Workflow: neuro_longitudinal" in task
    assert "clinical_report_presentation" in task
    assert "clinical_report_generator" in task
    assert "neuro_report_generator" in task
    assert "neuro_report_presenter" in task
    assert "Review the longitudinal MRI trend." in task


def test_build_console_agent_loads_presentation_skill():
    fake_agent = MagicMock()

    with patch("clinicalclaw.console_agent.create_claw_agent", return_value=fake_agent) as create_agent:
        build_console_agent(MagicMock())

    assert create_agent.call_args.kwargs["skills"] == [SKILLS_DIR]
    allowed = fake_agent.allow_only_tools.call_args.args
    assert "use_skill" in allowed
    assert "list_skills" in allowed
    assert "get_findings_workspace" in allowed
    assert "get_queue_workspace" in allowed
    assert "get_diagnosis_workspace" in allowed
    assert "get_screening_workspace" in allowed
    assert "lesion_trend_plotter" in allowed
    assert "treatment_event_timeline_renderer" in allowed
    assert "key_slice_selector" in allowed
    assert "overlay_composer" in allowed
    assert "risk_signal_renderer" in allowed
    assert "render_clinical_report" in allowed
    assert "build_neuro_visualization_bundle" in allowed


def test_demo_execute_stream_emits_routed_and_done():
    class FakeAgent:
        async def invoke(self, task, on_event=None):
            if on_event:
                on_event("tool_call", {"name": "get_safety_case"})
                on_event("tool_result", {"name": "get_safety_case", "success": True, "preview": "ok"})
            return MagicMock(status="done", result="Mock streamed answer", iterations=2)

    async def fake_route_with_llm(llm, message):
        return {
            "workflow_id": "radiation_safety_monitor",
            "workflow": {
                "id": "radiation_safety_monitor",
                "title": "Radiation Safety Monitor",
                "module": "safety",
                "tools": ["get_safety_case"],
            },
            "target_module": "safety",
            "suggested_module": "safety",
            "confidence": 0.91,
            "reason": "Detected a radiation safety incident request.",
            "next_action": "Open safety workspace.",
            "alternatives": [{"module": "home", "title": "General Clinical Command"}],
            "fallback": False,
        }

    with patch("clawagents.gateway.server.load_config", return_value=MagicMock()), \
         patch("clawagents.gateway.server.get_default_model", return_value="gpt-5-mini"), \
         patch("clawagents.gateway.server.create_provider", return_value=MagicMock(name="fake-llm")), \
         patch("clawagents.gateway.server.build_console_agent", return_value=FakeAgent()), \
         patch("clawagents.gateway.server.route_with_llm", side_effect=fake_route_with_llm):
        client = _build_client()
        response = client.post("/api/demo/execute-stream", json={"message": "Alert the QA lead about this radiation issue."})

    assert response.status_code == 200
    assert "event: routed" in response.text
    assert "event: done" in response.text
    assert "Mock streamed answer" in response.text


def test_build_routed_task_mentions_findings_presentation_skill():
    task = build_routed_task(
        {"workflow_id": "findings_closure"},
        "Does this critical lab need escalation?",
    )

    assert "Workflow: findings_closure" in task
    assert "clinical_report_presentation" in task
    assert "findings_brief_presenter" in task


def test_build_routed_task_mentions_queue_presentation_skill():
    task = build_routed_task(
        {"workflow_id": "queue_triage"},
        "Should this referral move into the urgent queue?",
    )

    assert "Workflow: queue_triage" in task
    assert "clinical_report_presentation" in task
    assert "queue_triage_presenter" in task


def test_build_routed_task_mentions_missed_diagnosis_presentation_skill():
    task = build_routed_task(
        {"workflow_id": "missed_diagnosis_detection"},
        "Does this report suggest a missed vertebral fracture workup gap?",
    )

    assert "Workflow: missed_diagnosis_detection" in task
    assert "clinical_report_presentation" in task
    assert "missed_diagnosis_presenter" in task


def test_build_routed_task_mentions_screening_gap_presentation_skill():
    task = build_routed_task(
        {"workflow_id": "screening_gap_closure"},
        "Does this positive FIT still need colonoscopy follow-up?",
    )

    assert "Workflow: screening_gap_closure" in task
    assert "clinical_report_presentation" in task
    assert "screening_gap_presenter" in task
