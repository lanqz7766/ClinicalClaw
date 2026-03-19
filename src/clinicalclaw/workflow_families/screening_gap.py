from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from clinicalclaw.workflow_engine import WorkflowActionKind, WorkflowDefinition, WorkflowFamily

DEFAULT_ACTIONABLE_TERMS = (
    "positive fit",
    "fecal immunochemical",
    "colonoscopy",
    "screening gap",
    "screening follow-up",
)

DEFAULT_URGENT_TERMS = (
    "overdue",
    "delayed",
    "weeks unresolved",
    "months unresolved",
    "weight loss",
    "anemia",
    "bleeding",
)

DEFAULT_RESOLVED_STATES = {"ordered", "scheduled", "completed", "addressed", "booked", "resolved"}


class ScreeningGapCase(BaseModel):
    workflow_id: str
    patient_id: str | None = None
    screening_text: str
    followup_summary: str = ""
    completion_state: str = "unknown"
    evidence_snippets: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)


class ScreeningGapEvaluation(BaseModel):
    workflow_id: str
    disposition: str
    risk_label: str
    review_required: bool
    gap_recommendation: str
    rationale: list[str]
    recommended_actions: list[str]


class ScreeningGapFamily:
    family = WorkflowFamily.screening_gap_closure

    def supports(self, workflow: WorkflowDefinition) -> bool:
        return workflow.family == self.family

    def normalize_case(self, workflow: WorkflowDefinition, payload: dict[str, Any]) -> ScreeningGapCase:
        if not self.supports(workflow):
            raise ValueError(f"workflow {workflow.id} is not part of screening_gap_closure")

        screening_text = (
            payload.get("screening_text")
            or payload.get("report_text")
            or payload.get("trigger_text")
            or payload.get("note_text")
            or ""
        ).strip()
        followup_summary = (
            payload.get("followup_summary")
            or payload.get("completion_state")
            or payload.get("screening_history")
            or ""
        ).strip()
        completion_state = str(payload.get("completion_state") or "unknown").lower()
        terms = [term.lower() for term in workflow.family_config.get("actionable_terms", DEFAULT_ACTIONABLE_TERMS)]
        combined = f"{screening_text} {followup_summary}".lower()
        evidence_snippets = [line.strip() for line in screening_text.splitlines() if line.strip()]
        matched_terms = sorted({term for term in terms if term in combined})
        return ScreeningGapCase(
            workflow_id=workflow.id,
            patient_id=payload.get("patient_id"),
            screening_text=screening_text,
            followup_summary=followup_summary,
            completion_state=completion_state,
            evidence_snippets=evidence_snippets[:3],
            matched_terms=matched_terms,
        )

    def evaluate(self, workflow: WorkflowDefinition, payload: dict[str, Any]) -> ScreeningGapEvaluation:
        case = self.normalize_case(workflow, payload)
        resolved_states = {
            state.lower()
            for state in workflow.family_config.get("resolved_states", sorted(DEFAULT_RESOLVED_STATES))
        }
        urgent_terms = {term.lower() for term in workflow.family_config.get("urgent_terms", DEFAULT_URGENT_TERMS)}
        text = f"{case.screening_text} {case.followup_summary}".lower()
        has_gap_language = bool(case.matched_terms)

        rationale: list[str] = []
        if case.completion_state in resolved_states or "completed" in text or "scheduled" in text:
            rationale.append("The screening gap is already closed or at least clearly scheduled.")
            disposition = "already_addressed"
            risk_label = "watch"
            review_required = False
            gap_recommendation = "Keep the current screening follow-up pathway and monitor completion."
        elif has_gap_language and any(term in text for term in urgent_terms):
            rationale.append("The result suggests a screening gap with overdue language and no closure signal.")
            disposition = "gap_likely"
            risk_label = "urgent"
            review_required = True
            gap_recommendation = "Escalate to the responsible clinician and request prompt follow-up."
        elif has_gap_language:
            rationale.append("The result suggests a screening gap but the case does not yet look overdue.")
            disposition = "gap_possible"
            risk_label = "alert"
            review_required = True
            gap_recommendation = "Open a screening follow-up task and verify the diagnostic next step."
        else:
            rationale.append("No strong screening gap language was found, but the case remains under review.")
            disposition = "needs_review"
            risk_label = "watch"
            review_required = True
            gap_recommendation = "Review the screening record for missing follow-up signals."

        recommended_actions = [
            action.label
            for action in workflow.actions
            if action.kind
            in {
                WorkflowActionKind.create_review_item,
                WorkflowActionKind.draft_followup_plan,
                WorkflowActionKind.draft_order,
                WorkflowActionKind.mock_email,
            }
        ]

        return ScreeningGapEvaluation(
            workflow_id=workflow.id,
            disposition=disposition,
            risk_label=risk_label,
            review_required=review_required,
            gap_recommendation=gap_recommendation,
            rationale=rationale,
            recommended_actions=recommended_actions[:3],
        )
