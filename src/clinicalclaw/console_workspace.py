from __future__ import annotations

from typing import Any

from clinicalclaw.demo_workspace import demo_workspace_store
from clinicalclaw.safety_monitor import safety_monitor_store


WORKFLOWS = [
    {
        "id": "general_chat",
        "title": "General Clinical Command",
        "module": "home",
        "status": "ready",
        "summary": "Natural-language intake that routes requests into the most relevant ClinicalClaw workflow.",
        "tools": ["workflow_router", "policy_guard", "tool_selector"],
        "tags": ["chat", "routing", "agent-entry"],
        "examples": [
            "Help me decide which workflow I should use.",
            "I have a new clinical task but I'm not sure where it belongs.",
        ],
    },
    {
        "id": "neuro_longitudinal",
        "title": "Neuro Longitudinal Review",
        "module": "neuro",
        "status": "prototype-ready",
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
        "status": "prototype-ready",
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
    return {
        "title": "ClinicalClaw Console",
        "tagline": "General clinical command center with workflow-specific modules.",
        "quick_prompts": [
            "Review this MRI trend and draft a physician summary.",
            "Check whether this radiotherapy case resembles a known failure pattern.",
            "Route my request to the right workflow and show the next actions.",
        ],
        "workflows": WORKFLOWS,
        "highlights": [
            {
                "label": "Available modules",
                "value": "2 scenario workspaces",
            },
            {
                "label": "Active safety queue",
                "value": f"{len(safety['cases'])} incoming cases",
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
    neuro_score = sum(1 for token in ROUTING_KEYWORDS["neuro"] if token in lowered)
    safety_score = sum(1 for token in ROUTING_KEYWORDS["safety"] if token in lowered)
    ranked = [
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
    neuro_score = next(item["score"] for item in ranked if item["module"] == "neuro")
    safety_score = next(item["score"] for item in ranked if item["module"] == "safety")

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
                "I can route requests into either workflow-specific module. Try a neuro question about longitudinal MRI "
                "change, or a safety question about incident patterns, alerting, or mitigation."
            )
        },
        "workflow": workflow,
        "target_module": "home",
        "target_view": "home",
        "suggested_steps": workflow["tools"],
        "alternatives": alternatives,
        "confidence": 0.0,
    }
