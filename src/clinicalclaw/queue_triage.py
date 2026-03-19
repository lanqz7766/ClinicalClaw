from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from threading import Lock
from pathlib import Path
from typing import Any

from clinicalclaw.workflow_engine import load_workflow_map
from clinicalclaw.workflow_families.queue_triage import QueueTriageFamily


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _title_case(value: str) -> str:
    return value.replace("_", " ").title()


RISK_COPY = {
    "watch": {
        "label": "Watch",
        "reason": "The queue item is open, but it does not yet need urgent reprioritization.",
    },
    "alert": {
        "label": "Alert",
        "reason": "The queue item looks elevated and should move ahead of routine cases.",
    },
    "urgent": {
        "label": "Urgent",
        "reason": "The queue item needs immediate attention and a rapid human review.",
    },
}


DEFAULT_DEMO_STORE = Path(__file__).resolve().parents[2] / "workflows" / "high_risk_referral_triage_demo_store.json"


def _default_demo_cases() -> list[dict[str, Any]]:
    return [
        {
            "id": "triage_case_001",
            "workflow_id": "high_risk_referral_triage",
            "title": "Neurology referral with progressive weakness and speech changes",
            "submitted_by": "Referral intake desk",
            "received_at": "2026-03-18T09:45:00+00:00",
            "status": "new",
            "owner": "Neurology triage nurse",
            "queue": "New referrals",
            "due_at": "2026-03-18T11:00:00+00:00",
            "patient_label": "Demo Referral A",
            "service_line": "Neurology",
            "source_type": "fax",
            "clinical_context": "Referral contains same-day escalation language and neurologic change.",
            "completion_state": "unknown",
            "trigger_text": "Patient has progressive left-sided weakness, new speech changes, and worsening gait over 48 hours. Referring clinician requests same-day review.",
            "focus_metric": {
                "label": "Priority score",
                "value": 94,
                "unit": "/100",
                "delta": "+28 at triage",
                "tone": "urgent",
            },
            "trend_points": [
                {"label": "Intake", "value": 66},
                {"label": "Nurse screen", "value": 78},
                {"label": "Current", "value": 94},
            ],
            "evidence_grid": [
                {"label": "Queue lane", "value": "Routine referral intake"},
                {"label": "Escalation cues", "value": "Weakness, speech changes, worsening gait"},
                {"label": "Target action", "value": "Fast-track triage"},
                {"label": "Current closure", "value": "Open"},
            ],
        },
        {
            "id": "triage_case_002",
            "workflow_id": "high_risk_referral_triage",
            "title": "Pulmonology referral with hemoptysis and weight loss",
            "submitted_by": "Referral intake desk",
            "received_at": "2026-03-18T10:10:00+00:00",
            "status": "new",
            "owner": "Pulmonary access coordinator",
            "queue": "Priority consults",
            "due_at": "2026-03-18T14:00:00+00:00",
            "patient_label": "Demo Referral B",
            "service_line": "Pulmonology",
            "source_type": "fax",
            "clinical_context": "Referral contains multiple escalation markers and an expedite request.",
            "completion_state": "unknown",
            "trigger_text": "Intermittent hemoptysis, 10 lb unintentional weight loss, and shortness of breath over two weeks. Request to expedite visit.",
            "focus_metric": {
                "label": "Priority score",
                "value": 86,
                "unit": "/100",
                "delta": "+21 at triage",
                "tone": "alert",
            },
            "trend_points": [
                {"label": "Intake", "value": 54},
                {"label": "Nurse screen", "value": 70},
                {"label": "Current", "value": 86},
            ],
            "evidence_grid": [
                {"label": "Queue lane", "value": "Routine referral intake"},
                {"label": "Escalation cues", "value": "Hemoptysis, weight loss, shortness of breath"},
                {"label": "Target action", "value": "Advance queue priority"},
                {"label": "Current closure", "value": "Open"},
            ],
        },
        {
            "id": "triage_case_003",
            "workflow_id": "high_risk_referral_triage",
            "title": "Cardiology referral already routed to rapid access clinic",
            "submitted_by": "Outpatient referral pool",
            "received_at": "2026-03-18T16:10:00+00:00",
            "status": "new",
            "owner": "Cardiology scheduling lead",
            "queue": "Rapid access clinic",
            "due_at": "2026-03-21T09:00:00+00:00",
            "patient_label": "Demo Referral C",
            "service_line": "Cardiology",
            "source_type": "portal",
            "clinical_context": "Referral has already been scheduled into a fast-track path.",
            "completion_state": "routed",
            "trigger_text": "Urgent referral has already been assigned to the rapid access clinic for review.",
            "focus_metric": {
                "label": "Priority score",
                "value": 62,
                "unit": "/100",
                "delta": "Queue already routed",
                "tone": "watch",
            },
            "trend_points": [
                {"label": "Intake", "value": 54},
                {"label": "Triage", "value": 62},
            ],
            "evidence_grid": [
                {"label": "Queue lane", "value": "Rapid access clinic"},
                {"label": "Escalation cues", "value": "Urgent referral language"},
                {"label": "Target action", "value": "Already routed"},
                {"label": "Current closure", "value": "Routed"},
            ],
        },
    ]


def _load_demo_cases() -> list[dict[str, Any]]:
    if DEFAULT_DEMO_STORE.exists():
        payload = json.loads(DEFAULT_DEMO_STORE.read_text(encoding="utf-8"))
        cases = payload.get("cases")
        if isinstance(cases, list) and cases:
            return cases
    return _default_demo_cases()


class QueueTriageStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._workflows = load_workflow_map("workflows")
        self._family = QueueTriageFamily()
        self._cases = self._seed_cases()

    def _build_summary_cards(self, case: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {"label": "Risk", "value": case["risk_label"], "tone": case["risk_tier"]},
            {"label": "Queue", "value": case["queue"], "tone": "neutral"},
            {"label": "Owner", "value": case["owner"], "tone": "neutral"},
            {"label": "Due", "value": case["due_at"], "tone": "neutral"},
        ]

    def _build_steps(self, case: dict[str, Any]) -> list[dict[str, str]]:
        disposition = case["disposition"]
        routed = disposition == "already_prioritized"
        review_done = case["review"]["status"] in {"approve", "acknowledged"}
        return [
            {"title": "Queue item received", "state": "done"},
            {"title": "Priority scored", "state": "done"},
            {"title": "Queue move drafted", "state": "done" if disposition != "already_prioritized" else "current"},
            {"title": "Reviewer sign-off", "state": "done" if review_done else ("current" if not routed else "upcoming")},
        ]

    def _build_timeline(self, case: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {
                "title": "Case entered queue triage",
                "detail": f"{case['submitted_by']} opened the queue item.",
                "created_at": case["received_at"],
            },
            {
                "title": "Priority score calculated",
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
            "to": "queue-owner@clinicalclaw.demo",
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
                "priority_score": seed["focus_metric"]["value"],
                "queue_context": {
                    "patient_id": seed.get("patient_label"),
                    "queue_state": seed.get("completion_state", "unknown"),
                    "priority_score": seed["focus_metric"]["value"],
                },
            },
        )
        risk_copy = RISK_COPY[evaluation.risk_label]
        normalized = self._family.normalize_case(
            workflow,
            {
                "patient_id": seed.get("patient_label"),
                "trigger_text": seed["trigger_text"],
                "completion_state": seed.get("completion_state", "unknown"),
                "priority_score": seed["focus_metric"]["value"],
            },
        )
        hydrated = {
            **seed,
            "workflow_title": workflow.title,
            "workflow_summary": workflow.summary,
            "family": workflow.family.value,
            "risk_tier": evaluation.risk_label,
            "risk_label": risk_copy["label"],
            "risk_reason": risk_copy["reason"],
            "disposition": evaluation.disposition,
            "queue_recommendation": evaluation.queue_recommendation,
            "rationale": evaluation.rationale,
            "recommended_actions": evaluation.recommended_actions,
            "matched_terms": normalized.matched_terms,
            "review": {
                "status": "open",
                "comment": "Awaiting triage review.",
                "updated_at": _now_iso(),
            },
            "audit": [
                {
                    "id": f"audit_seed_{seed['id']}",
                    "title": "Queue triage evaluation completed",
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
        return {seed["id"]: self._hydrate_case(seed) for seed in _load_demo_cases()}

    def _queue_summary(self) -> dict[str, int]:
        summary = {"watch": 0, "alert": 0, "urgent": 0}
        for case in self._cases.values():
            summary[case["risk_tier"]] += 1
        return summary

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            default_case = next(iter(self._cases.values()))
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
                "default_case_id": default_case["id"],
                "workspace": deepcopy(default_case),
            }

    def get_case(self, case_id: str) -> dict[str, Any]:
        with self._lock:
            if case_id not in self._cases:
                raise KeyError(case_id)
            return deepcopy(self._cases[case_id])

    def rerun(self, case_id: str) -> dict[str, Any]:
        with self._lock:
            case = self._cases[case_id]
            workflow = self._workflows[case["workflow_id"]]
            evaluation = self._family.evaluate(
                workflow,
                {
                    "patient_id": case.get("patient_label"),
                    "trigger_text": case["trigger_text"],
                    "completion_state": case.get("completion_state", "unknown"),
                    "priority_score": case["focus_metric"]["value"],
                },
            )
            risk_copy = RISK_COPY[evaluation.risk_label]
            case["risk_tier"] = evaluation.risk_label
            case["risk_label"] = risk_copy["label"]
            case["risk_reason"] = risk_copy["reason"]
            case["disposition"] = evaluation.disposition
            case["queue_recommendation"] = evaluation.queue_recommendation
            case["rationale"] = evaluation.rationale
            case["recommended_actions"] = evaluation.recommended_actions
            case["focus_metric"]["tone"] = evaluation.risk_label
            case["status"] = "triaged"
            case["review"]["updated_at"] = _now_iso()
            case["audit"].append(
                {
                    "id": f"audit_rerun_{case_id}_{len(case['audit']) + 1}",
                    "title": "Queue triage rerun completed",
                    "detail": evaluation.rationale[0],
                    "severity": "warning" if evaluation.risk_label in {"alert", "urgent"} else "info",
                    "created_at": _now_iso(),
                }
            )
            case["summary_cards"] = self._build_summary_cards(case)
            case["status_steps"] = self._build_steps(case)
            case["timeline"] = self._build_timeline(case)
            case["mock_email"] = self._build_mock_email(case)
            return deepcopy(case)

    def review(self, case_id: str, action: str, comment: str | None = None) -> dict[str, Any]:
        with self._lock:
            case = self._cases[case_id]
            action = action.lower()
            status_map = {
                "approve": "approved",
                "reject": "rejected",
                "watch": "watch",
                "acknowledge": "acknowledged",
            }
            case["review"] = {
                "status": action,
                "comment": comment or "No review note provided.",
                "updated_at": _now_iso(),
            }
            case["status"] = status_map.get(action, action)
            case["audit"].append(
                {
                    "id": f"audit_review_{case_id}_{len(case['audit']) + 1}",
                    "title": "Queue triage reviewed",
                    "detail": comment or f"Reviewer selected {action}.",
                    "severity": "info",
                    "created_at": _now_iso(),
                }
            )
            case["summary_cards"] = self._build_summary_cards(case)
            case["status_steps"] = self._build_steps(case)
            case["timeline"] = self._build_timeline(case)
            case["mock_email"] = self._build_mock_email(case)
            return deepcopy(case)

    def explain(self, case_id: str, question: str) -> dict[str, Any]:
        with self._lock:
            case = self._cases[case_id]
            question_lower = question.lower()
            if any(word in question_lower for word in ("why", "reason", "flag", "escalat")):
                answer = (
                    f"{case['title']} was flagged because {case['rationale'][0].lower()} "
                    f"The suggested queue move is to {case['queue_recommendation'].lower()}"
                )
            elif any(word in question_lower for word in ("next", "action", "do")):
                answer = (
                    f"Recommended next step: {case['queue_recommendation']} "
                    f"Owner: {case['owner']}. Due: {case['due_at']}."
                )
            else:
                answer = (
                    f"Risk tier is {case['risk_label']}. "
                    f"Current disposition: {case['disposition'].replace('_', ' ')}."
                )
            case["audit"].append(
                {
                    "id": f"audit_explain_{case_id}_{len(case['audit']) + 1}",
                    "title": "Queue triage explanation requested",
                    "detail": question,
                    "severity": "info",
                    "created_at": _now_iso(),
                }
            )
            return {
                "case_id": case_id,
                "question": question,
                "answer": answer,
                "updated_case": deepcopy(case),
            }


queue_triage_store = QueueTriageStore()
