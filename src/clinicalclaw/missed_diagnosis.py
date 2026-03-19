from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from math import ceil
from pathlib import Path
from threading import Lock
from typing import Any

from clinicalclaw.workflow_engine import load_workflow_map
from clinicalclaw.workflow_families.missed_diagnosis import MissedDiagnosisFamily


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _title_case(value: str) -> str:
    return value.replace("_", " ").title()


RISK_COPY = {
    "watch": {
        "label": "Watch",
        "reason": "The report contains a possible diagnosis gap, but the record suggests the pathway may already be addressed.",
    },
    "alert": {
        "label": "Alert",
        "reason": "The report contains a likely missed diagnosis signal and should be reviewed promptly.",
    },
    "urgent": {
        "label": "Urgent",
        "reason": "The report suggests a likely missed vertebral fracture diagnosis with no clear follow-up closure.",
    },
}


DEFAULT_DEMO_STORE = Path(__file__).resolve().parents[2] / "workflows" / "missed_vertebral_fracture_detection_demo_store.json"


def _default_demo_cases() -> list[dict[str, Any]]:
    return [
        {
            "id": "md_case_001",
            "workflow_id": "missed_vertebral_fracture_detection",
            "title": "Thoracic compression fracture mentioned without osteoporosis workup",
            "submitted_by": "Radiology QA feed",
            "received_at": "2026-03-18T09:20:00+00:00",
            "status": "new",
            "owner": "Primary care triage clinician",
            "queue": "Missed diagnosis review",
            "due_at": "2026-03-18T12:00:00+00:00",
            "patient_label": "Demo Spine A",
            "service_line": "Radiology",
            "source_type": "report",
            "clinical_context": "No DEXA order, no bone health note, and no fracture follow-up in the chart.",
            "completion_state": "unknown",
            "report_text": (
                "Mild acute vertebral compression fracture at T8 with height loss. Recommend correlation for osteoporosis."
            ),
            "followup_summary": "No follow-up order or osteoporosis workup found.",
            "focus_metric": {
                "label": "Gap score",
                "value": 92,
                "unit": "/100",
                "delta": "+24 at review",
                "tone": "urgent",
            },
            "trend_points": [
                {"label": "Initial read", "value": 68},
                {"label": "QA screen", "value": 80},
                {"label": "Current", "value": 92},
            ],
            "evidence_grid": [
                {"label": "Fracture signal", "value": "Acute T8 compression fracture"},
                {"label": "Follow-up", "value": "No osteoporosis workup"},
                {"label": "Target action", "value": "Open fracture review"},
                {"label": "Current closure", "value": "Open"},
            ],
        },
        {
            "id": "md_case_002",
            "workflow_id": "missed_vertebral_fracture_detection",
            "title": "Lumbar vertebral fracture already routed to bone health clinic",
            "submitted_by": "Radiology follow-up registry",
            "received_at": "2026-03-18T10:55:00+00:00",
            "status": "new",
            "owner": "Bone health coordinator",
            "queue": "Fracture follow-up",
            "due_at": "2026-03-22T09:00:00+00:00",
            "patient_label": "Demo Spine B",
            "service_line": "Primary care",
            "source_type": "report",
            "clinical_context": "Referral already sent to the bone health clinic after initial review.",
            "completion_state": "scheduled",
            "report_text": "Chronic vertebral fracture deformity at L1. Osteoporosis evaluation has already been scheduled.",
            "followup_summary": "Bone health clinic visit scheduled next week.",
            "focus_metric": {
                "label": "Gap score",
                "value": 51,
                "unit": "/100",
                "delta": "Follow-up scheduled",
                "tone": "watch",
            },
            "trend_points": [
                {"label": "Initial read", "value": 49},
                {"label": "Registry check", "value": 51},
            ],
            "evidence_grid": [
                {"label": "Fracture signal", "value": "Chronic L1 deformity"},
                {"label": "Follow-up", "value": "Scheduled bone health clinic"},
                {"label": "Target action", "value": "Confirm appointment"},
                {"label": "Current closure", "value": "Scheduled"},
            ],
        },
        {
            "id": "md_case_003",
            "workflow_id": "missed_vertebral_fracture_detection",
            "title": "Possible vertebral compression fracture with pending review",
            "submitted_by": "ED report feed",
            "received_at": "2026-03-18T14:10:00+00:00",
            "status": "new",
            "owner": "Hospitalist review nurse",
            "queue": "Open radiology gaps",
            "due_at": "2026-03-18T18:00:00+00:00",
            "patient_label": "Demo Spine C",
            "service_line": "Emergency medicine",
            "source_type": "report",
            "clinical_context": "Back pain was noted, but next-step workup is unclear.",
            "completion_state": "unknown",
            "report_text": "Possible vertebral compression fracture. Recommend osteoporosis evaluation.",
            "followup_summary": "No clear documentation of DEXA, labs, or bone health referral.",
            "focus_metric": {
                "label": "Gap score",
                "value": 78,
                "unit": "/100",
                "delta": "+13 at triage",
                "tone": "alert",
            },
            "trend_points": [
                {"label": "Initial read", "value": 61},
                {"label": "Triage", "value": 78},
            ],
            "evidence_grid": [
                {"label": "Fracture signal", "value": "Compression fracture language"},
                {"label": "Follow-up", "value": "No clear workup documented"},
                {"label": "Target action", "value": "Prompt clinician review"},
                {"label": "Current closure", "value": "Open"},
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


class MissedDiagnosisStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._workflows = load_workflow_map("workflows")
        self._family = MissedDiagnosisFamily()
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
                "title": "Report entered missed-diagnosis review",
                "detail": f"{case['submitted_by']} opened the case.",
                "created_at": case["received_at"],
            },
            {
                "title": "Gap engine completed review",
                "detail": f"Assigned {case['risk_label']} based on vertebral fracture language and follow-up status.",
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
            "to": "diagnostic-review@clinicalclaw.demo",
            "subject": f"[{case['risk_label']}] {case['workflow_title']}",
            "body": (
                f"{case['title']} was evaluated as {case['risk_label']}. "
                f"Recommended next actions: {', '.join(case['recommended_actions']) or 'manual review'}."
            ),
            "sent": case["risk_tier"] in {"alert", "urgent"},
        }

    def _seed_cases(self) -> dict[str, dict[str, Any]]:
        workflow = self._workflows["missed_vertebral_fracture_detection"]
        seeded: dict[str, dict[str, Any]] = {}
        for seed in _load_demo_cases():
            evaluation = self._family.evaluate(
                workflow,
                {
                    "patient_id": seed.get("patient_label"),
                    "report_text": seed["report_text"],
                    "followup_summary": seed.get("followup_summary", ""),
                    "completion_state": seed.get("completion_state", "unknown"),
                },
            )
            risk_copy = RISK_COPY[evaluation.risk_label]
            seeded_case = {
                **seed,
                "workflow_title": workflow.title,
                "workflow_summary": workflow.summary,
                "family": workflow.family.value,
                "risk_tier": evaluation.risk_label,
                "risk_label": risk_copy["label"],
                "risk_reason": risk_copy["reason"],
                "disposition": evaluation.disposition,
                "gap_recommendation": evaluation.gap_recommendation,
                "rationale": evaluation.rationale,
                "recommended_actions": evaluation.recommended_actions,
                "matched_terms": self._family.normalize_case(
                    workflow,
                    {
                        "patient_id": seed.get("patient_label"),
                        "report_text": seed["report_text"],
                        "followup_summary": seed.get("followup_summary", ""),
                        "completion_state": seed.get("completion_state", "unknown"),
                    },
                ).matched_terms,
                "review": {
                    "status": "open",
                    "comment": "Awaiting missed diagnosis review.",
                    "updated_at": _now_iso(),
                },
                "audit": [
                    {
                        "id": f"audit_seed_{seed['id']}",
                        "title": "Initial missed diagnosis scan completed",
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
            workflow = self._workflows[case["workflow_id"]]
            evaluation = self._family.evaluate(
                workflow,
                {
                    "patient_id": case.get("patient_label"),
                    "report_text": case["report_text"],
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
                    "title": "Missed diagnosis engine rerun",
                    "detail": f"Priority refreshed to {risk_copy['label']} after rescoring the vertebral fracture gap.",
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
                    f"The key gap is {', '.join(case['matched_terms']) or 'vertebral fracture language without closure'}. "
                    f"Disposition: {case['disposition'].replace('_', ' ')}."
                )
            case["audit"].insert(
                0,
                {
                    "id": f"audit_chat_{case_id}_{ceil(datetime.now(UTC).timestamp())}",
                    "title": "Missed diagnosis explainer used",
                    "detail": answer,
                    "severity": "info",
                    "created_at": _now_iso(),
                },
            )
            return {"answer": answer, "workspace": deepcopy(case)}


missed_diagnosis_store = MissedDiagnosisStore()
