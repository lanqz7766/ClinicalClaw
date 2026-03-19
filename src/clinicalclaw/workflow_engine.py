from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

try:
    import yaml
except ImportError:  # pragma: no cover - dependency is declared for runtime use
    yaml = None


class WorkflowFamily(str, Enum):
    findings_closure = "findings_closure"
    screening_gap_closure = "screening_gap_closure"
    missed_diagnosis_detection = "missed_diagnosis_detection"
    queue_triage = "queue_triage"
    registry_abstraction = "registry_abstraction"
    prior_auth_prep = "prior_auth_prep"
    trial_matching = "trial_matching"
    documentation_reconciliation = "documentation_reconciliation"


class WorkflowStatus(str, Enum):
    design_ready = "design_ready"
    prototype_ready = "prototype_ready"
    live_validation_pending = "live_validation_pending"


class WorkflowActionKind(str, Enum):
    create_review_item = "create_review_item"
    draft_followup_plan = "draft_followup_plan"
    draft_order = "draft_order"
    draft_schedule = "draft_schedule"
    mock_email = "mock_email"
    queue_reprioritization = "queue_reprioritization"
    chart_summary = "chart_summary"


class WorkflowInputSpec(BaseModel):
    name: str
    source: str
    description: str
    required: bool = True


class WorkflowRuleSetSpec(BaseModel):
    id: str
    summary: str
    references: list[str] = Field(default_factory=list)


class WorkflowActionSpec(BaseModel):
    id: str
    label: str
    kind: WorkflowActionKind
    description: str
    reviewer_required: bool = True


class WorkflowPresentationSpec(BaseModel):
    skill: str
    sections: list[str] = Field(default_factory=list)
    tone: str = "concise_clinical"


class WorkflowTestSpec(BaseModel):
    mode: str = "mock"
    sample_payload: dict[str, Any] = Field(default_factory=dict)


class WorkflowDefinition(BaseModel):
    id: str
    version: str = "1.0"
    title: str
    family: WorkflowFamily
    specialties: list[str] = Field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.design_ready
    summary: str
    problem_statement: str
    live_test_ready: bool = False
    inputs: list[WorkflowInputSpec] = Field(default_factory=list)
    trigger_signals: list[str] = Field(default_factory=list)
    evidence_sources: list[str] = Field(default_factory=list)
    rule_sets: list[WorkflowRuleSetSpec] = Field(default_factory=list)
    actions: list[WorkflowActionSpec] = Field(default_factory=list)
    presentation: WorkflowPresentationSpec
    examples: list[str] = Field(default_factory=list)
    family_config: dict[str, Any] = Field(default_factory=dict)


class WorkflowFamilySummary(BaseModel):
    family: WorkflowFamily
    workflow_ids: list[str]
    specialties: list[str]


def load_workflows(directory: str | Path) -> list[WorkflowDefinition]:
    workflow_dir = Path(directory)
    if not workflow_dir.exists():
        return []

    workflows: list[WorkflowDefinition] = []
    required_keys = {"id", "title", "family", "summary", "problem_statement", "presentation"}
    candidate_paths = sorted(workflow_dir.rglob("*.json"))
    if yaml is not None:
        candidate_paths += sorted(workflow_dir.rglob("*.yaml"))
        candidate_paths += sorted(workflow_dir.rglob("*.yml"))

    for path in candidate_paths:
        if path.suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
        else:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not required_keys.issubset(payload.keys()):
            continue
        workflows.append(WorkflowDefinition.model_validate(payload))
    return workflows


def load_workflow_map(directory: str | Path) -> dict[str, WorkflowDefinition]:
    return {workflow.id: workflow for workflow in load_workflows(directory)}


class WorkflowEngine:
    def __init__(self, workflows: list[WorkflowDefinition]):
        self.workflows = workflows
        self.workflow_map = {workflow.id: workflow for workflow in workflows}

    def list_families(self) -> list[WorkflowFamilySummary]:
        families: dict[WorkflowFamily, list[WorkflowDefinition]] = {}
        for workflow in self.workflows:
            families.setdefault(workflow.family, []).append(workflow)

        summaries: list[WorkflowFamilySummary] = []
        for family, family_workflows in sorted(families.items(), key=lambda item: item[0].value):
            specialties = sorted({tag for workflow in family_workflows for tag in workflow.specialties})
            summaries.append(
                WorkflowFamilySummary(
                    family=family,
                    workflow_ids=[workflow.id for workflow in family_workflows],
                    specialties=specialties,
                )
            )
        return summaries

    def list_workflows(self, family: WorkflowFamily | None = None) -> list[WorkflowDefinition]:
        if family is None:
            return list(self.workflows)
        return [workflow for workflow in self.workflows if workflow.family == family]

    def get_workflow(self, workflow_id: str) -> WorkflowDefinition | None:
        return self.workflow_map.get(workflow_id)


def build_workflow_engine(directory: str | Path = "workflows") -> WorkflowEngine:
    return WorkflowEngine(load_workflows(directory))
