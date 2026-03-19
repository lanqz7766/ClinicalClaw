import json

from clinicalclaw.workflow_engine import (
    WorkflowFamily,
    build_workflow_engine,
    load_workflow_map,
)
from clinicalclaw.workflow_families.findings_closure import FindingsClosureFamily


def test_workflow_definitions_load_expected_initial_library():
    workflows = load_workflow_map("workflows")

    assert len(workflows) == 10
    assert "critical_lab_escalation" in workflows
    assert workflows["critical_lab_escalation"].family == WorkflowFamily.findings_closure
    assert workflows["high_risk_referral_triage"].family == WorkflowFamily.queue_triage
    assert workflows["unrecognized_af_detection"].family == WorkflowFamily.missed_diagnosis_detection


def test_workflow_engine_groups_workflows_by_family():
    engine = build_workflow_engine("workflows")
    families = {summary.family: summary for summary in engine.list_families()}

    assert WorkflowFamily.findings_closure in families
    assert "critical_lab_escalation" in families[WorkflowFamily.findings_closure].workflow_ids
    assert WorkflowFamily.queue_triage in families
    assert WorkflowFamily.missed_diagnosis_detection in families


def test_workflow_loader_ignores_non_spec_json_payloads_without_ids(tmp_path):
    valid_workflow = {
        "id": "valid_queue_workflow",
        "title": "Valid Queue Workflow",
        "family": "queue_triage",
        "summary": "Valid workflow payload.",
        "problem_statement": "Queue needs triage.",
        "presentation": {"skill": "triage_brief_presenter"},
    }
    ignored_payload = {
        "cases": [{"id": "triage_case_001"}],
        "workspace": {"title": "Queue demo store"},
    }

    (tmp_path / "valid_queue_workflow.json").write_text(json.dumps(valid_workflow), encoding="utf-8")
    (tmp_path / "queue_demo_store.json").write_text(json.dumps(ignored_payload), encoding="utf-8")

    workflows = load_workflow_map(tmp_path)

    assert list(workflows) == ["valid_queue_workflow"]


def test_workflow_loader_skips_incomplete_id_bearing_payloads(tmp_path):
    malformed_payload = {
        "id": "not_really_a_workflow",
        "cases": [{"id": "triage_case_001"}],
    }
    (tmp_path / "bad.json").write_text(json.dumps(malformed_payload), encoding="utf-8")

    assert load_workflow_map(tmp_path) == {}


def test_findings_closure_family_can_evaluate_actionable_case():
    workflow = load_workflow_map("workflows")["critical_lab_escalation"]
    family = FindingsClosureFamily()

    evaluation = family.evaluate(
        workflow,
        {
            "patient_id": "demo-123",
            "lab_text": "Potassium 6.4 mmol/L critical high. Notify clinician immediately.",
            "completion_state": "unknown",
        },
    )

    assert evaluation.workflow_id == "critical_lab_escalation"
    assert evaluation.risk_label == "urgent"
    assert evaluation.disposition == "review_required"
    assert len(evaluation.recommended_actions) >= 2


def test_findings_closure_family_detects_already_closed_case():
    workflow = load_workflow_map("workflows")["positive_fit_followup"]
    family = FindingsClosureFamily()

    evaluation = family.evaluate(
        workflow,
        {
            "lab_text": "Positive FIT result documented.",
            "completion_state": "completed",
        },
    )

    assert evaluation.disposition == "already_addressed"
    assert evaluation.risk_label == "watch"


def test_actionable_radiology_workflow_loads_enhanced_spec_fields():
    workflow = load_workflow_map("workflows")["actionable_radiology_findings"]

    assert workflow.presentation.skill == "findings_brief_presenter"
    assert workflow.presentation.tone == "compact_actionable_findings"
    assert "owner_context" in {item.name for item in workflow.inputs}
    assert "notification_log" in {item.name for item in workflow.inputs}
    assert "radiology_urgent_escalation" in {rule.id for rule in workflow.rule_sets}
    assert "draft_order" in {action.kind.value for action in workflow.actions}
    assert "draft_schedule" in {action.kind.value for action in workflow.actions}
    assert "same day" in workflow.family_config["timeframe_terms"]
    assert "ordering clinician" in workflow.family_config["owner_roles"]


def test_actionable_radiology_findings_detects_broader_followup_language():
    workflow = load_workflow_map("workflows")["actionable_radiology_findings"]
    family = FindingsClosureFamily()

    evaluation = family.evaluate(
        workflow,
        {
            "patient_id": "demo-rad-001",
            "report_text": (
                "Incidental left renal lesion. Dedicated renal mass MRI is recommended for further evaluation. "
                "Short-interval follow-up in 3 months is advised."
            ),
            "completion_state": "unknown",
        },
    )

    assert evaluation.risk_label == "alert"
    assert evaluation.disposition == "ready_for_action"
    assert any("Actionable follow-up language was detected" in line for line in evaluation.rationale)
    assert "Draft diagnostic order suggestion" in evaluation.recommended_actions


def test_actionable_radiology_findings_honors_custom_resolved_states_and_urgent_terms():
    workflow = load_workflow_map("workflows")["actionable_radiology_findings"]
    family = FindingsClosureFamily()

    resolved = family.evaluate(
        workflow,
        {
            "report_text": "Suspicious pulmonary opacity. Follow-up CT is recommended.",
            "completion_state": "patient_notified",
        },
    )
    urgent = family.evaluate(
        workflow,
        {
            "report_text": "Possible cord compression. Same-day MRI and emergent ED evaluation recommended.",
            "completion_state": "unknown",
        },
    )

    assert resolved.disposition == "already_addressed"
    assert resolved.risk_label == "watch"
    assert urgent.disposition == "review_required"
    assert urgent.risk_label == "urgent"
