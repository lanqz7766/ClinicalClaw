from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from clinicalclaw.config import ClinicalClawSettings, load_settings
from clinicalclaw.connectors import ConnectorBundle, build_connector_bundle
from clinicalclaw.connectors.base import (
    PatientChartBundle,
    SmartEndpoints,
    SmartLaunchRequest,
    SmartLaunchSession,
)
from clinicalclaw.models import (
    AccessAction,
    AccessEventRecord,
    AccessOutcome,
    ArtifactRecord,
    ArtifactStatus,
    ArtifactType,
    CreateTaskRunRequest,
    MemoryOutcome,
    RunMemoryRecord,
    ScenarioOutput,
    ScenarioSpec,
    SmartLaunchSessionRecord,
    SmartTokenStateRecord,
    TaskRunRecord,
    TaskRunStatus,
)
from clinicalclaw.runtime import build_agent_for_scenario
from clinicalclaw.scenarios import load_scenario_map
from clinicalclaw.store import MemoryStore, SQLiteStore


@dataclass
class ScenarioExecutionResult:
    scenario: ScenarioSpec
    task_run_id: str
    review_required: bool
    artifact_ids: list[str]
    access_event_ids: list[str]
    result: Any


class ClinicalClawService:
    SMART_LIVE_LAUNCH_MEMORY_ID = "smart_live_launch_validation"
    SMART_LIVE_READ_MEMORY_ID = "smart_live_read_validation"
    SMART_LIVE_TOKEN_MEMORY_ID = "smart_live_token_validation"

    def __init__(
        self,
        settings: ClinicalClawSettings | None = None,
        store: MemoryStore | None = None,
        scenario_map: dict[str, ScenarioSpec] | None = None,
        connectors: ConnectorBundle | None = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.scenario_map = scenario_map or load_scenario_map(self.settings.scenario_dir)
        self.store = store or SQLiteStore(self.settings.database_path)
        self.connectors = connectors or build_connector_bundle(self.settings)
        self.store.bootstrap_demo_data(list(self.scenario_map.values()))
        self._restore_latest_smart_token()

    def get_scenario(self, scenario_id: str | None) -> ScenarioSpec | None:
        if not scenario_id:
            return None
        return self.scenario_map.get(scenario_id)

    def build_prompt(
        self,
        task: str,
        scenario: ScenarioSpec,
        connector_context: str = "",
        memory_context: str = "",
    ) -> str:
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
            f"{connector_context}"
            f"{memory_context}"
            "Task request:\n"
            f"{task}\n\n"
            "Constraints:\n"
            "- Do not assume missing patient or study context.\n"
            "- Do not claim write-back completed.\n"
            "- Return a review-ready result with missing-data flags when needed."
        )

    def build_memory_context(self, scenario_id: str) -> str:
        memories = self.store.list_run_memories(scenario_id, limit=self.settings.memory_history_limit)
        if not memories:
            return ""
        lines = ["Relevant prior run memory:"]
        for memory in memories:
            lines.append(
                f"- [{memory.outcome.value}] {memory.summary} Guidance: {memory.guidance}"
            )
        return "\n".join(lines) + "\n\n"

    def build_integration_memory_context(self, scenario: ScenarioSpec) -> str:
        sections: list[str] = []
        if scenario.policy.connectors.ehr.value == "read":
            memories = self.store.list_run_memories(
                self.SMART_LIVE_READ_MEMORY_ID,
                limit=self.settings.memory_history_limit,
            )
            if memories:
                sections.append("Relevant SMART live integration memory:")
                for memory in memories:
                    sections.append(
                        f"- [{memory.outcome.value}] {memory.summary} Guidance: {memory.guidance}"
                    )
        if not sections:
            return ""
        return "\n".join(sections) + "\n\n"

    def _restore_latest_smart_token(self) -> None:
        if self.settings.ehr_connector_mode == "mock":
            return

        configured_iss = self.settings.fhir_base_url.rstrip("/")
        for token_state in self.store.list_smart_token_states(limit=20):
            if configured_iss and token_state.iss.rstrip("/") != configured_iss:
                continue
            self.connectors.ehr.access_token = token_state.access_token
            return

    async def collect_connector_context(
        self,
        *,
        task_run_id: str,
        scenario: ScenarioSpec,
        requested_by: str,
        external_patient_id: str | None,
    ) -> str:
        sections: list[str] = []

        if scenario.policy.connectors.ehr.value == "read" and external_patient_id:
            await self.ensure_active_smart_token()
            chart = await self.connectors.ehr.fetch_patient_chart(patient_id=external_patient_id)
            self.store.add_access_event(
                AccessEventRecord(
                    task_run_id=task_run_id,
                    system=self.connectors.ehr.connector_name,
                    action=AccessAction.read,
                    resource_type="PatientChartBundle",
                    resource_id=external_patient_id,
                    outcome=AccessOutcome.success,
                    actor=requested_by,
                    details={"mode": self.connectors.ehr.mode.value},
                )
            )
            sections.append(self._format_chart_context(chart))

        if scenario.policy.connectors.imaging.value == "read" and external_patient_id:
            studies = await self.connectors.imaging.search_studies(patient_id=external_patient_id)
            self.store.add_access_event(
                AccessEventRecord(
                    task_run_id=task_run_id,
                    system=self.connectors.imaging.connector_name,
                    action=AccessAction.query,
                    resource_type="ImagingStudy",
                    resource_id=external_patient_id,
                    outcome=AccessOutcome.success,
                    actor=requested_by,
                    details={"study_count": len(studies), "mode": self.connectors.imaging.mode.value},
                )
            )
            sections.append(self._format_imaging_context(studies))

        if not sections:
            return ""
        return "Connector context:\n" + "\n\n".join(sections) + "\n\n"

    def _format_chart_context(self, chart: PatientChartBundle) -> str:
        return (
            "FHIR chart summary:\n"
            f"- patient: {chart.patient.display_name} ({chart.patient.patient_id})\n"
            f"- encounter: {chart.encounter.encounter_id if chart.encounter else 'none'}\n"
            f"- problems: {', '.join(chart.problems) or 'none'}\n"
            f"- medications: {', '.join(chart.medications) or 'none'}\n"
            f"- observations: {', '.join(chart.observations) or 'none'}\n"
            f"- diagnostic reports: {', '.join(ref.resource_id for ref in chart.diagnostic_reports) or 'none'}\n"
            f"- imaging studies: {', '.join(ref.resource_id for ref in chart.imaging_studies) or 'none'}"
        )

    def _format_imaging_context(self, studies: list[Any]) -> str:
        if not studies:
            return "Imaging summary:\n- no studies returned"
        lines = ["Imaging summary:"]
        for study in studies[:5]:
            lines.append(
                f"- {study.study_instance_uid} | {study.modality} | {study.description} | series={study.series_count}"
            )
        return "\n".join(lines)

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

    def _record_memory(
        self,
        *,
        scenario_id: str,
        task_run_id: str,
        outcome: MemoryOutcome,
        summary: str,
        guidance: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.store.add_run_memory(
            RunMemoryRecord(
                scenario_id=scenario_id,
                task_run_id=task_run_id,
                outcome=outcome,
                summary=summary,
                guidance=guidance,
                content=content,
                metadata=metadata or {},
            )
        )

    def _record_run_memory(
        self,
        *,
        scenario: ScenarioSpec,
        task_run_id: str,
        outcome: MemoryOutcome,
        summary: str,
        guidance: str,
        content: str,
    ) -> None:
        self._record_memory(
            scenario_id=scenario.id,
            task_run_id=task_run_id,
            outcome=outcome,
            summary=summary,
            guidance=guidance,
            content=content,
            metadata={"scenario_name": scenario.name},
        )

    def _record_smart_launch_memory(
        self,
        *,
        outcome: MemoryOutcome,
        summary: str,
        guidance: str,
        content: str,
        session_id: str,
        iss: str,
        patient_id: str | None = None,
        encounter_id: str | None = None,
    ) -> None:
        self._record_memory(
            scenario_id=self.SMART_LIVE_LAUNCH_MEMORY_ID,
            task_run_id=session_id,
            outcome=outcome,
            summary=summary,
            guidance=guidance,
            content=content,
            metadata={
                "integration": "smart",
                "phase": "launch",
                "iss": iss,
                "patient_id": patient_id or "",
                "encounter_id": encounter_id or "",
            },
        )

    def _record_smart_read_memory(
        self,
        *,
        outcome: MemoryOutcome,
        summary: str,
        guidance: str,
        content: str,
        patient_id: str,
        encounter_id: str | None = None,
        iss: str | None = None,
    ) -> None:
        self._record_memory(
            scenario_id=self.SMART_LIVE_READ_MEMORY_ID,
            task_run_id=patient_id,
            outcome=outcome,
            summary=summary,
            guidance=guidance,
            content=content,
            metadata={
                "integration": "smart",
                "phase": "read",
                "iss": iss or "",
                "patient_id": patient_id,
                "encounter_id": encounter_id or "",
            },
        )

    def _record_smart_token_memory(
        self,
        *,
        outcome: MemoryOutcome,
        summary: str,
        guidance: str,
        content: str,
        iss: str,
        source_token_id: str,
        refreshed_token_id: str | None = None,
    ) -> None:
        self._record_memory(
            scenario_id=self.SMART_LIVE_TOKEN_MEMORY_ID,
            task_run_id=source_token_id,
            outcome=outcome,
            summary=summary,
            guidance=guidance,
            content=content,
            metadata={
                "integration": "smart",
                "phase": "token",
                "iss": iss,
                "source_token_id": source_token_id,
                "refreshed_token_id": refreshed_token_id or "",
            },
        )

    def get_latest_smart_token_state(self, *, iss: str | None = None) -> SmartTokenStateRecord | None:
        for token_state in self.store.list_smart_token_states(limit=20):
            if iss and token_state.iss.rstrip("/") != iss.rstrip("/"):
                continue
            return token_state
        return None

    async def ensure_active_smart_token(
        self,
        *,
        iss: str | None = None,
        skew_seconds: int = 60,
    ) -> SmartTokenStateRecord | None:
        resolved_iss = (iss or self.settings.fhir_base_url).rstrip("/")
        token_state = self.get_latest_smart_token_state(iss=resolved_iss or None)
        if not token_state:
            return None

        self.connectors.ehr.access_token = token_state.access_token
        if not token_state.is_expired(skew_seconds=skew_seconds):
            return token_state

        if not token_state.refresh_token:
            self._record_smart_token_memory(
                outcome=MemoryOutcome.failure,
                summary="SMART token expired and no refresh token was available.",
                guidance=(
                    "Request offline access or run a fresh SMART launch before attempting connector reads "
                    "after expiry."
                ),
                content=f"token_id={token_state.id}; iss={token_state.iss}",
                iss=token_state.iss,
                source_token_id=token_state.id,
            )
            raise ValueError("SMART token expired and no refresh token is available")

        try:
            refreshed = await self.connectors.ehr.refresh_access_token(
                refresh_token=token_state.refresh_token,
                scope=token_state.scope,
                iss=token_state.iss,
            )
            refreshed_record = self.store.save_smart_token_state(
                SmartTokenStateRecord(
                    session_id=token_state.session_id,
                    iss=token_state.iss,
                    token_type=refreshed.token_type,
                    access_token=refreshed.access_token,
                    refresh_token=refreshed.refresh_token,
                    scope=refreshed.scope,
                    expires_in=refreshed.expires_in,
                    patient_id=refreshed.patient_id or token_state.patient_id,
                    encounter_id=refreshed.encounter_id or token_state.encounter_id,
                    metadata={
                        "mode": refreshed.metadata.get("mode", ""),
                        "refreshed_from": token_state.id,
                    },
                )
            )
            self.connectors.ehr.access_token = refreshed_record.access_token
            self._record_smart_token_memory(
                outcome=MemoryOutcome.success,
                summary=f"SMART token refresh succeeded for issuer {token_state.iss}.",
                guidance=(
                    "Reuse the latest refreshed token state for sandbox reads and keep monitoring expiry before "
                    "long-running scenario execution."
                ),
                content=f"source_token_id={token_state.id}; refreshed_token_id={refreshed_record.id}",
                iss=token_state.iss,
                source_token_id=token_state.id,
                refreshed_token_id=refreshed_record.id,
            )
            return refreshed_record
        except Exception as exc:
            self._record_smart_token_memory(
                outcome=MemoryOutcome.failure,
                summary=f"SMART token refresh failed: {type(exc).__name__}",
                guidance=(
                    "Fall back to a fresh SMART launch if refresh fails or the sandbox does not issue refresh "
                    "tokens for the current scope."
                ),
                content=str(exc)[:1500],
                iss=token_state.iss,
                source_token_id=token_state.id,
            )
            raise

    async def validate_smart_read(
        self,
        *,
        patient_id: str,
        encounter_id: str | None = None,
        iss: str | None = None,
    ) -> PatientChartBundle:
        try:
            await self.ensure_active_smart_token(iss=iss, skew_seconds=60)
            chart = await self.connectors.ehr.fetch_patient_chart(
                patient_id=patient_id,
                encounter_id=encounter_id,
            )
            self._record_smart_read_memory(
                outcome=MemoryOutcome.success,
                summary=(
                    "SMART live read succeeded for "
                    f"patient {patient_id} with {len(chart.diagnostic_reports)} diagnostic reports "
                    f"and {len(chart.imaging_studies)} imaging studies."
                ),
                guidance=(
                    "Reuse validated SMART issuer and scopes. If a sandbox patient later returns 410 or no longer "
                    "has expected resources, switch to a currently active patient ID before retrying."
                ),
                content=(
                    f"patient={chart.patient.display_name}; "
                    f"encounter={chart.encounter.encounter_id if chart.encounter else 'none'}; "
                    f"diagnostic_reports={len(chart.diagnostic_reports)}; "
                    f"imaging_studies={len(chart.imaging_studies)}"
                ),
                patient_id=patient_id,
                encounter_id=encounter_id or (chart.encounter.encounter_id if chart.encounter else None),
                iss=iss or self.settings.fhir_base_url,
            )
            return chart
        except Exception as exc:
            self._record_smart_read_memory(
                outcome=MemoryOutcome.failure,
                summary=f"SMART live read failed: {type(exc).__name__}",
                guidance=(
                    "Check that the sandbox patient is still active, that SMART scopes cover the requested read path, "
                    "and that the selected issuer still serves the target resources."
                ),
                content=str(exc)[:1500],
                patient_id=patient_id,
                encounter_id=encounter_id,
                iss=iss or self.settings.fhir_base_url,
            )
            raise

    def list_review_queue(self, limit: int = 20) -> list[TaskRunRecord]:
        return self.store.list_tasks_by_status(TaskRunStatus.in_review, limit=limit)

    def transition_task(
        self,
        *,
        task_id: str,
        target_status: TaskRunStatus,
        actor: str,
        note: str | None = None,
    ) -> TaskRunRecord:
        task = self.store.get_task(task_id)
        if not task:
            raise ValueError(f"Unknown task: {task_id}")

        allowed = {
            TaskRunStatus.draft: {TaskRunStatus.queued},
            TaskRunStatus.queued: {TaskRunStatus.running, TaskRunStatus.failed},
            TaskRunStatus.running: {TaskRunStatus.in_review, TaskRunStatus.approved, TaskRunStatus.failed},
            TaskRunStatus.in_review: {TaskRunStatus.approved, TaskRunStatus.rejected},
            TaskRunStatus.approved: {TaskRunStatus.filed},
            TaskRunStatus.rejected: set(),
            TaskRunStatus.filed: set(),
            TaskRunStatus.failed: set(),
        }
        if target_status not in allowed[task.status]:
            raise ValueError(f"Invalid task transition: {task.status.value} -> {target_status.value}")

        from_status = task.status.value
        updated = self.store.update_task_status(task_id, target_status.value, note=note)
        action = AccessAction.review if target_status in {TaskRunStatus.in_review, TaskRunStatus.approved, TaskRunStatus.rejected} else AccessAction.file
        self.store.add_access_event(
            AccessEventRecord(
                task_run_id=task_id,
                system="clinicalclaw",
                action=action,
                resource_type="TaskRun",
                resource_id=task_id,
                outcome=AccessOutcome.success,
                actor=actor,
                details={
                    "from_status": from_status,
                    "to_status": target_status.value,
                    "note": note or "",
                },
            )
        )
        return updated

    def approve_task(self, task_id: str, actor: str, note: str | None = None) -> TaskRunRecord:
        return self.transition_task(
            task_id=task_id,
            target_status=TaskRunStatus.approved,
            actor=actor,
            note=note,
        )

    def reject_task(self, task_id: str, actor: str, note: str | None = None) -> TaskRunRecord:
        return self.transition_task(
            task_id=task_id,
            target_status=TaskRunStatus.rejected,
            actor=actor,
            note=note,
        )

    def file_task(self, task_id: str, actor: str, note: str | None = None) -> TaskRunRecord:
        return self.transition_task(
            task_id=task_id,
            target_status=TaskRunStatus.filed,
            actor=actor,
            note=note,
        )

    async def begin_smart_launch(
        self,
        *,
        iss: str,
        launch: str | None = None,
        patient_id: str | None = None,
        encounter_id: str | None = None,
        state: str | None = None,
    ) -> SmartLaunchSessionRecord:
        session = await self.connectors.ehr.begin_sandbox_launch(
            iss=iss,
            launch=launch,
            patient_id=patient_id,
            encounter_id=encounter_id,
            state=state,
        )
        return self.store.save_smart_launch_session(
            SmartLaunchSessionRecord(
                iss=session.request.iss,
                state=session.state,
                authorize_url=session.authorize_url,
                client_id=session.request.client_id,
                redirect_uri=session.request.redirect_uri,
                scope=session.request.scope,
                launch=session.request.launch,
                patient_id=session.request.patient_id,
                encounter_id=session.request.encounter_id,
                code_verifier=session.code_verifier,
                metadata={"mode": session.metadata.get("mode", ""), "endpoints": session.endpoints.metadata},
            )
        )

    async def complete_smart_launch(
        self,
        *,
        session_id: str,
        callback_url: str,
    ) -> tuple[SmartTokenStateRecord, Any]:
        persisted = self.store.get_smart_launch_session(session_id)
        if not persisted:
            raise ValueError(f"Unknown SMART launch session: {session_id}")

        endpoints = await self.connectors.ehr.discover_endpoints(persisted.iss)
        session = SmartLaunchSession(
            request=SmartLaunchRequest(
                iss=persisted.iss,
                client_id=persisted.client_id,
                redirect_uri=persisted.redirect_uri,
                scope=persisted.scope,
                launch=persisted.launch,
                patient_id=persisted.patient_id,
                encounter_id=persisted.encounter_id,
                state=persisted.state,
            ),
            endpoints=endpoints,
            state=persisted.state,
            code_verifier=persisted.code_verifier,
            authorize_url=persisted.authorize_url,
            metadata=persisted.metadata,
        )

        try:
            token_set, launch_context = await self.connectors.ehr.complete_sandbox_launch(
                callback_url=callback_url,
                session=session,
            )
            token_record = self.store.save_smart_token_state(
                SmartTokenStateRecord(
                    session_id=persisted.id,
                    iss=launch_context.iss,
                    token_type=token_set.token_type,
                    access_token=token_set.access_token,
                    refresh_token=token_set.refresh_token,
                    scope=token_set.scope,
                    expires_in=token_set.expires_in,
                    patient_id=token_set.patient_id,
                    encounter_id=token_set.encounter_id,
                    metadata={"mode": token_set.metadata.get("mode", "")},
                )
            )
            self._record_smart_launch_memory(
                outcome=MemoryOutcome.success,
                summary=(
                    f"SMART launch completed for issuer {launch_context.iss} "
                    f"and patient {token_record.patient_id or 'unknown'}."
                ),
                guidance=(
                    "Reuse this issuer/client/redirect combination for future sandbox validation. "
                    "If callback state mismatches or token exchange fails, regenerate a fresh launch session."
                ),
                content=callback_url[:1500],
                session_id=persisted.id,
                iss=launch_context.iss,
                patient_id=token_record.patient_id,
                encounter_id=token_record.encounter_id,
            )
            return token_record, launch_context
        except Exception as exc:
            self._record_smart_launch_memory(
                outcome=MemoryOutcome.failure,
                summary=f"SMART launch failed: {type(exc).__name__}",
                guidance=(
                    "Verify issuer, callback URL, PKCE state, and client redirect configuration before retrying "
                    "the SMART launch flow."
                ),
                content=str(exc)[:1500],
                session_id=persisted.id,
                iss=persisted.iss,
                patient_id=persisted.patient_id,
                encounter_id=persisted.encounter_id,
            )
            raise

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
        connector_context = await self.collect_connector_context(
            task_run_id=task_run.id,
            scenario=scenario,
            requested_by=requested_by,
            external_patient_id=external_patient_id,
        )
        memory_context = (
            self.build_memory_context(scenario.id)
            + self.build_integration_memory_context(scenario)
        )
        prompt = self.build_prompt(
            task,
            scenario,
            connector_context=connector_context,
            memory_context=memory_context,
        )

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
            result_text = result.result if isinstance(result.result, str) else str(result.result)
            self._record_run_memory(
                scenario=scenario,
                task_run_id=task_run.id,
                outcome=MemoryOutcome.success,
                summary=f"Scenario completed with status {result.status}.",
                guidance="Reuse the same connector path and keep outputs review-ready before any filing.",
                content=result_text[:1500],
            )
            return ScenarioExecutionResult(
                scenario=scenario,
                task_run_id=task_run.id,
                review_required=scenario.review.required,
                artifact_ids=artifact_ids,
                access_event_ids=list(self.store.tasks[task_run.id].access_event_ids),
                result=result,
            )
        except Exception as exc:
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
            self._record_run_memory(
                scenario=scenario,
                task_run_id=task_run.id,
                outcome=MemoryOutcome.failure,
                summary=f"Scenario failed: {type(exc).__name__}",
                guidance="Check connector availability, patient context, and scenario constraints before retrying.",
                content=str(exc)[:1500],
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
