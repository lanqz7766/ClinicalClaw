from __future__ import annotations

from datetime import UTC, datetime, timedelta
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


class CaseStatus(str, Enum):
    intake = "intake"
    active = "active"
    in_review = "in_review"
    closed = "closed"


class AccessAction(str, Enum):
    read = "read"
    write = "write"
    export = "export"
    launch = "launch"
    query = "query"
    review = "review"
    file = "file"


class AccessOutcome(str, Enum):
    pending = "pending"
    success = "success"
    denied = "denied"
    failed = "failed"


class MemoryOutcome(str, Enum):
    success = "success"
    failure = "failure"


class DataClassification(str, Enum):
    phi = "phi"
    deidentified = "deidentified"
    metadata_only = "metadata_only"
    internal = "internal"


class ConnectorAccessLevel(str, Enum):
    none = "none"
    read = "read"
    write = "write"


class TargetStandard(str, Enum):
    fhir = "FHIR"
    dicom = "DICOM"
    internal = "INTERNAL"


class ArtifactStatus(str, Enum):
    draft = "draft"
    in_review = "in_review"
    approved = "approved"
    exported = "exported"


class StandardMapping(BaseModel):
    standard: TargetStandard
    resource_type: str
    notes: str = ""


class ScenarioInput(BaseModel):
    name: str
    source: str
    description: str
    required: bool = True
    classification: DataClassification = DataClassification.internal
    example: str | None = None


class ScenarioOutput(BaseModel):
    name: str
    kind: str
    description: str
    format: str
    review_required: bool = True
    target_mappings: list[StandardMapping] = Field(default_factory=list)


class ReviewSpec(BaseModel):
    required: bool = True
    reviewer_role: str
    approve_transition: TaskRunStatus = TaskRunStatus.approved
    reject_transition: TaskRunStatus = TaskRunStatus.rejected
    notes: str = ""


class FailurePolicy(BaseModel):
    code: str
    condition: str
    action: str


class ConnectorPolicy(BaseModel):
    ehr: ConnectorAccessLevel = ConnectorAccessLevel.none
    imaging: ConnectorAccessLevel = ConnectorAccessLevel.none
    write_back: ConnectorAccessLevel = ConnectorAccessLevel.none


class ExternalReference(BaseModel):
    system: str
    resource_type: str
    resource_id: str
    display: str | None = None


class ToolPolicy(BaseModel):
    allowed_tools: list[str] = Field(default_factory=list)
    blocked_tools: list[str] = Field(default_factory=list)
    write_back: bool = False
    phi_access: bool = False
    requires_human_review: bool = True
    max_iterations: int = 12
    connectors: ConnectorPolicy = Field(default_factory=ConnectorPolicy)


class ScenarioSpec(BaseModel):
    id: str
    version: str = "1.0"
    name: str
    summary: str
    clinical_goal: str
    intent_type: str
    inputs: list[ScenarioInput] = Field(default_factory=list)
    outputs: list[ScenarioOutput] = Field(default_factory=list)
    review: ReviewSpec
    failure_policies: list[FailurePolicy] = Field(default_factory=list)
    policy: ToolPolicy


class CaseRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"case_{uuid4().hex[:12]}")
    status: CaseStatus = CaseStatus.intake
    external_patient_id: str | None = None
    encounter_id: str | None = None
    scenario_ids: list[str] = Field(default_factory=list)
    external_references: list[ExternalReference] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"artifact_{uuid4().hex[:12]}")
    case_id: str | None = None
    task_run_id: str | None = None
    artifact_type: ArtifactType
    title: str
    path: str
    status: ArtifactStatus = ArtifactStatus.draft
    mime_type: str = "application/json"
    target_mappings: list[StandardMapping] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AccessEventRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"access_{uuid4().hex[:12]}")
    case_id: str | None = None
    task_run_id: str | None = None
    system: str
    action: AccessAction
    resource_type: str
    resource_id: str | None = None
    outcome: AccessOutcome = AccessOutcome.pending
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
    review_required: bool = True
    input_references: list[ExternalReference] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    access_event_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateTaskRunRequest(BaseModel):
    scenario_id: str
    requested_by: str
    case_id: str | None = None
    external_patient_id: str | None = None
    note: str | None = None


class RunMemoryRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"memory_{uuid4().hex[:12]}")
    scenario_id: str
    task_run_id: str | None = None
    outcome: MemoryOutcome
    summary: str
    guidance: str
    content: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SmartLaunchSessionRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"launch_{uuid4().hex[:12]}")
    iss: str
    state: str
    authorize_url: str
    client_id: str
    redirect_uri: str
    scope: str
    launch: str | None = None
    patient_id: str | None = None
    encounter_id: str | None = None
    code_verifier: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SmartTokenStateRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"token_{uuid4().hex[:12]}")
    session_id: str | None = None
    iss: str
    token_type: str = "Bearer"
    access_token: str
    refresh_token: str | None = None
    scope: str = ""
    expires_in: int | None = None
    patient_id: str | None = None
    encounter_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def expires_at(self) -> datetime | None:
        if self.expires_in is None:
            return None
        return self.created_at + timedelta(seconds=self.expires_in)

    def is_expired(self, skew_seconds: int = 60) -> bool:
        expires_at = self.expires_at()
        if expires_at is None:
            return False
        return utc_now() >= (expires_at - timedelta(seconds=skew_seconds))
