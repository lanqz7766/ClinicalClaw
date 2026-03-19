from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from pydantic import BaseModel, Field


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class DemoMessage(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


class DemoTimelinePoint(BaseModel):
    study_id: str
    study_date: str
    age_years: int
    diagnosis: str
    sequence: str
    left_hippocampus_ml: float
    right_hippocampus_ml: float

    @property
    def total_hippocampus_ml(self) -> float:
        return round(self.left_hippocampus_ml + self.right_hippocampus_ml, 2)


class DemoReviewState(BaseModel):
    status: str = "in_review"
    reviewer: str = "Neuroradiology reviewer"
    comment: str = "Awaiting physician review."
    updated_at: str = Field(default_factory=_utc_now_iso)


class DemoAuditEvent(BaseModel):
    id: str
    title: str
    detail: str
    severity: str = "info"
    created_at: str = Field(default_factory=_utc_now_iso)


class DemoWorkspaceStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._cases = self._build_cases()

    def _build_cases(self) -> dict[str, dict[str, Any]]:
        timeline = [
            DemoTimelinePoint(
                study_id="oasis3-mr-2021-02",
                study_date="2021-02-14",
                age_years=71,
                diagnosis="Subjective cognitive decline",
                sequence="3D T1 MPRAGE",
                left_hippocampus_ml=3.42,
                right_hippocampus_ml=3.36,
            ),
            DemoTimelinePoint(
                study_id="oasis3-mr-2022-03",
                study_date="2022-03-10",
                age_years=72,
                diagnosis="Subjective cognitive decline",
                sequence="3D T1 MPRAGE",
                left_hippocampus_ml=3.29,
                right_hippocampus_ml=3.24,
            ),
            DemoTimelinePoint(
                study_id="oasis3-mr-2023-05",
                study_date="2023-05-04",
                age_years=73,
                diagnosis="Mild cognitive impairment",
                sequence="3D T1 MPRAGE",
                left_hippocampus_ml=3.11,
                right_hippocampus_ml=3.07,
            ),
            DemoTimelinePoint(
                study_id="oasis3-mr-2024-08",
                study_date="2024-08-19",
                age_years=74,
                diagnosis="Amnestic mild cognitive impairment",
                sequence="3D T1 MPRAGE",
                left_hippocampus_ml=2.86,
                right_hippocampus_ml=2.80,
            ),
        ]

        baseline_total = timeline[0].total_hippocampus_ml
        latest_total = timeline[-1].total_hippocampus_ml
        previous_total = timeline[-2].total_hippocampus_ml
        annual_change_pct = -4.7
        recent_segment_pct = -6.5
        delta_pct = round(((latest_total - baseline_total) / baseline_total) * 100, 1)
        acceleration_flag = recent_segment_pct < annual_change_pct - 1.0

        report_sections = [
            {
                "title": "Exam overview",
                "body": (
                    "Longitudinal review includes four T1-weighted MRI timepoints from the OASIS-3 mock "
                    "demonstration case. The patient timeline shows progression from subjective cognitive "
                    "decline to amnestic mild cognitive impairment."
                ),
            },
            {
                "title": "Structural volume change",
                "body": (
                    f"Combined hippocampal volume declined from {baseline_total:.2f} mL at baseline to "
                    f"{latest_total:.2f} mL at the latest study, a net change of {delta_pct}%."
                ),
            },
            {
                "title": "Annualized rate",
                "body": (
                    f"Estimated whole-period annualized hippocampal decline is {annual_change_pct}% per year, "
                    f"with a more recent segment change of {recent_segment_pct}% per year."
                ),
            },
            {
                "title": "Accelerated decline",
                "body": (
                    "Trend analysis flags accelerated decline because the latest interval is steeper than the "
                    "overall longitudinal slope. This should be treated as a physician-facing warning, not a "
                    "standalone diagnosis."
                ),
            },
            {
                "title": "Risk guidance",
                "body": (
                    "Current pattern supports a high-attention follow-up recommendation. Review alongside age, "
                    "MoCA or MMSE trend, vascular burden, medication history, and clinical symptom evolution."
                ),
            },
        ]

        initial_messages = [
            DemoMessage(
                id="msg_intro_1",
                role="assistant",
                content=(
                    "This mock workspace demonstrates a longitudinal hippocampal atrophy review using an "
                    "OASIS-3 style case. Ask for a report, request a trend explanation, or upload notes to "
                    "simulate additional context."
                ),
                created_at=_utc_now_iso(),
            )
        ]

        case = {
            "id": "oasis3-demo-hippocampus",
            "title": "OASIS-3 hippocampal atrophy review",
            "dataset": "OASIS-3 (mocked workspace state)",
            "patient": {
                "id": "OAS3-1142",
                "display_name": "Subject OAS3-1142",
                "sex": "Female",
                "age": 74,
                "diagnosis": "Amnestic mild cognitive impairment",
                "mrn": "DEMO-1142",
                "summary": (
                    "Four MRI timepoints over 3.5 years with progressive hippocampal volume loss and a more "
                    "rapid most recent interval."
                ),
            },
            "timeline": [
                {
                    "study_id": point.study_id,
                    "study_date": point.study_date,
                    "age_years": point.age_years,
                    "diagnosis": point.diagnosis,
                    "sequence": point.sequence,
                    "left_hippocampus_ml": point.left_hippocampus_ml,
                    "right_hippocampus_ml": point.right_hippocampus_ml,
                    "total_hippocampus_ml": point.total_hippocampus_ml,
                }
                for point in timeline
            ],
            "analysis": {
                "structure": "Bilateral hippocampus",
                "baseline_total_ml": baseline_total,
                "latest_total_ml": latest_total,
                "previous_total_ml": previous_total,
                "annual_change_pct": annual_change_pct,
                "recent_segment_pct": recent_segment_pct,
                "delta_pct": delta_pct,
                "recent_delta_vs_overall_pct": round(abs(recent_segment_pct) - abs(annual_change_pct), 1),
                "accelerated_decline": acceleration_flag,
                "risk_level": "High attention",
                "risk_reason": (
                    "Recent hippocampal decline is materially faster than the long-run slope and coincides "
                    "with worsening diagnostic labeling."
                ),
                "next_checks": [
                    "Correlate with MoCA or MMSE trajectory.",
                    "Review vascular burden and medication changes.",
                    "Consider whether interval shortening or repeat imaging is clinically warranted.",
                ],
            },
            "workflow": {
                "title": "Longitudinal hippocampal review",
                "status": "ready_for_review",
                "objective": (
                    "Compare four MRI timepoints, quantify bilateral hippocampal decline, flag acceleration, "
                    "and prepare a physician-facing report."
                ),
                "last_run_at": _utc_now_iso(),
                "steps": [
                    {
                        "name": "Load longitudinal case context",
                        "tool": "ehr_timeline_loader",
                        "status": "completed",
                        "detail": "Patient summary, diagnosis progression, and visit timeline were loaded.",
                    },
                    {
                        "name": "Read MRI timepoints",
                        "tool": "mri_series_selector",
                        "status": "completed",
                        "detail": "Four T1 MRI studies selected for longitudinal comparison.",
                    },
                    {
                        "name": "Calculate hippocampal trend",
                        "tool": "volume_trend_analyzer",
                        "status": "completed",
                        "detail": "Annualized and recent-segment decline rates were computed.",
                    },
                    {
                        "name": "Draft physician report",
                        "tool": "report_generator",
                        "status": "completed",
                        "detail": "Summary, risk tier, and follow-up guidance were refreshed.",
                    },
                ],
            },
            "imaging_preview": {
                "title": "Representative coronal slice",
                "caption": "Mock coronal hippocampal overlay for presentation only.",
                "image_url": "/demo-assets/hippocampus-preview.svg",
            },
            "report": {
                "title": "AI longitudinal hippocampal review",
                "subtitle": "Mock physician-facing summary for product prototyping",
                "risk_level": "High attention",
                "summary": (
                    "Bilateral hippocampal volume shows progressive decline across four MRI studies, with "
                    "the latest interval demonstrating a steeper drop than the overall trend. Findings support "
                    "closer physician review rather than automated diagnosis."
                ),
                "sections": report_sections,
                "physician_questions": [
                    "Does the cognitive trajectory match the imaging slope change?",
                    "Are there interval medication or vascular changes that could affect interpretation?",
                    "Should repeat MRI timing be shortened because the latest decline segment steepened?",
                ],
            },
            "review": DemoReviewState().model_dump(),
            "messages": [message.model_dump() for message in initial_messages],
            "uploads": [],
            "audit": [
                DemoAuditEvent(
                    id="audit_seed_1",
                    title="Mock dataset loaded",
                    detail="Initialized demo case from OASIS-3 style longitudinal metadata and precomputed volumes.",
                ).model_dump(),
                DemoAuditEvent(
                    id="audit_seed_2",
                    title="Longitudinal report prepared",
                    detail="Generated mock report sections and accelerated decline flag for UI prototyping.",
                ).model_dump(),
            ],
        }
        return {case["id"]: case}

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            default_case_id = next(iter(self._cases))
            return {
                "cases": [
                    {
                        "id": case["id"],
                        "title": case["title"],
                        "dataset": case["dataset"],
                        "patient": case["patient"],
                        "review": case["review"],
                        "risk_level": case["analysis"]["risk_level"],
                    }
                    for case in self._cases.values()
                ],
                "default_case_id": default_case_id,
                "workspace": deepcopy(self._cases[default_case_id]),
            }

    def get_case(self, case_id: str) -> dict[str, Any]:
        with self._lock:
            case = self._cases.get(case_id)
            if not case:
                raise KeyError(case_id)
            return deepcopy(case)

    def add_upload(self, case_id: str, filename: str) -> dict[str, Any]:
        with self._lock:
            case = self._cases[case_id]
            case["uploads"].append(
                {
                    "id": f"upload_{len(case['uploads']) + 1}",
                    "filename": filename,
                    "added_at": _utc_now_iso(),
                }
            )
            case["audit"].insert(
                0,
                DemoAuditEvent(
                    id=f"audit_upload_{len(case['audit']) + 1}",
                    title="Local file attached",
                    detail=f"Registered local mock upload: {filename}",
                ).model_dump(),
            )
            return deepcopy(case)

    def chat(self, case_id: str, message: str) -> dict[str, Any]:
        with self._lock:
            case = self._cases[case_id]
            user_message = DemoMessage(
                id=f"msg_user_{len(case['messages']) + 1}",
                role="user",
                content=message,
                created_at=_utc_now_iso(),
            )
            case["messages"].append(user_message.model_dump())

            lowered = message.lower()
            if "report" in lowered or "analy" in lowered or "atrophy" in lowered:
                assistant_text = (
                    "I reran the longitudinal workflow across four MRI timepoints. The refreshed mock output "
                    "shows accelerated bilateral hippocampal decline, estimates a -4.7% annualized change, "
                    "shows a steeper recent segment at -6.5% per year, and updates the physician review report."
                )
                audit_title = "Longitudinal analysis requested"
                audit_detail = "Chat-triggered mock analysis reran the hippocampal trend summary and refreshed the report."
                case["review"]["status"] = "in_review"
                case["review"]["comment"] = "AI report refreshed and ready for reviewer action."
                case["review"]["updated_at"] = _utc_now_iso()
                case["workflow"]["status"] = "ready_for_review"
                case["workflow"]["last_run_at"] = _utc_now_iso()
                case["workflow"]["steps"][-1]["detail"] = "Report rerun from chat instruction and ready for reviewer action."
            elif "risk" in lowered:
                assistant_text = (
                    "Risk is currently labeled High attention in this mock case because the most recent interval "
                    "declines faster than the overall slope. This is a trend-based warning, not a diagnosis."
                )
                audit_title = "Risk explanation requested"
                audit_detail = "Explained mock rule-based risk flag using overall versus recent hippocampal slope."
                case["workflow"]["status"] = "risk_explained"
            else:
                assistant_text = (
                    "I can help summarize the longitudinal trend, explain the risk flag, or regenerate the mock "
                    "report. Try asking for a report or for the latest hippocampal decline explanation."
                )
                audit_title = "General chat guidance"
                audit_detail = "Returned mock guidance for supported neuro longitudinal demo actions."
                case["workflow"]["status"] = "awaiting_instruction"

            assistant_message = DemoMessage(
                id=f"msg_assistant_{len(case['messages']) + 1}",
                role="assistant",
                content=assistant_text,
                created_at=_utc_now_iso(),
            )
            case["messages"].append(assistant_message.model_dump())
            case["audit"].insert(
                0,
                DemoAuditEvent(
                    id=f"audit_chat_{len(case['audit']) + 1}",
                    title=audit_title,
                    detail=audit_detail,
                ).model_dump(),
            )
            return {
                "assistant": assistant_message.model_dump(),
                "workspace": deepcopy(case),
            }

    def review(self, case_id: str, action: str, comment: str | None = None) -> dict[str, Any]:
        with self._lock:
            case = self._cases[case_id]
            normalized = action.strip().lower()
            status_map = {
                "approve": "approved",
                "reject": "rejected",
                "comment": case["review"]["status"],
            }
            status = status_map.get(normalized, case["review"]["status"])
            case["review"]["status"] = status
            case["review"]["comment"] = comment or case["review"]["comment"]
            case["review"]["updated_at"] = _utc_now_iso()
            if normalized == "approve":
                case["workflow"]["status"] = "approved"
            elif normalized == "reject":
                case["workflow"]["status"] = "rejected"
            elif normalized == "comment":
                case["workflow"]["status"] = "reviewer_commented"
            case["audit"].insert(
                0,
                DemoAuditEvent(
                    id=f"audit_review_{len(case['audit']) + 1}",
                    title=f"Reviewer action: {normalized}",
                    detail=comment or f"Review status changed to {status}.",
                    severity="success" if normalized == "approve" else "warning" if normalized == "reject" else "info",
                ).model_dump(),
            )
            return deepcopy(case)


demo_workspace_store = DemoWorkspaceStore()
