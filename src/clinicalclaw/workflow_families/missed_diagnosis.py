from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from clinicalclaw.workflow_engine import WorkflowActionKind, WorkflowDefinition, WorkflowFamily

DEFAULT_EVIDENCE_TERMS = (
    "compression fracture",
    "vertebral fracture",
    "vertebral compression fracture",
    "osteoporosis",
    "fragility fracture",
    "bone density",
    "dexa",
    "follow-up",
    "workup",
    "evaluation",
)

DEFAULT_URGENT_TERMS = (
    "new",
    "acute",
    "severe",
    "multiple",
    "progressive",
    "pain",
    "height loss",
)

DEFAULT_RESOLVED_STATES = {"completed", "scheduled", "addressed", "documented", "closed", "resolved"}


class MissedDiagnosisCase(BaseModel):
    workflow_id: str
    patient_id: str | None = None
    report_text: str
    followup_summary: str = ""
    completion_state: str = "unknown"
    evidence_snippets: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)


class MissedDiagnosisEvaluation(BaseModel):
    workflow_id: str
    disposition: str
    risk_label: str
    review_required: bool
    gap_recommendation: str
    rationale: list[str]
    recommended_actions: list[str]


class MissedDiagnosisFamily:
    family = WorkflowFamily.missed_diagnosis_detection

    def supports(self, workflow: WorkflowDefinition) -> bool:
        return workflow.family == self.family

    def normalize_case(self, workflow: WorkflowDefinition, payload: dict[str, Any]) -> MissedDiagnosisCase:
        if not self.supports(workflow):
            raise ValueError(f"workflow {workflow.id} is not part of missed_diagnosis_detection")

        report_text = (
            payload.get("report_text")
            or payload.get("finding_text")
            or payload.get("trigger_text")
            or payload.get("note_text")
            or ""
        ).strip()
        followup_summary = (
            payload.get("followup_summary")
            or payload.get("completion_state")
            or payload.get("follow_up_status")
            or ""
        ).strip()
        completion_state = str(payload.get("completion_state") or "unknown").lower()
        terms = [term.lower() for term in workflow.family_config.get("evidence_terms", DEFAULT_EVIDENCE_TERMS)]
        combined = f"{report_text} {followup_summary}".lower()
        evidence_snippets = [line.strip() for line in report_text.splitlines() if line.strip()]
        matched_terms = sorted({term for term in terms if term in combined})
        return MissedDiagnosisCase(
            workflow_id=workflow.id,
            patient_id=payload.get("patient_id"),
            report_text=report_text,
            followup_summary=followup_summary,
            completion_state=completion_state,
            evidence_snippets=evidence_snippets[:3],
            matched_terms=matched_terms,
        )

    def evaluate(self, workflow: WorkflowDefinition, payload: dict[str, Any]) -> MissedDiagnosisEvaluation:
        case = self.normalize_case(workflow, payload)
        resolved_states = {
            state.lower()
            for state in workflow.family_config.get("resolved_states", sorted(DEFAULT_RESOLVED_STATES))
        }
        urgent_terms = {term.lower() for term in workflow.family_config.get("urgent_terms", DEFAULT_URGENT_TERMS)}
        text = f"{case.report_text} {case.followup_summary}".lower()
        has_evidence = bool(case.matched_terms)

        rationale: list[str] = []
        if case.completion_state in resolved_states or "scheduled" in text or "completed" in text:
            rationale.append("The fracture pathway already shows follow-up, scheduling, or completion.")
            disposition = "already_addressed"
            risk_label = "watch"
            review_required = False
            gap_recommendation = "Keep the current follow-up pathway and monitor for completion."
        elif has_evidence and any(term in text for term in urgent_terms):
            rationale.append("The report contains vertebral fracture language with urgent descriptors and no closure signal.")
            disposition = "likely_missed_diagnosis"
            risk_label = "urgent"
            review_required = True
            gap_recommendation = "Escalate to a clinician and request prompt osteoporosis evaluation."
        elif has_evidence:
            rationale.append("The report mentions vertebral fracture or osteoporosis language without clear follow-up closure.")
            disposition = "needs_review"
            risk_label = "alert"
            review_required = True
            gap_recommendation = "Open a fracture follow-up task and confirm osteoporosis workup."
        else:
            rationale.append("No convincing fracture signal was found, but the case remains open for manual review.")
            disposition = "needs_review"
            risk_label = "watch"
            review_required = True
            gap_recommendation = "Review the report for missed fracture or bone health language."

        recommended_actions = [
            action.label
            for action in workflow.actions
            if action.kind
            in {
                WorkflowActionKind.create_review_item,
                WorkflowActionKind.draft_followup_plan,
                WorkflowActionKind.draft_order,
                WorkflowActionKind.mock_email,
                WorkflowActionKind.chart_summary,
            }
        ]

        return MissedDiagnosisEvaluation(
            workflow_id=workflow.id,
            disposition=disposition,
            risk_label=risk_label,
            review_required=review_required,
            gap_recommendation=gap_recommendation,
            rationale=rationale,
            recommended_actions=recommended_actions[:3],
        )
