from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from clinicalclaw.workflow_engine import WorkflowActionKind, WorkflowDefinition, WorkflowFamily

DEFAULT_PRIORITY_TERMS = (
    "urgent",
    "high-risk",
    "high risk",
    "expedite",
    "fast-track",
    "rapid access",
    "worsening",
    "same day",
    "today",
    "priority",
)

DEFAULT_URGENT_TERMS = (
    "emergency",
    "stat",
    "immediately",
    "rapidly worsening",
    "hemoptysis",
    "syncope",
    "severe",
)

DEFAULT_RESOLVED_STATES = {"assigned", "booked", "scheduled", "routed", "acknowledged", "completed", "closed", "triaged"}


class QueueTriageCase(BaseModel):
    workflow_id: str
    patient_id: str | None = None
    trigger_text: str
    queue_state: str = "unknown"
    priority_score: int = 0
    evidence_snippets: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)


class QueueTriageEvaluation(BaseModel):
    workflow_id: str
    disposition: str
    risk_label: str
    review_required: bool
    queue_recommendation: str
    rationale: list[str]
    recommended_actions: list[str]


class QueueTriageFamily:
    family = WorkflowFamily.queue_triage

    def supports(self, workflow: WorkflowDefinition) -> bool:
        return workflow.family == self.family

    def normalize_case(self, workflow: WorkflowDefinition, payload: dict[str, Any]) -> QueueTriageCase:
        if not self.supports(workflow):
            raise ValueError(f"workflow {workflow.id} is not part of queue_triage")

        trigger_text = (
            payload.get("trigger_text")
            or payload.get("referral_text")
            or payload.get("discharge_summary")
            or payload.get("queue_text")
            or payload.get("note_text")
            or ""
        ).strip()
        queue_context = payload.get("queue_context") if isinstance(payload.get("queue_context"), dict) else {}
        completion_state = str(
            payload.get("completion_state")
            or queue_context.get("completion_state")
            or payload.get("queue_state")
            or payload.get("status")
            or "unknown"
        ).lower()
        terms = [term.lower() for term in workflow.family_config.get("priority_terms", DEFAULT_PRIORITY_TERMS)]
        snippets = [line.strip() for line in trigger_text.splitlines() if line.strip()]
        matched_terms = sorted({term for term in terms if term in trigger_text.lower()})
        priority_score = int(payload.get("priority_score") or queue_context.get("priority_score") or 0)
        return QueueTriageCase(
            workflow_id=workflow.id,
            patient_id=payload.get("patient_id") or queue_context.get("patient_id"),
            trigger_text=trigger_text,
            queue_state=completion_state,
            priority_score=priority_score,
            evidence_snippets=snippets[:3],
            matched_terms=matched_terms,
        )

    def evaluate(self, workflow: WorkflowDefinition, payload: dict[str, Any]) -> QueueTriageEvaluation:
        case = self.normalize_case(workflow, payload)
        resolved_states = {
            state.lower()
            for state in workflow.family_config.get("resolved_states", sorted(DEFAULT_RESOLVED_STATES))
        }
        urgent_terms = {
            term.lower()
            for term in workflow.family_config.get("urgent_terms", DEFAULT_URGENT_TERMS)
        }

        rationale: list[str] = []
        if case.queue_state in resolved_states:
            rationale.append(f"Queue state is already '{case.queue_state}'.")
            disposition = "already_prioritized"
            risk_label = "watch"
            queue_recommendation = "Keep the current queue placement and monitor for change."
        else:
            urgency_hit = any(term in case.trigger_text.lower() for term in urgent_terms)
            score_hit = case.priority_score >= 85
            elevated_hit = case.priority_score >= 60 or bool(case.matched_terms)

            if urgency_hit or score_hit:
                rationale.append("High-risk escalation language or a high priority score was detected.")
                disposition = "escalate_immediately"
                risk_label = "urgent"
                queue_recommendation = "Move the case to the urgent triage lane."
            elif elevated_hit:
                rationale.append(
                    "Priority language was detected: " + ", ".join(case.matched_terms[:4]) + "."
                    if case.matched_terms
                    else "The case has a moderately elevated priority score."
                )
                disposition = "reprioritize_queue"
                risk_label = "alert"
                queue_recommendation = "Advance the case ahead of routine items."
            else:
                rationale.append("The case is still open but does not show a strong escalation signal.")
                disposition = "needs_review"
                risk_label = "watch"
                queue_recommendation = "Keep the case under manual review."

        recommended_actions = [
            action.label
            for action in workflow.actions
            if action.kind
            in {
                WorkflowActionKind.create_review_item,
                WorkflowActionKind.queue_reprioritization,
                WorkflowActionKind.draft_schedule,
                WorkflowActionKind.mock_email,
            }
        ]

        return QueueTriageEvaluation(
            workflow_id=workflow.id,
            disposition=disposition,
            risk_label=risk_label,
            review_required=disposition != "already_prioritized",
            queue_recommendation=queue_recommendation,
            rationale=rationale,
            recommended_actions=recommended_actions[:3],
        )
