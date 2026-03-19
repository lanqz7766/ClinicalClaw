from clinicalclaw.missed_diagnosis import missed_diagnosis_store
from clinicalclaw.workflow_engine import WorkflowFamily, load_workflow_map
from clinicalclaw.workflow_families.missed_diagnosis import MissedDiagnosisFamily


def test_missed_diagnosis_workflow_loads_as_missed_diagnosis_family():
    workflows = load_workflow_map("workflows")

    assert "missed_vertebral_fracture_detection" in workflows
    assert workflows["missed_vertebral_fracture_detection"].family == WorkflowFamily.missed_diagnosis_detection
    assert workflows["missed_vertebral_fracture_detection"].presentation.skill == "missed_diagnosis_presenter"


def test_missed_diagnosis_family_detects_unworked_up_vertebral_fracture():
    workflow = load_workflow_map("workflows")["missed_vertebral_fracture_detection"]
    family = MissedDiagnosisFamily()

    evaluation = family.evaluate(
        workflow,
        {
            "patient_id": "demo-spine-1",
            "report_text": (
                "Mild acute vertebral compression fracture at T8 with height loss. Recommend correlation for osteoporosis."
            ),
            "followup_summary": "No follow-up order or osteoporosis workup found.",
            "completion_state": "unknown",
        },
    )

    assert evaluation.workflow_id == "missed_vertebral_fracture_detection"
    assert evaluation.risk_label == "urgent"
    assert evaluation.disposition == "likely_missed_diagnosis"
    assert evaluation.review_required is True
    assert "osteoporosis" in evaluation.gap_recommendation.lower()


def test_missed_diagnosis_family_detects_resolved_case():
    workflow = load_workflow_map("workflows")["missed_vertebral_fracture_detection"]
    family = MissedDiagnosisFamily()

    evaluation = family.evaluate(
        workflow,
        {
            "report_text": "Chronic vertebral fracture deformity at L1. Osteoporosis evaluation has already been scheduled.",
            "followup_summary": "Bone health clinic visit scheduled next week.",
            "completion_state": "scheduled",
        },
    )

    assert evaluation.disposition == "already_addressed"
    assert evaluation.risk_label == "watch"
    assert evaluation.review_required is False


def test_missed_diagnosis_store_seeds_demo_cases_and_review_flow():
    payload = missed_diagnosis_store.snapshot()

    assert payload["default_case_id"] == "md_case_001"
    assert len(payload["cases"]) == 3
    assert payload["workspace"]["workflow_id"] == "missed_vertebral_fracture_detection"
    assert payload["workspace"]["risk_tier"] == "urgent"
    assert payload["workspace"]["mock_email"]["sent"] is True

    rerun = missed_diagnosis_store.rerun("md_case_003")
    assert rerun["risk_tier"] == "alert"
    assert rerun["review"]["status"] == "open"
    assert rerun["audit"][0]["title"] == "Missed diagnosis engine rerun"

    reviewed = missed_diagnosis_store.review("md_case_003", "approve", "Workup underway.")
    assert reviewed["review"]["status"] == "approve"
    assert reviewed["review"]["comment"] == "Workup underway."

    explanation = missed_diagnosis_store.explain("md_case_001", "Why was this escalated?")
    assert "gap" in explanation["answer"].lower()
    assert explanation["workspace"]["id"] == "md_case_001"
