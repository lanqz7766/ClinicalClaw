from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from clinicalclaw.workflow_engine import WorkflowActionKind, WorkflowDefinition, WorkflowFamily

DEFAULT_ACTIONABLE_TERMS = (
    "follow-up",
    "follow up",
    "recommend",
    "suspicious",
    "positive",
    "critical",
    "abnormal",
    "urgent",
)

DEFAULT_RESOLVED_STATES = {"completed", "scheduled", "addressed", "filed", "resolved"}


class FindingsClosureCase(BaseModel):
    workflow_id: str
    patient_id: str | None = None
    trigger_text: str
    completion_state: str = "unknown"
    evidence_snippets: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)


class FindingsClosureEvaluation(BaseModel):
    workflow_id: str
    disposition: str
    risk_label: str
    review_required: bool
    rationale: list[str]
    recommended_actions: list[str]


class FindingsClosureFamily:
    family = WorkflowFamily.findings_closure

    def supports(self, workflow: WorkflowDefinition) -> bool:
        return workflow.family == self.family

    def normalize_case(self, workflow: WorkflowDefinition, payload: dict[str, Any]) -> FindingsClosureCase:
        if not self.supports(workflow):
            raise ValueError(f"workflow {workflow.id} is not part of findings_closure")

        trigger_text = (
            payload.get("trigger_text")
            or payload.get("report_text")
            or payload.get("lab_text")
            or payload.get("finding_text")
            or ""
        ).strip()
        completion_state = str(payload.get("completion_state") or "unknown").lower()
        terms = [term.lower() for term in workflow.family_config.get("actionable_terms", DEFAULT_ACTIONABLE_TERMS)]
        snippets = [line.strip() for line in trigger_text.splitlines() if line.strip()]
        matched_terms = sorted({term for term in terms if term in trigger_text.lower()})
        return FindingsClosureCase(
            workflow_id=workflow.id,
            patient_id=payload.get("patient_id"),
            trigger_text=trigger_text,
            completion_state=completion_state,
            evidence_snippets=snippets[:3],
            matched_terms=matched_terms,
        )

    def evaluate(self, workflow: WorkflowDefinition, payload: dict[str, Any]) -> FindingsClosureEvaluation:
        case = self.normalize_case(workflow, payload)
        resolved_states = {
            state.lower()
            for state in workflow.family_config.get("resolved_states", sorted(DEFAULT_RESOLVED_STATES))
        }
        urgent_terms = {
            term.lower()
            for term in workflow.family_config.get("urgent_terms", ["critical", "urgent", "stat", "immediate"])
        }

        rationale: list[str] = []
        if case.completion_state in resolved_states:
            rationale.append(f"Completion state is already '{case.completion_state}'.")
            disposition = "already_addressed"
            risk_label = "watch"
        else:
            if any(term in case.trigger_text.lower() for term in urgent_terms):
                rationale.append("Urgent escalation language was detected in the trigger text.")
                disposition = "review_required"
                risk_label = "urgent"
            elif case.matched_terms:
                rationale.append(
                    "Actionable follow-up language was detected: " + ", ".join(case.matched_terms[:4]) + "."
                )
                disposition = "ready_for_action"
                risk_label = "alert"
            else:
                rationale.append("The case has not been closed and still needs manual review.")
                disposition = "review_required"
                risk_label = "watch"

        recommended_actions = [
            action.label
            for action in workflow.actions
            if action.kind
            in {
                WorkflowActionKind.create_review_item,
                WorkflowActionKind.draft_followup_plan,
                WorkflowActionKind.draft_order,
                WorkflowActionKind.mock_email,
                WorkflowActionKind.draft_schedule,
            }
        ]

        return FindingsClosureEvaluation(
            workflow_id=workflow.id,
            disposition=disposition,
            risk_label=risk_label,
            review_required=True,
            rationale=rationale,
            recommended_actions=recommended_actions[:3],
        )
