from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from clinicalclaw.config import ClinicalClawSettings, load_settings
from clinicalclaw.models import (
    AccessAction,
    AccessEventRecord,
    AccessOutcome,
    ArtifactRecord,
    ArtifactStatus,
    ArtifactType,
    CreateTaskRunRequest,
    ScenarioOutput,
    ScenarioSpec,
)
from clinicalclaw.runtime import build_agent_for_scenario
from clinicalclaw.scenarios import load_scenario_map
from clinicalclaw.store import MemoryStore


@dataclass
class ScenarioExecutionResult:
    scenario: ScenarioSpec
    task_run_id: str
    review_required: bool
    artifact_ids: list[str]
    access_event_ids: list[str]
    result: Any


class ClinicalClawService:
    def __init__(
        self,
        settings: ClinicalClawSettings | None = None,
        store: MemoryStore | None = None,
        scenario_map: dict[str, ScenarioSpec] | None = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.scenario_map = scenario_map or load_scenario_map(self.settings.scenario_dir)
        self.store = store or MemoryStore()
        self.store.bootstrap_demo_data(list(self.scenario_map.values()))

    def get_scenario(self, scenario_id: str | None) -> ScenarioSpec | None:
        if not scenario_id:
            return None
        return self.scenario_map.get(scenario_id)

    def build_prompt(self, task: str, scenario: ScenarioSpec) -> str:
        input_names = ", ".join(item.name for item in scenario.inputs) or "none"
        output_names = ", ".join(item.name for item in scenario.outputs) or "none"
        failure_rules = "\n".join(
            f"- {item.code}: {item.action}" for item in scenario.failure_policies
        ) or "- none"
        connector_summary = (
            f"EHR={scenario.policy.connectors.ehr}, "
            f"Imaging={scenario.policy.connectors.imaging}, "
            f"WriteBack={scenario.policy.connectors.write_back}"
        )

        return (
            f"Scenario: {scenario.name} (id={scenario.id}, version={scenario.version})\n"
            f"Intent: {scenario.intent_type}\n"
            f"Clinical goal: {scenario.clinical_goal}\n"
            f"Inputs in scope: {input_names}\n"
            f"Outputs expected: {output_names}\n"
            f"Connector permissions: {connector_summary}\n"
            f"Review gate: {scenario.review.reviewer_role}; required={scenario.review.required}\n"
            "Failure handling rules:\n"
            f"{failure_rules}\n\n"
            "Task request:\n"
            f"{task}\n\n"
            "Constraints:\n"
            "- Do not assume missing patient or study context.\n"
            "- Do not claim write-back completed.\n"
            "- Return a review-ready result with missing-data flags when needed."
        )

    def _create_task_request(
        self,
        scenario_id: str,
        requested_by: str,
        case_id: str | None,
        external_patient_id: str | None,
        note: str | None,
    ) -> CreateTaskRunRequest:
        return CreateTaskRunRequest(
            scenario_id=scenario_id,
            requested_by=requested_by,
            case_id=case_id,
            external_patient_id=external_patient_id,
            note=note,
        )

    def _record_launch_event(self, task_run_id: str, scenario: ScenarioSpec, requested_by: str) -> None:
        self.store.add_access_event(
            AccessEventRecord(
                task_run_id=task_run_id,
                system="clinicalclaw",
                action=AccessAction.launch,
                resource_type="Scenario",
                resource_id=scenario.id,
                outcome=AccessOutcome.success,
                actor=requested_by,
                details={"intent_type": scenario.intent_type},
            )
        )

    def _record_completion_artifacts(self, task_run_id: str, scenario: ScenarioSpec) -> list[str]:
        artifact_ids: list[str] = []
        for output in scenario.outputs:
            artifact = self.store.add_artifact(self._build_artifact(task_run_id, scenario, output))
            artifact_ids.append(artifact.id)
        return artifact_ids

    def _build_artifact(self, task_run_id: str, scenario: ScenarioSpec, output: ScenarioOutput) -> ArtifactRecord:
        artifact_type = ArtifactType.json
        if output.format == "markdown":
            artifact_type = ArtifactType.report
        elif output.format == "pdf":
            artifact_type = ArtifactType.pdf
        elif output.format == "html":
            artifact_type = ArtifactType.html

        return ArtifactRecord(
            task_run_id=task_run_id,
            artifact_type=artifact_type,
            title=f"{scenario.id}:{output.name}",
            path=f".clinicalclaw/artifacts/{task_run_id}/{output.name}.{output.format}",
            status=ArtifactStatus.in_review if output.review_required else ArtifactStatus.draft,
            mime_type=_infer_mime_type(output.format),
            target_mappings=output.target_mappings,
            metadata={"scenario_id": scenario.id, "output_kind": output.kind},
        )

    async def invoke_scenario(
        self,
        *,
        task: str,
        scenario_id: str,
        llm: Any,
        requested_by: str = "gateway",
        case_id: str | None = None,
        external_patient_id: str | None = None,
        note: str | None = None,
        on_event: Any = None,
    ) -> ScenarioExecutionResult:
        scenario = self.scenario_map[scenario_id]
        request = self._create_task_request(
            scenario_id=scenario_id,
            requested_by=requested_by,
            case_id=case_id,
            external_patient_id=external_patient_id,
            note=note,
        )
        task_run = self.store.create_task(request, self.scenario_map)
        self.store.update_task_status(task_run.id, "queued")
        self._record_launch_event(task_run.id, scenario, requested_by)

        agent = build_agent_for_scenario(self.settings, scenario, model=llm)
        prompt = self.build_prompt(task, scenario)

        try:
            self.store.update_task_status(task_run.id, "running")
            result = await agent.invoke(prompt, on_event=on_event)
            final_status = "in_review" if scenario.review.required else "approved"
            self.store.update_task_status(task_run.id, final_status)
            artifact_ids = self._record_completion_artifacts(task_run.id, scenario)
            self.store.add_access_event(
                AccessEventRecord(
                    task_run_id=task_run.id,
                    system="clinicalclaw",
                    action=AccessAction.export,
                    resource_type="TaskRun",
                    resource_id=task_run.id,
                    outcome=AccessOutcome.success,
                    actor=requested_by,
                    details={
                        "review_required": scenario.review.required,
                        "artifact_count": len(artifact_ids),
                    },
                )
            )
            return ScenarioExecutionResult(
                scenario=scenario,
                task_run_id=task_run.id,
                review_required=scenario.review.required,
                artifact_ids=artifact_ids,
                access_event_ids=list(self.store.tasks[task_run.id].access_event_ids),
                result=result,
            )
        except Exception:
            self.store.update_task_status(task_run.id, "failed")
            self.store.add_access_event(
                AccessEventRecord(
                    task_run_id=task_run.id,
                    system="clinicalclaw",
                    action=AccessAction.export,
                    resource_type="TaskRun",
                    resource_id=task_run.id,
                    outcome=AccessOutcome.failed,
                    actor=requested_by,
                    details={"scenario_id": scenario.id},
                )
            )
            raise


def _infer_mime_type(fmt: str) -> str:
    mapping = {
        "json": "application/json",
        "markdown": "text/markdown",
        "html": "text/html",
        "pdf": "application/pdf",
    }
    return mapping.get(fmt, "application/octet-stream")
