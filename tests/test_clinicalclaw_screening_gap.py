from clinicalclaw.screening_gap import load_screening_gap_workflow, screening_gap_store
from clinicalclaw.workflow_engine import WorkflowFamily
from clinicalclaw.workflow_families.screening_gap import ScreeningGapFamily


def test_screening_gap_workflow_loads_from_local_spec():
    workflow = load_screening_gap_workflow()

    assert workflow.id == "screening_gap_positive_fit_followup"
    assert workflow.family == WorkflowFamily.screening_gap_closure


def test_screening_gap_family_detects_unclosed_positive_fit():
    workflow = load_screening_gap_workflow()
    family = ScreeningGapFamily()

    evaluation = family.evaluate(
        workflow,
        {
            "patient_id": "demo-screen-1",
            "screening_text": "Positive FIT result documented. Colonoscopy is overdue and no order or completion was found.",
            "followup_summary": "Overdue follow-up has not been placed.",
            "completion_state": "unknown",
        },
    )

    assert evaluation.workflow_id == "screening_gap_positive_fit_followup"
    assert evaluation.risk_label == "urgent"
    assert evaluation.disposition == "gap_likely"
    assert evaluation.review_required is True
    assert "follow-up" in evaluation.gap_recommendation.lower()


def test_screening_gap_family_detects_scheduled_followup():
    workflow = load_screening_gap_workflow()
    family = ScreeningGapFamily()

    evaluation = family.evaluate(
        workflow,
        {
            "screening_text": "Positive FIT result documented. Colonoscopy is scheduled next week.",
            "followup_summary": "Diagnostic colonoscopy booking confirmed.",
            "completion_state": "scheduled",
        },
    )

    assert evaluation.disposition == "already_addressed"
    assert evaluation.risk_label == "watch"
    assert evaluation.review_required is False


def test_screening_gap_store_exposes_demo_cases_and_review_flow():
    payload = screening_gap_store.snapshot()

    assert payload["default_case_id"] == "sg_case_001"
    assert len(payload["cases"]) == 3
    assert payload["workspace"]["workflow_id"] == "screening_gap_positive_fit_followup"
    assert payload["workspace"]["risk_tier"] == "urgent"

    rerun = screening_gap_store.rerun("sg_case_003")
    assert rerun["risk_tier"] == "alert"
    assert rerun["audit"][0]["title"] == "Screening gap engine rerun"

    reviewed = screening_gap_store.review("sg_case_003", "approve", "Follow-up outreach underway.")
    assert reviewed["review"]["status"] == "approve"
    assert reviewed["review"]["comment"] == "Follow-up outreach underway."

    explanation = screening_gap_store.explain("sg_case_001", "Why was this flagged?")
    assert "gap" in explanation["answer"].lower()
    assert explanation["workspace"]["id"] == "sg_case_001"
