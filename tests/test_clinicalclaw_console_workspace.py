from clinicalclaw.console_workspace import console_snapshot, route_general_query


def test_console_snapshot_includes_multiple_modules():
    payload = console_snapshot()

    assert payload["title"] == "ClinicalClaw Console"
    assert len(payload["workflows"]) >= 6
    assert payload["modules"]["findings"]["title"]
    assert payload["modules"]["queue"]["title"]
    assert payload["modules"]["diagnosis"]["title"]
    assert payload["modules"]["screening"]["title"]
    assert payload["modules"]["neuro"]["title"]
    assert payload["modules"]["safety"]["title"]


def test_route_general_query_can_select_findings_queue_diagnosis_screening_neuro_or_safety():
    findings = route_general_query("Does this critical potassium result need urgent escalation?")
    queue = route_general_query("Should this high-risk referral be expedited in the queue today?")
    diagnosis = route_general_query("Does this report suggest a missed vertebral fracture workup gap?")
    screening = route_general_query("Does this positive FIT still need colonoscopy follow-up?")
    neuro = route_general_query("Review this MRI longitudinal atrophy trend and generate a report.")
    metastasis = route_general_query("Review this longitudinal brain metastasis MRI trend and draft a physician report.")
    safety = route_general_query("Check whether this radiation plan incident should trigger an alert.")

    assert findings["target_module"] == "findings"
    assert "closure_checker" in findings["suggested_steps"]
    assert queue["target_module"] == "queue"
    assert "priority_scorer" in queue["suggested_steps"]
    assert diagnosis["target_module"] == "diagnosis"
    assert "workup_recommender" in diagnosis["suggested_steps"]
    assert screening["target_module"] == "screening"
    assert "gap_checker" in screening["suggested_steps"]
    assert neuro["target_module"] == "neuro"
    assert "brain_met_response_tracker" in neuro["suggested_steps"]
    assert metastasis["target_module"] == "neuro"
    assert metastasis["workflow"]["id"] == "neuro_longitudinal"
    assert "brain_met_response_tracker" in metastasis["suggested_steps"]
    assert safety["target_module"] == "safety"
    assert "risk_tier_engine" in safety["suggested_steps"]
