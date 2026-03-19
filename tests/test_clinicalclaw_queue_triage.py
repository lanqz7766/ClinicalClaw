from pathlib import Path

from clinicalclaw.queue_triage import queue_triage_store
from clinicalclaw.workflow_engine import WorkflowFamily, load_workflow_map
from clinicalclaw.workflow_families.queue_triage import QueueTriageFamily


def test_queue_triage_workflows_load_and_group_into_family():
    workflows = load_workflow_map("workflows")

    assert "high_risk_referral_triage" in workflows
    assert workflows["high_risk_referral_triage"].family == WorkflowFamily.queue_triage
    assert workflows["post_discharge_followup"].family == WorkflowFamily.queue_triage


def test_queue_triage_workflows_use_compact_case_centric_presentation():
    workflows = load_workflow_map("workflows")
    referral = workflows["high_risk_referral_triage"]
    discharge = workflows["post_discharge_followup"]

    assert referral.presentation.skill == "queue_triage_presenter"
    assert referral.presentation.sections == [
        "Case Signal",
        "Queue Status",
        "Recommended Queue Move",
        "Review Status",
    ]
    assert referral.presentation.tone == "compact_case_triage"
    assert "brief_focus" in referral.family_config

    assert discharge.presentation.skill == "queue_triage_presenter"
    assert discharge.presentation.sections == [
        "Case Signal",
        "Timing Window",
        "Recommended Next Step",
        "Review Status",
    ]
    assert discharge.presentation.tone == "compact_case_triage"
    assert "brief_focus" in discharge.family_config


def test_queue_triage_family_evaluates_high_risk_referral():
    workflow = load_workflow_map("workflows")["high_risk_referral_triage"]
    family = QueueTriageFamily()

    evaluation = family.evaluate(
        workflow,
        {
            "patient_id": "demo-queue-1",
            "referral_text": "Progressive weakness, speech change, and worsening gait. Please review today.",
            "completion_state": "unknown",
            "priority_score": 94,
        },
    )

    assert evaluation.workflow_id == "high_risk_referral_triage"
    assert evaluation.risk_label == "urgent"
    assert evaluation.disposition == "escalate_immediately"
    assert evaluation.review_required is True
    assert "urgent triage lane" in evaluation.queue_recommendation.lower()


def test_queue_triage_family_detects_already_routed_case():
    workflow = load_workflow_map("workflows")["high_risk_referral_triage"]
    family = QueueTriageFamily()

    evaluation = family.evaluate(
        workflow,
        {
            "referral_text": "Urgent referral has already been assigned to the rapid access clinic for review.",
            "completion_state": "routed",
            "priority_score": 62,
        },
    )

    assert evaluation.disposition == "already_prioritized"
    assert evaluation.risk_label == "watch"
    assert evaluation.review_required is False


def test_queue_triage_store_seeds_realistic_cases():
    payload = queue_triage_store.snapshot()

    assert payload["default_case_id"] == "triage_case_001"
    assert len(payload["cases"]) >= 3
    assert payload["workspace"]["workflow_id"] == "high_risk_referral_triage"
    assert payload["workspace"]["risk_tier"] == "urgent"


def test_queue_triage_store_explain_and_review_update_workspace():
    response = queue_triage_store.explain("triage_case_001", "Why was this case flagged?")
    assert "urgent" in response["answer"].lower() or "high-risk" in response["answer"].lower()
    assert response["updated_case"]["audit"][-1]["title"] == "Queue triage explanation requested"

    reviewed = queue_triage_store.review("triage_case_001", "approve", "Fast-track path confirmed.")
    assert reviewed["review"]["status"] == "approve"
    assert reviewed["review"]["comment"] == "Fast-track path confirmed."
    assert reviewed["status"] == "approved"
    assert reviewed["audit"][-1]["title"] == "Queue triage reviewed"
    assert reviewed["summary_cards"][1]["value"]
    assert reviewed["status_steps"][-1]["state"] in {"done", "current", "upcoming"}


def test_queue_triage_presenter_skill_is_compact_and_case_centric():
    skill_text = Path("skills/queue_triage_presenter/SKILL.md").read_text(encoding="utf-8")

    assert "case-centric" in skill_text.lower()
    assert "`Case Signal`" in skill_text
    assert "`Queue Status`" in skill_text
    assert "`Recommended Next Step`" in skill_text
    assert "`Review Status`" in skill_text
    assert "within 7 days" in skill_text.lower()
    assert "same day" in skill_text.lower()
    assert "do not expose tool names" in skill_text.lower()


def test_queue_triage_store_rerun_preserves_review_and_refreshes_workspace():
    queue_triage_store.review("triage_case_002", "acknowledge", "Coordinator accepted reprioritization.")

    rerun = queue_triage_store.rerun("triage_case_002")

    assert rerun["review"]["status"] == "acknowledge"
    assert rerun["review"]["comment"] == "Coordinator accepted reprioritization."
    assert rerun["status"] == "triaged"
    assert rerun["audit"][-1]["title"] == "Queue triage rerun completed"
    assert rerun["summary_cards"][0]["value"] in {"Watch", "Alert", "Urgent"}


def test_queue_triage_store_explain_next_action_and_default_answer_paths():
    next_step = queue_triage_store.explain("triage_case_001", "What should we do next?")
    default = queue_triage_store.explain("triage_case_003", "Give me the snapshot.")

    assert "Recommended next step:" in next_step["answer"]
    assert "Risk tier is" in default["answer"]
