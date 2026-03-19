from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from math import ceil
from pathlib import Path
from threading import Lock
from typing import Any

from clinicalclaw.workflow_engine import WorkflowDefinition
from clinicalclaw.workflow_families.screening_gap import ScreeningGapFamily


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _title_case(value: str) -> str:
    return value.replace("_", " ").title()


RISK_COPY = {
    "watch": {
        "label": "Watch",
        "reason": "The screening follow-up is either already arranged or does not yet show a clear gap.",
    },
    "alert": {
        "label": "Alert",
        "reason": "The screening result appears to need diagnostic follow-up and should be reviewed soon.",
    },
    "urgent": {
        "label": "Urgent",
        "reason": "The screening result suggests a likely missed follow-up with overdue language or additional risk markers.",
    },
}


WORKFLOW_PATH = Path(__file__).resolve().parents[2] / "workflows" / "screening_gap" / "screening_gap_positive_fit_followup.json"
DEMO_STORE_PATH = (
    Path(__file__).resolve().parents[2]
    / "workflows"
    / "screening_gap"
    / "screening_gap_positive_fit_followup_demo_store.json"
)


def load_screening_gap_workflow() -> WorkflowDefinition:
    return WorkflowDefinition.model_validate_json(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _default_demo_cases() -> list[dict[str, Any]]:
    return [
        {
            "id": "sg_case_001",
            "workflow_id": "screening_gap_positive_fit_followup",
            "title": "Positive FIT without colonoscopy follow-up",
            "submitted_by": "Population health navigator",
            "received_at": "2026-03-18T09:10:00+00:00",
            "status": "new",
            "owner": "Primary care navigator",
            "queue": "Colorectal screening closure",
            "due_at": "2026-03-18T12:00:00+00:00",
            "patient_label": "Demo Screen A",
            "service_line": "Primary care",
            "source_type": "lab",
            "clinical_context": "Positive stool screening result with overdue colonoscopy follow-up and no order in the chart.",
            "completion_state": "unknown",
            "screening_text": "Positive FIT result documented. Colonoscopy is overdue and no order or completion was found.",
            "followup_summary": "Overdue follow-up has not been placed.",
            "focus_metric": {
                "label": "Gap score",
                "value": 93,
                "unit": "/100",
                "delta": "+27 at review",
                "tone": "urgent",
            },
            "trend_points": [
                {"label": "Intake", "value": 66},
                {"label": "Navigator", "value": 79},
                {"label": "Current", "value": 93},
            ],
            "evidence_grid": [
                {"label": "Screening signal", "value": "Positive FIT"},
                {"label": "Follow-up", "value": "No colonoscopy order"},
                {"label": "Target action", "value": "Open review item"},
                {"label": "Current closure", "value": "Open"},
            ],
        },
        {
            "id": "sg_case_002",
            "workflow_id": "screening_gap_positive_fit_followup",
            "title": "Positive FIT already scheduled for colonoscopy",
            "submitted_by": "Population health navigator",
            "received_at": "2026-03-18T10:05:00+00:00",
            "status": "new",
            "owner": "Primary care navigator",
            "queue": "Colorectal screening closure",
            "due_at": "2026-03-25T09:00:00+00:00",
            "patient_label": "Demo Screen B",
            "service_line": "Primary care",
            "source_type": "lab",
            "clinical_context": "Colonoscopy appointment has already been placed on the schedule.",
            "completion_state": "scheduled",
            "screening_text": "Positive FIT result documented. Colonoscopy is scheduled next week.",
            "followup_summary": "Diagnostic colonoscopy booking confirmed.",
            "focus_metric": {
                "label": "Gap score",
                "value": 49,
                "unit": "/100",
                "delta": "Follow-up scheduled",
                "tone": "watch",
            },
            "trend_points": [
                {"label": "Intake", "value": 49},
                {"label": "Registry", "value": 49},
            ],
            "evidence_grid": [
                {"label": "Screening signal", "value": "Positive FIT"},
                {"label": "Follow-up", "value": "Colonoscopy scheduled"},
                {"label": "Target action", "value": "Confirm booking"},
                {"label": "Current closure", "value": "Scheduled"},
            ],
        },
        {
            "id": "sg_case_003",
            "workflow_id": "screening_gap_positive_fit_followup",
            "title": "Positive FIT with delayed diagnostic follow-up",
            "submitted_by": "Screening registry feed",
            "received_at": "2026-03-18T14:25:00+00:00",
            "status": "new",
            "owner": "Colorectal screening coordinator",
            "queue": "Open screening gaps",
            "due_at": "2026-03-18T18:00:00+00:00",
            "patient_label": "Demo Screen C",
            "service_line": "Gastroenterology",
            "source_type": "lab",
            "clinical_context": "Follow-up has not been documented in the chart.",
            "completion_state": "unknown",
            "screening_text": "Positive FIT remains unresolved. Colonoscopy follow-up is not documented.",
            "followup_summary": "No diagnostic step is recorded.",
            "focus_metric": {
                "label": "Gap score",
                "value": 80,
                "unit": "/100",
                "delta": "+15 at triage",
                "tone": "alert",
            },
            "trend_points": [
                {"label": "Initial", "value": 65},
                {"label": "Triage", "value": 80},
            ],
            "evidence_grid": [
                {"label": "Screening signal", "value": "Positive FIT"},
                {"label": "Follow-up", "value": "Delayed and undocumented"},
                {"label": "Target action", "value": "Prompt clinician review"},
                {"label": "Current closure", "value": "Open"},
            ],
        },
    ]


def _load_demo_cases() -> list[dict[str, Any]]:
    if DEMO_STORE_PATH.exists():
        payload = json.loads(DEMO_STORE_PATH.read_text(encoding="utf-8"))
        cases = payload.get("cases")
        if isinstance(cases, list) and cases:
            return cases
    return _default_demo_cases()


class ScreeningGapStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._workflow = load_screening_gap_workflow()
        self._family = ScreeningGapFamily()
        self._cases = self._seed_cases()

    def _build_summary_cards(self, case: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {"label": "Risk", "value": case["risk_label"], "tone": case["risk_tier"]},
            {"label": "Disposition", "value": _title_case(case["disposition"]), "tone": "neutral"},
            {"label": "Owner", "value": case["owner"], "tone": "neutral"},
            {"label": "Due", "value": case["due_at"], "tone": "neutral"},
        ]

    def _build_timeline(self, case: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {
                "title": "Screening result entered",
                "detail": f"{case['submitted_by']} opened the case.",
                "created_at": case["received_at"],
            },
            {
                "title": "Gap engine completed review",
                "detail": f"Assigned {case['risk_label']} based on screening language and follow-up status.",
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
            "to": "screening-ops@clinicalclaw.demo",
            "subject": f"[{case['risk_label']}] {case['workflow_title']}",
            "body": (
                f"{case['title']} was evaluated as {case['risk_label']}. "
                f"Recommended next actions: {', '.join(case['recommended_actions']) or 'manual review'}."
            ),
            "sent": case["risk_tier"] in {"alert", "urgent"},
        }

    def _seed_cases(self) -> dict[str, dict[str, Any]]:
        seeded: dict[str, dict[str, Any]] = {}
        for seed in _load_demo_cases():
            evaluation = self._family.evaluate(
                self._workflow,
                {
                    "patient_id": seed.get("patient_label"),
                    "screening_text": seed["screening_text"],
                    "followup_summary": seed.get("followup_summary", ""),
                    "completion_state": seed.get("completion_state", "unknown"),
                },
            )
            risk_copy = RISK_COPY[evaluation.risk_label]
            seeded_case = {
                **seed,
                "workflow_title": self._workflow.title,
                "workflow_summary": self._workflow.summary,
                "family": self._workflow.family.value,
                "risk_tier": evaluation.risk_label,
                "risk_label": risk_copy["label"],
                "risk_reason": risk_copy["reason"],
                "disposition": evaluation.disposition,
                "gap_recommendation": evaluation.gap_recommendation,
                "rationale": evaluation.rationale,
                "recommended_actions": evaluation.recommended_actions,
                "matched_terms": self._family.normalize_case(
                    self._workflow,
                    {
                        "patient_id": seed.get("patient_label"),
                        "screening_text": seed["screening_text"],
                        "followup_summary": seed.get("followup_summary", ""),
                        "completion_state": seed.get("completion_state", "unknown"),
                    },
                ).matched_terms,
                "review": {
                    "status": "open",
                    "comment": "Awaiting screening gap review.",
                    "updated_at": _now_iso(),
                },
                "audit": [
                    {
                        "id": f"audit_seed_{seed['id']}",
                        "title": "Initial screening gap scan completed",
                        "detail": evaluation.rationale[0],
                        "severity": "warning" if evaluation.risk_label in {"alert", "urgent"} else "info",
                        "created_at": _now_iso(),
                    }
                ],
            }
            seeded_case["summary_cards"] = self._build_summary_cards(seeded_case)
            seeded_case["timeline"] = self._build_timeline(seeded_case)
            seeded_case["mock_email"] = self._build_mock_email(seeded_case)
            seeded[seed["id"]] = seeded_case
        return seeded

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            default_case = next(iter(self._cases.values()))
            queue_summary = {"watch": 0, "alert": 0, "urgent": 0}
            for case in self._cases.values():
                queue_summary[case["risk_tier"]] += 1
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
                "queue_summary": queue_summary,
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
            evaluation = self._family.evaluate(
                self._workflow,
                {
                    "patient_id": case.get("patient_label"),
                    "screening_text": case["screening_text"],
                    "followup_summary": case.get("followup_summary", ""),
                    "completion_state": case.get("completion_state", "unknown"),
                },
            )
            risk_copy = RISK_COPY[evaluation.risk_label]
            case["risk_tier"] = evaluation.risk_label
            case["risk_label"] = risk_copy["label"]
            case["risk_reason"] = risk_copy["reason"]
            case["disposition"] = evaluation.disposition
            case["gap_recommendation"] = evaluation.gap_recommendation
            case["rationale"] = evaluation.rationale
            case["recommended_actions"] = evaluation.recommended_actions
            case["mock_email"] = self._build_mock_email(case)
            case["summary_cards"] = self._build_summary_cards(case)
            case["timeline"] = self._build_timeline(case)
            case["audit"].insert(
                0,
                {
                    "id": f"audit_rerun_{case_id}_{ceil(datetime.now(UTC).timestamp())}",
                    "title": "Screening gap engine rerun",
                    "detail": f"Priority refreshed to {risk_copy['label']} after rescoring the screening gap.",
                    "severity": "success" if evaluation.risk_label in {"alert", "urgent"} else "info",
                    "created_at": _now_iso(),
                },
            )
            return deepcopy(case)

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
                    "detail": comment or f"Reviewer changed case state to {normalized}.",
                    "severity": "warning" if normalized in {"reject", "urgent"} else "success" if normalized == "approve" else "info",
                    "created_at": _now_iso(),
                },
            )
            return deepcopy(case)

    def explain(self, case_id: str, question: str) -> dict[str, Any]:
        with self._lock:
            case = self._cases[case_id]
            lowered = question.lower()
            if "email" in lowered or "alert" in lowered:
                answer = (
                    f"This case is currently {case['risk_label']}. The mock email alert is "
                    f"{'prepared and marked sent' if case['mock_email']['sent'] else 'prepared but not sent'} "
                    f"to {case['mock_email']['to']}."
                )
            elif "next" in lowered or "action" in lowered or "do" in lowered:
                answer = (
                    f"The active owner is {case['owner']}. Next recommended actions are: "
                    f"{'; '.join(case['recommended_actions'][:2])}."
                )
            else:
                answer = (
                    f"The key screening gap is {', '.join(case['matched_terms']) or 'positive FIT with no closure signal'}. "
                    f"Disposition: {case['disposition'].replace('_', ' ')}."
                )
            case["audit"].insert(
                0,
                {
                    "id": f"audit_chat_{case_id}_{ceil(datetime.now(UTC).timestamp())}",
                    "title": "Screening gap explainer used",
                    "detail": answer,
                    "severity": "info",
                    "created_at": _now_iso(),
                },
            )
            return {"answer": answer, "workspace": deepcopy(case)}


screening_gap_store = ScreeningGapStore()
