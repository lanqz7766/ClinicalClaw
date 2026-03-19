from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from math import ceil
from threading import Lock
from typing import Any

from clinicalclaw.workflow_engine import load_workflow_map
from clinicalclaw.workflow_families.findings_closure import FindingsClosureFamily


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _title_case(value: str) -> str:
    return value.replace("_", " ").title()


RISK_COPY = {
    "watch": {
        "label": "Watch",
        "reason": "The finding still needs review, but immediate escalation is not required.",
    },
    "alert": {
        "label": "Alert",
        "reason": "The finding appears actionable and still looks open in the current workflow.",
    },
    "urgent": {
        "label": "Urgent",
        "reason": "The finding appears actionable and time-sensitive. Immediate review is recommended.",
    },
}


FINDINGS_CASES = [
    {
        "id": "finding_case_001",
        "workflow_id": "critical_lab_escalation",
        "title": "Critical potassium result needs rapid escalation",
        "submitted_by": "Chemistry analyzer feed",
        "received_at": "2026-03-19T10:18:00+00:00",
        "status": "new",
        "owner": "Inpatient medicine covering clinician",
        "queue": "Critical results",
        "due_at": "2026-03-19T10:45:00+00:00",
        "patient_label": "Demo Patient A",
        "service_line": "Hospital medicine",
        "source_type": "lab",
        "clinical_context": "CKD stage 3, lisinopril and spironolactone on active med list.",
        "completion_state": "unknown",
        "trigger_text": "Potassium 6.4 mmol/L critical high. Please notify responsible clinician immediately.",
        "focus_metric": {
            "label": "Potassium",
            "value": "6.4",
            "unit": "mmol/L",
            "delta": "+0.7 from prior",
            "tone": "urgent",
        },
        "trend_points": [
            {"label": "Feb 18", "value": 4.9},
            {"label": "Mar 1", "value": 5.2},
            {"label": "Mar 12", "value": 5.7},
            {"label": "Mar 19", "value": 6.4},
        ],
        "evidence_grid": [
            {"label": "Result channel", "value": "Chemistry analyzer"},
            {"label": "Current meds", "value": "Lisinopril, spironolactone"},
            {"label": "Renal risk", "value": "CKD stage 3"},
            {"label": "Current closure", "value": "No acknowledgement recorded"},
        ],
    },
    {
        "id": "finding_case_002",
        "workflow_id": "positive_fit_followup",
        "title": "Positive FIT still lacks colonoscopy follow-up",
        "submitted_by": "Population health closure queue",
        "received_at": "2026-03-19T08:10:00+00:00",
        "status": "new",
        "owner": "Primary care screening navigator",
        "queue": "Cancer screening closure",
        "due_at": "2026-03-20T17:00:00+00:00",
        "patient_label": "Demo Patient B",
        "service_line": "Primary care",
        "source_type": "lab",
        "clinical_context": "Average-risk colorectal screening pathway.",
        "completion_state": "unknown",
        "trigger_text": "Positive FIT result documented. No colonoscopy order or completion was found in the closure queue.",
        "focus_metric": {
            "label": "FIT Result",
            "value": "Positive",
            "unit": "",
            "delta": "14 days unresolved",
            "tone": "alert",
        },
        "trend_points": [
            {"label": "2022", "value": 0},
            {"label": "2023", "value": 0},
            {"label": "2024", "value": 1},
        ],
        "evidence_grid": [
            {"label": "Screening path", "value": "Average-risk CRC screening"},
            {"label": "Order status", "value": "No colonoscopy order found"},
            {"label": "Follow-up", "value": "No completion documented"},
            {"label": "Current closure", "value": "Open"},
        ],
    },
    {
        "id": "finding_case_003",
        "workflow_id": "suspicious_lung_nodule_followup",
        "title": "Suspicious lung nodule already moved into surveillance",
        "submitted_by": "Radiology follow-up registry",
        "received_at": "2026-03-18T15:22:00+00:00",
        "status": "new",
        "owner": "Pulmonary nodule clinic",
        "queue": "Nodule surveillance",
        "due_at": "2026-04-01T12:00:00+00:00",
        "patient_label": "Demo Patient C",
        "service_line": "Pulmonology",
        "source_type": "report",
        "clinical_context": "Incidental 8 mm right upper lobe nodule on routine chest CT.",
        "completion_state": "scheduled",
        "trigger_text": "Suspicious pulmonary nodule. Follow-up CT in 6 months is recommended and has been scheduled.",
        "focus_metric": {
            "label": "Nodule",
            "value": "8",
            "unit": "mm",
            "delta": "Follow-up CT scheduled",
            "tone": "watch",
        },
        "trend_points": [
            {"label": "Prior CT", "value": 6},
            {"label": "Current CT", "value": 8},
        ],
        "evidence_grid": [
            {"label": "Location", "value": "Right upper lobe"},
            {"label": "Follow-up interval", "value": "6 months"},
            {"label": "Surveillance status", "value": "Scheduled"},
            {"label": "Current closure", "value": "Already addressed"},
        ],
    },
]


class FindingsClosureStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._workflows = load_workflow_map("workflows")
        self._family = FindingsClosureFamily()
        self._cases = self._seed_cases()

    def _build_summary_cards(self, case: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {"label": "Risk", "value": case["risk_label"], "tone": case["risk_tier"]},
            {"label": "Closure", "value": _title_case(case["disposition"]), "tone": "neutral"},
            {"label": "Owner", "value": case["owner"], "tone": "neutral"},
            {"label": "Due", "value": case["due_at"], "tone": "neutral"},
        ]

    def _build_steps(self, case: dict[str, Any]) -> list[dict[str, str]]:
        disposition = case["disposition"]
        closure_done = disposition == "already_addressed"
        review_done = case["review"]["status"] in {"approve", "acknowledged"}
        return [
            {"title": "Finding detected", "state": "done"},
            {"title": "Closure checked", "state": "done"},
            {"title": "Action drafted", "state": "done" if disposition != "already_addressed" else "current"},
            {"title": "Reviewer sign-off", "state": "done" if review_done else ("current" if not closure_done else "upcoming")},
        ]

    def _build_timeline(self, case: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {
                "title": "Case entered findings monitor",
                "detail": f"{case['submitted_by']} opened the case.",
                "created_at": case["received_at"],
            },
            {
                "title": "Closure engine scored the case",
                "detail": f"Assigned {case['risk_label']} with disposition {case['disposition'].replace('_', ' ')}.",
                "created_at": case["received_at"],
            },
            {
                "title": "Owner follow-up pending",
                "detail": f"Current owner: {case['owner']}. Queue: {case['queue']}.",
                "created_at": case["due_at"],
            },
        ]

    def _build_mock_email(self, case: dict[str, Any]) -> dict[str, Any]:
        return {
            "to": "results-owner@clinicalclaw.demo",
            "subject": f"[{case['risk_label']}] {case['workflow_title']}",
            "body": (
                f"{case['title']} was evaluated as {case['risk_label']}. "
                f"Recommended next actions: {', '.join(case['recommended_actions']) or 'manual review'}."
            ),
            "sent": case["risk_tier"] in {"alert", "urgent"},
        }

    def _hydrate_case(self, seed: dict[str, Any]) -> dict[str, Any]:
        workflow = self._workflows[seed["workflow_id"]]
        evaluation = self._family.evaluate(
            workflow,
            {
                "patient_id": seed.get("patient_label"),
                "trigger_text": seed["trigger_text"],
                "completion_state": seed.get("completion_state", "unknown"),
            },
        )
        risk_copy = RISK_COPY[evaluation.risk_label]
        hydrated = {
            **seed,
            "workflow_title": workflow.title,
            "workflow_summary": workflow.summary,
            "family": workflow.family.value,
            "risk_tier": evaluation.risk_label,
            "risk_label": risk_copy["label"],
            "risk_reason": risk_copy["reason"],
            "disposition": evaluation.disposition,
            "rationale": evaluation.rationale,
            "recommended_actions": evaluation.recommended_actions,
            "matched_terms": self._family.normalize_case(
                workflow,
                {
                    "patient_id": seed.get("patient_label"),
                    "trigger_text": seed["trigger_text"],
                    "completion_state": seed.get("completion_state", "unknown"),
                },
            ).matched_terms,
            "review": {
                "status": "open",
                "comment": "Awaiting clinician or operational review.",
                "updated_at": _now_iso(),
            },
            "audit": [
                {
                    "id": f"audit_seed_{seed['id']}",
                    "title": "Findings closure evaluation completed",
                    "detail": evaluation.rationale[0],
                    "severity": "warning" if evaluation.risk_label in {"alert", "urgent"} else "info",
                    "created_at": _now_iso(),
                }
            ],
        }
        hydrated["summary_cards"] = self._build_summary_cards(hydrated)
        hydrated["status_steps"] = self._build_steps(hydrated)
        hydrated["timeline"] = self._build_timeline(hydrated)
        hydrated["mock_email"] = self._build_mock_email(hydrated)
        return hydrated

    def _seed_cases(self) -> dict[str, dict[str, Any]]:
        return {seed["id"]: self._hydrate_case(seed) for seed in FINDINGS_CASES}

    def _queue_summary(self) -> dict[str, int]:
        summary = {"watch": 0, "alert": 0, "urgent": 0}
        for case in self._cases.values():
            summary[case["risk_tier"]] += 1
        return summary

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            default_case_id = "finding_case_001"
            return {
                "cases": [
                    {
                        "id": case["id"],
                        "title": case["title"],
                        "workflow_title": case["workflow_title"],
                        "risk_tier": case["risk_tier"],
                        "risk_label": case["risk_label"],
                        "owner": case["owner"],
                        "queue": case["queue"],
                        "due_at": case["due_at"],
                    }
                    for case in self._cases.values()
                ],
                "queue_summary": self._queue_summary(),
                "default_case_id": default_case_id,
                "workspace": deepcopy(self._cases[default_case_id]),
            }

    def get_case(self, case_id: str) -> dict[str, Any]:
        with self._lock:
            case = self._cases.get(case_id)
            if not case:
                raise KeyError(case_id)
            return deepcopy(case)

    def rerun(self, case_id: str) -> dict[str, Any]:
        with self._lock:
            case = self._cases[case_id]
            refreshed = self._hydrate_case(case)
            refreshed["review"] = case["review"]
            refreshed["audit"] = [
                {
                    "id": f"audit_rerun_{case_id}_{ceil(datetime.now(UTC).timestamp())}",
                    "title": "Findings engine rerun",
                    "detail": f"Refreshed case and confirmed {refreshed['risk_label']} status.",
                    "severity": "success" if refreshed["risk_tier"] in {"alert", "urgent"} else "info",
                    "created_at": _now_iso(),
                },
                *case["audit"],
            ]
            self._cases[case_id] = refreshed
            return deepcopy(refreshed)

    def review(self, case_id: str, action: str, comment: str | None = None) -> dict[str, Any]:
        with self._lock:
            case = self._cases[case_id]
            normalized = action.strip().lower()
            case["review"]["status"] = normalized
            case["review"]["comment"] = comment or case["review"]["comment"]
            case["review"]["updated_at"] = _now_iso()
            case["audit"].insert(
                0,
                {
                    "id": f"audit_review_{case_id}_{ceil(datetime.now(UTC).timestamp())}",
                    "title": f"Reviewer action: {normalized}",
                    "detail": comment or f"Reviewer changed findings case state to {normalized}.",
                    "severity": "warning" if normalized in {"reject", "urgent"} else "success" if normalized == "approve" else "info",
                    "created_at": _now_iso(),
                },
            )
            case["status_steps"] = self._build_steps(case)
            return deepcopy(case)

    def explain(self, case_id: str, question: str) -> dict[str, Any]:
        with self._lock:
            case = self._cases[case_id]
            lowered = question.lower()
            if "why" in lowered or "flag" in lowered:
                answer = case["rationale"][0]
            elif "email" in lowered or "alert" in lowered:
                answer = (
                    f"This case is {case['risk_label']}. The owner notification is "
                    f"{'ready and marked sent' if case['mock_email']['sent'] else 'drafted for review'}."
                )
            else:
                answer = (
                    f"Recommended next actions: {', '.join(case['recommended_actions'])}. "
                    f"Current disposition: {case['disposition'].replace('_', ' ')}."
                )
            case["audit"].insert(
                0,
                {
                    "id": f"audit_explain_{case_id}_{ceil(datetime.now(UTC).timestamp())}",
                    "title": "Findings explainer used",
                    "detail": answer,
                    "severity": "info",
                    "created_at": _now_iso(),
                },
            )
            return {"answer": answer, "workspace": deepcopy(case)}


findings_closure_store = FindingsClosureStore()
