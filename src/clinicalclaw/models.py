from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class TaskRunStatus(str, Enum):
    draft = "draft"
    queued = "queued"
    running = "running"
    in_review = "in_review"
    approved = "approved"
    filed = "filed"
    rejected = "rejected"
    failed = "failed"


class ArtifactType(str, Enum):
    report = "report"
    image = "image"
    dicom = "dicom"
    json = "json"
    pdf = "pdf"
    html = "html"


class AccessAction(str, Enum):
    read = "read"
    write = "write"
    export = "export"
    launch = "launch"
    query = "query"


class ToolPolicy(BaseModel):
    allowed_tools: list[str] = Field(default_factory=list)
    blocked_tools: list[str] = Field(default_factory=list)
    write_back: bool = False
    phi_access: bool = False
    requires_human_review: bool = True


class ScenarioSpec(BaseModel):
    id: str
    name: str
    summary: str
    clinical_goal: str
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    review_gate: str
    policy: ToolPolicy


class CaseRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"case_{uuid4().hex[:12]}")
    external_patient_id: str | None = None
    encounter_id: str | None = None
    scenario_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"artifact_{uuid4().hex[:12]}")
    case_id: str | None = None
    task_run_id: str | None = None
    artifact_type: ArtifactType
    title: str
    path: str
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AccessEventRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"access_{uuid4().hex[:12]}")
    case_id: str | None = None
    task_run_id: str | None = None
    system: str
    action: AccessAction
    outcome: str = "pending"
    actor: str = "platform"
    created_at: datetime = Field(default_factory=utc_now)
    details: dict[str, Any] = Field(default_factory=dict)


class TaskRunRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"task_{uuid4().hex[:12]}")
    case_id: str | None = None
    scenario_id: str
    requested_by: str
    status: TaskRunStatus = TaskRunStatus.draft
    note: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    policy_snapshot: ToolPolicy
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateTaskRunRequest(BaseModel):
    scenario_id: str
    requested_by: str
    case_id: str | None = None
    external_patient_id: str | None = None
    note: str | None = None

