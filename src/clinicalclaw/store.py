from __future__ import annotations

from clinicalclaw.models import (
    AccessAction,
    AccessOutcome,
    AccessEventRecord,
    ArtifactRecord,
    ArtifactStatus,
    ArtifactType,
    CaseRecord,
    CreateTaskRunRequest,
    ScenarioSpec,
    TaskRunRecord,
)


class MemoryStore:
    def __init__(self) -> None:
        self.cases: dict[str, CaseRecord] = {}
        self.tasks: dict[str, TaskRunRecord] = {}
        self.artifacts: dict[str, ArtifactRecord] = {}
        self.access_events: dict[str, AccessEventRecord] = {}

    def bootstrap_demo_data(self, scenarios: list[ScenarioSpec]) -> None:
        if self.cases:
            return

        demo_case = CaseRecord(
            external_patient_id="demo-patient-001",
            encounter_id="encounter-demo-001",
            scenario_ids=[scenario.id for scenario in scenarios],
            metadata={"source": "week-1-shell"},
        )
        self.cases[demo_case.id] = demo_case

        if scenarios:
            first = scenarios[0]
            demo_task = TaskRunRecord(
                case_id=demo_case.id,
                scenario_id=first.id,
                requested_by="system-bootstrap",
                status="in_review",
                note="Demo task for platform shell",
                policy_snapshot=first.policy,
                review_required=first.review.required,
                metadata={"demo": True},
            )
            self.tasks[demo_task.id] = demo_task

        demo_artifact = ArtifactRecord(
            case_id=demo_case.id,
            artifact_type=ArtifactType.json,
            title="Shell platform manifest",
            path=".clinicalclaw/artifacts/demo_manifest.json",
            status=ArtifactStatus.in_review,
            metadata={"status": "placeholder"},
        )
        self.artifacts[demo_artifact.id] = demo_artifact

        demo_access = AccessEventRecord(
            case_id=demo_case.id,
            system="shell-platform",
            action=AccessAction.launch,
            resource_type="PlatformSession",
            resource_id="bootstrap",
            outcome=AccessOutcome.success,
            details={"note": "Week 1 bootstrap event"},
        )
        self.access_events[demo_access.id] = demo_access

    def create_case_if_needed(self, request: CreateTaskRunRequest, scenarios: dict[str, ScenarioSpec]) -> str:
        if request.case_id:
            return request.case_id

        scenario = scenarios[request.scenario_id]
        case_record = CaseRecord(
            external_patient_id=request.external_patient_id,
            scenario_ids=[scenario.id],
            metadata={"created_from": "task_request"},
        )
        self.cases[case_record.id] = case_record
        return case_record.id

    def create_task(self, request: CreateTaskRunRequest, scenarios: dict[str, ScenarioSpec]) -> TaskRunRecord:
        case_id = self.create_case_if_needed(request, scenarios)
        scenario = scenarios[request.scenario_id]
        task = TaskRunRecord(
            case_id=case_id,
            scenario_id=scenario.id,
            requested_by=request.requested_by,
            note=request.note,
            policy_snapshot=scenario.policy,
            review_required=scenario.review.required,
            metadata={"scenario_name": scenario.name},
        )
        self.tasks[task.id] = task
        return task
