from __future__ import annotations

from typing import Any

from clinicalclaw.demo_workspace import demo_workspace_store
from clinicalclaw.findings_closure import findings_closure_store
from clinicalclaw.missed_diagnosis import missed_diagnosis_store
from clinicalclaw.queue_triage import queue_triage_store
from clinicalclaw.screening_gap import screening_gap_store
from clinicalclaw.safety_monitor import safety_monitor_store


WORKFLOWS = [
    {
        "id": "general_chat",
        "title": "General Clinical Command",
        "module": "home",
        "summary": "Natural-language intake that routes requests into the most relevant ClinicalClaw workflow.",
        "tools": ["workflow_router", "policy_guard", "tool_selector"],
        "tags": ["chat", "routing", "agent-entry"],
        "examples": [
            "Help me decide which workflow I should use.",
            "I have a new clinical task but I'm not sure where it belongs.",
        ],
    },
    {
        "id": "findings_closure",
        "title": "Findings Closure",
        "module": "findings",
        "summary": "Actionable findings follow-up across labs, radiology reports, and other result-closure workflows.",
        "tools": ["finding_parser", "closure_checker", "action_recommender", "review_router"],
        "tags": ["findings", "follow-up", "lab", "report", "closure"],
        "examples": [
            "Does this critical lab need urgent escalation?",
            "Check whether this actionable report finding still needs follow-up.",
        ],
    },
    {
        "id": "queue_triage",
        "title": "Queue Triage",
        "module": "queue",
        "summary": "Reprioritize high-risk referrals and follow-up queues with compact review-first triage logic.",
        "tools": ["queue_reader", "priority_scorer", "review_router", "action_recommender"],
        "tags": ["queue", "referral", "triage", "follow-up"],
        "examples": [
            "Should this referral move to an urgent queue?",
            "Review this post-discharge case and suggest the next triage step.",
        ],
    },
    {
        "id": "missed_diagnosis_detection",
        "title": "Missed Diagnosis Review",
        "module": "diagnosis",
        "summary": "Detect likely diagnosis gaps from reports and chart follow-up signals, then prepare review-first workup guidance.",
        "tools": ["gap_reader", "evidence_bundle", "workup_recommender", "review_router"],
        "tags": ["diagnosis-gap", "fracture", "chart-review", "follow-up"],
        "examples": [
            "Does this report suggest a missed vertebral fracture workup gap?",
            "Review this case for a likely missed diagnosis and summarize the next step.",
        ],
    },
    {
        "id": "screening_gap_closure",
        "title": "Screening Gap Closure",
        "module": "screening",
        "summary": "Detect overdue or unresolved screening follow-up and prepare a concise review-first closure plan.",
        "tools": ["screening_reader", "gap_checker", "followup_recommender", "review_router"],
        "tags": ["screening", "gap", "follow-up", "population-health"],
        "examples": [
            "Does this positive FIT still need diagnostic follow-up?",
            "Review this screening result and tell me whether the gap is still open.",
        ],
    },
    {
        "id": "neuro_longitudinal",
        "title": "Neuro Longitudinal Review",
        "module": "neuro",
        "summary": "Longitudinal MRI review for hippocampal atrophy trend analysis, report generation, and review.",
        "tools": ["ehr_timeline_loader", "mri_series_selector", "volume_trend_analyzer", "report_generator"],
        "tags": ["brain", "mri", "atrophy", "report"],
        "examples": [
            "Compare this longitudinal MRI trend and draft a physician report.",
            "Is there accelerated hippocampal atrophy in this case?",
        ],
    },
    {
        "id": "radiation_safety_monitor",
        "title": "Radiation Safety Monitor",
        "module": "safety",
        "summary": "Case-based failure pattern matching with watch/alert/urgent triage and mitigation playbooks.",
        "tools": ["case_parser", "failure_pattern_matcher", "risk_tier_engine", "mock_email_router"],
        "tags": ["qa", "radiation-oncology", "incident", "alert"],
        "examples": [
            "Does this radiation incident require an urgent alert?",
            "Match this QA case against historical failure patterns.",
        ],
    },
]


ROUTING_KEYWORDS = {
    "findings": {
        "critical",
        "lab",
        "follow-up",
        "follow up",
        "result",
        "finding",
        "abnormal pap",
        "nodule",
        "potassium",
    },
    "queue": {
        "referral",
        "queue",
        "triage",
        "high-risk",
        "high risk",
        "post-discharge",
        "post discharge",
        "expedite",
        "same-day",
        "same day",
        "follow-up window",
        "follow up window",
        "outreach",
    },
    "diagnosis": {
        "missed diagnosis",
        "missed fracture",
        "vertebral",
        "compression fracture",
        "osteoporosis",
        "gap",
        "unrecognized",
        "undiagnosed",
        "atrial fibrillation",
        "hypertension",
    },
    "screening": {
        "screening",
        "positive fit",
        "fit",
        "colonoscopy",
        "cervical",
        "pap",
        "hpv",
        "lung cancer screening",
        "diabetic eye exam",
        "overdue screening",
        "care gap",
    },
    "neuro": {"mri", "brain", "hippocampus", "atrophy", "neuro", "longitudinal", "report", "volume", "trend"},
    "safety": {
        "incident",
        "safety",
        "radiation",
        "radiotherapy",
        "timeout",
        "error",
        "alert",
        "adaptive",
        "plan",
        "qa",
        "physics",
        "dosimetry",
        "beam",
    },
}


def console_snapshot() -> dict[str, Any]:
    neuro = demo_workspace_store.snapshot()
    safety = safety_monitor_store.snapshot()
    findings = findings_closure_store.snapshot()
    queue = queue_triage_store.snapshot()
    diagnosis = missed_diagnosis_store.snapshot()
    screening = screening_gap_store.snapshot()
    return {
        "title": "ClinicalClaw Console",
        "tagline": "General clinical command center with workflow-specific modules.",
        "quick_prompts": [
            "Review this MRI trend and draft a physician summary.",
            "Should this referral move into an urgent queue today?",
            "Does this positive FIT still need colonoscopy follow-up?",
            "Check whether this radiotherapy case resembles a known failure pattern.",
            "Route my request to the right workflow and show the next actions.",
        ],
        "workflows": WORKFLOWS,
        "highlights": [
            {
                "label": "Available modules",
                "value": f"{len([item for item in WORKFLOWS if item['module'] != 'home'])} workflow workspaces",
            },
            {
                "label": "Active safety queue",
                "value": f"{len(safety['cases'])} incoming cases",
            },
            {
                "label": "Open findings queue",
                "value": f"{len(findings['cases'])} actionable cases",
            },
            {
                "label": "Queue triage lane",
                "value": f"{len(queue['cases'])} triage cases",
            },
            {
                "label": "Diagnosis gap review",
                "value": f"{len(diagnosis['cases'])} review cases",
            },
            {
                "label": "Screening gap queue",
                "value": f"{len(screening['cases'])} screening cases",
            },
            {
                "label": "Neuro report state",
                "value": neuro["workspace"]["review"]["status"].replace("_", " ").title(),
            },
        ],
        "modules": {
            "neuro": {
                "title": neuro["workspace"]["title"],
                "summary": neuro["workspace"]["patient"]["summary"],
                "risk": neuro["workspace"]["analysis"]["risk_level"],
                "default_case_id": neuro["default_case_id"],
            },
            "findings": {
                "title": findings["workspace"]["title"],
                "summary": findings["workspace"]["risk_reason"],
                "risk": findings["workspace"]["risk_label"],
                "default_case_id": findings["default_case_id"],
            },
            "queue": {
                "title": queue["workspace"]["title"],
                "summary": queue["workspace"]["risk_reason"],
                "risk": queue["workspace"]["risk_label"],
                "default_case_id": queue["default_case_id"],
            },
            "diagnosis": {
                "title": diagnosis["workspace"]["title"],
                "summary": diagnosis["workspace"]["risk_reason"],
                "risk": diagnosis["workspace"]["risk_label"],
                "default_case_id": diagnosis["default_case_id"],
            },
            "screening": {
                "title": screening["workspace"]["title"],
                "summary": screening["workspace"]["risk_reason"],
                "risk": screening["workspace"]["risk_label"],
                "default_case_id": screening["default_case_id"],
            },
            "safety": {
                "title": safety["workspace"]["title"],
                "summary": safety["workspace"]["risk_reason"],
                "risk": safety["workspace"]["risk_label"],
                "default_case_id": safety["default_case_id"],
            },
        },
    }


def rank_workflows(message: str) -> list[dict[str, Any]]:
    lowered = message.lower()
    findings_score = sum(1 for token in ROUTING_KEYWORDS["findings"] if token in lowered)
    queue_score = sum(1 for token in ROUTING_KEYWORDS["queue"] if token in lowered)
    diagnosis_score = sum(1 for token in ROUTING_KEYWORDS["diagnosis"] if token in lowered)
    screening_score = sum(1 for token in ROUTING_KEYWORDS["screening"] if token in lowered)
    neuro_score = sum(1 for token in ROUTING_KEYWORDS["neuro"] if token in lowered)
    safety_score = sum(1 for token in ROUTING_KEYWORDS["safety"] if token in lowered)
    ranked = [
        {
            "module": "findings",
            "workflow": next(item for item in WORKFLOWS if item["module"] == "findings"),
            "score": findings_score,
        },
        {
            "module": "queue",
            "workflow": next(item for item in WORKFLOWS if item["module"] == "queue"),
            "score": queue_score,
        },
        {
            "module": "diagnosis",
            "workflow": next(item for item in WORKFLOWS if item["module"] == "diagnosis"),
            "score": diagnosis_score,
        },
        {
            "module": "screening",
            "workflow": next(item for item in WORKFLOWS if item["module"] == "screening"),
            "score": screening_score,
        },
        {
            "module": "neuro",
            "workflow": next(item for item in WORKFLOWS if item["module"] == "neuro"),
            "score": neuro_score,
        },
        {
            "module": "safety",
            "workflow": next(item for item in WORKFLOWS if item["module"] == "safety"),
            "score": safety_score,
        },
    ]
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked


def route_general_query(message: str) -> dict[str, Any]:
    ranked = rank_workflows(message)
    best = ranked[0]
    alternatives = [
        {"module": item["module"], "title": item["workflow"]["title"], "score": item["score"]}
        for item in ranked
        if item["score"] > 0
    ]
    findings_score = next(item["score"] for item in ranked if item["module"] == "findings")
    queue_score = next(item["score"] for item in ranked if item["module"] == "queue")
    diagnosis_score = next(item["score"] for item in ranked if item["module"] == "diagnosis")
    screening_score = next(item["score"] for item in ranked if item["module"] == "screening")
    neuro_score = next(item["score"] for item in ranked if item["module"] == "neuro")
    safety_score = next(item["score"] for item in ranked if item["module"] == "safety")

    if screening_score >= findings_score and screening_score >= queue_score and screening_score >= diagnosis_score and screening_score >= neuro_score and screening_score >= safety_score and screening_score > 0:
        workflow = best["workflow"]
        return {
            "assistant": {
                "content": (
                    "I routed this request to Screening Gap Closure. The next step is to verify whether the screening follow-up "
                    "is still open, summarize the missing step, and prepare a review-first closure recommendation."
                )
            },
            "workflow": workflow,
            "target_module": "screening",
            "target_view": "screening",
            "suggested_steps": workflow["tools"],
            "alternatives": alternatives,
            "confidence": min(0.55 + screening_score * 0.12, 0.9),
        }

    if findings_score >= queue_score and findings_score >= diagnosis_score and findings_score >= neuro_score and findings_score >= safety_score and findings_score > 0:
        workflow = best["workflow"]
        return {
            "assistant": {
                "content": (
                    "I routed this request to Findings Closure. The next step is to inspect the incoming finding, "
                    "check whether follow-up is already closed, and prepare the safest next action for review."
                )
            },
            "workflow": workflow,
            "target_module": "findings",
            "target_view": "findings",
            "suggested_steps": workflow["tools"],
            "alternatives": alternatives,
            "confidence": min(0.55 + findings_score * 0.12, 0.9),
        }

    if queue_score >= diagnosis_score and queue_score >= screening_score and queue_score >= neuro_score and queue_score >= safety_score and queue_score > 0:
        workflow = best["workflow"]
        return {
            "assistant": {
                "content": (
                    "I routed this request to Queue Triage. The next step is to inspect the queue item, "
                    "score urgency, and prepare the safest queue move for review."
                )
            },
            "workflow": workflow,
            "target_module": "queue",
            "target_view": "queue",
            "suggested_steps": workflow["tools"],
            "alternatives": alternatives,
            "confidence": min(0.55 + queue_score * 0.12, 0.9),
        }

    if diagnosis_score >= screening_score and diagnosis_score >= neuro_score and diagnosis_score >= safety_score and diagnosis_score > 0:
        workflow = best["workflow"]
        return {
            "assistant": {
                "content": (
                    "I routed this request to Missed Diagnosis Review. The next step is to inspect the signal, "
                    "check whether follow-up is already documented, and prepare a review-first workup recommendation."
                )
            },
            "workflow": workflow,
            "target_module": "diagnosis",
            "target_view": "diagnosis",
            "suggested_steps": workflow["tools"],
            "alternatives": alternatives,
            "confidence": min(0.55 + diagnosis_score * 0.12, 0.9),
        }

    if neuro_score > safety_score and neuro_score > 0:
        workflow = best["workflow"]
        return {
            "assistant": {
                "content": (
                    "I routed this request to the Neuro Longitudinal Review module. The best next step is to "
                    "load the longitudinal MRI case, run the volume trend analyzer, and refresh the physician-facing report."
                )
            },
            "workflow": workflow,
            "target_module": "neuro",
            "target_view": "neuro",
            "suggested_steps": workflow["tools"],
            "alternatives": alternatives,
            "confidence": min(0.55 + neuro_score * 0.12, 0.9),
        }

    if safety_score >= neuro_score and safety_score > 0:
        workflow = best["workflow"]
        return {
            "assistant": {
                "content": (
                    "I routed this request to the Radiation Safety Monitor. The next step is to parse the case "
                    "text, compare it against the local failure library, assign a watch/alert/urgent tier, and prepare mitigation guidance."
                )
            },
            "workflow": workflow,
            "target_module": "safety",
            "target_view": "safety",
            "suggested_steps": workflow["tools"],
            "alternatives": alternatives,
            "confidence": min(0.55 + safety_score * 0.12, 0.9),
        }

    workflow = next(item for item in WORKFLOWS if item["module"] == "home")
    return {
        "assistant": {
            "content": (
                "I can route requests into workflow-specific modules. Try a findings question about critical results or "
                "follow-up closure, a queue question about referrals or post-discharge follow-up, a diagnosis-gap question "
                "about missed fractures or unrecognized conditions, a screening question about open preventive or diagnostic "
                "follow-up, a neuro question about longitudinal MRI change, or a safety question about incident patterns."
            )
        },
        "workflow": workflow,
        "target_module": "home",
        "target_view": "home",
        "suggested_steps": workflow["tools"],
        "alternatives": alternatives,
        "confidence": 0.0,
    }
