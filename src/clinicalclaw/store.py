from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import UTC, datetime

from clinicalclaw.models import (
    AccessAction,
    AccessOutcome,
    AccessEventRecord,
    ArtifactRecord,
    ArtifactStatus,
    ArtifactType,
    CaseRecord,
    CreateTaskRunRequest,
    RunMemoryRecord,
    ScenarioSpec,
    SmartLaunchSessionRecord,
    SmartTokenStateRecord,
    TaskRunRecord,
    TaskRunStatus,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


class MemoryStore:
    def __init__(self) -> None:
        self.cases: dict[str, CaseRecord] = {}
        self.tasks: dict[str, TaskRunRecord] = {}
        self.artifacts: dict[str, ArtifactRecord] = {}
        self.access_events: dict[str, AccessEventRecord] = {}
        self.run_memories: dict[str, RunMemoryRecord] = {}
        self.smart_launch_sessions: dict[str, SmartLaunchSessionRecord] = {}
        self.smart_token_states: dict[str, SmartTokenStateRecord] = {}

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
                status=TaskRunStatus.in_review,
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

    def update_task_status(self, task_id: str, status: str, note: str | None = None) -> TaskRunRecord:
        task = self.tasks[task_id]
        task.status = TaskRunStatus(status)
        task.updated_at = utc_now()
        if note is not None:
            task.note = note
        self._sync_artifact_statuses(task)
        return task

    def get_task(self, task_id: str) -> TaskRunRecord | None:
        return self.tasks.get(task_id)

    def list_tasks_by_status(self, status: TaskRunStatus, limit: int = 20) -> list[TaskRunRecord]:
        tasks = [task for task in self.tasks.values() if task.status == status]
        tasks.sort(key=lambda item: item.updated_at, reverse=True)
        return tasks[:limit]

    def add_access_event(self, event: AccessEventRecord) -> AccessEventRecord:
        self.access_events[event.id] = event
        if event.task_run_id and event.task_run_id in self.tasks:
            task = self.tasks[event.task_run_id]
            task.access_event_ids.append(event.id)
            task.updated_at = utc_now()
        return event

    def add_artifact(self, artifact: ArtifactRecord) -> ArtifactRecord:
        self.artifacts[artifact.id] = artifact
        if artifact.task_run_id and artifact.task_run_id in self.tasks:
            task = self.tasks[artifact.task_run_id]
            task.artifact_ids.append(artifact.id)
            task.updated_at = utc_now()
            self._sync_artifact_statuses(task)
        return artifact

    def add_run_memory(self, memory: RunMemoryRecord) -> RunMemoryRecord:
        self.run_memories[memory.id] = memory
        return memory

    def list_run_memories(self, scenario_id: str, limit: int = 3) -> list[RunMemoryRecord]:
        memories = [item for item in self.run_memories.values() if item.scenario_id == scenario_id]
        memories.sort(key=lambda item: item.created_at, reverse=True)
        return memories[:limit]

    def save_smart_launch_session(self, session: SmartLaunchSessionRecord) -> SmartLaunchSessionRecord:
        self.smart_launch_sessions[session.id] = session
        return session

    def get_smart_launch_session(self, session_id: str) -> SmartLaunchSessionRecord | None:
        return self.smart_launch_sessions.get(session_id)

    def save_smart_token_state(self, token_state: SmartTokenStateRecord) -> SmartTokenStateRecord:
        self.smart_token_states[token_state.id] = token_state
        return token_state

    def list_smart_token_states(self, limit: int = 10) -> list[SmartTokenStateRecord]:
        token_states = list(self.smart_token_states.values())
        token_states.sort(key=lambda item: item.created_at, reverse=True)
        return token_states[:limit]

    def _sync_artifact_statuses(self, task: TaskRunRecord) -> None:
        target = None
        if task.status == TaskRunStatus.in_review:
            target = ArtifactStatus.in_review
        elif task.status == TaskRunStatus.approved:
            target = ArtifactStatus.approved
        elif task.status == TaskRunStatus.filed:
            target = ArtifactStatus.exported
        elif task.status == TaskRunStatus.rejected:
            target = ArtifactStatus.draft

        if target is None:
            return

        for artifact_id in task.artifact_ids:
            artifact = self.artifacts.get(artifact_id)
            if artifact:
                artifact.status = target


class SQLiteStore(MemoryStore):
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        super().__init__()
        self._init_db()
        self._load_all()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY,
                    task_run_id TEXT,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS access_events (
                    id TEXT PRIMARY KEY,
                    task_run_id TEXT,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS run_memories (
                    id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL,
                    task_run_id TEXT,
                    outcome TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS smart_launch_sessions (
                    id TEXT PRIMARY KEY,
                    iss TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS smart_token_states (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    iss TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                """
            )

    def _load_all(self) -> None:
        with self._connect() as conn:
            self.cases = self._load_table(conn, "cases", CaseRecord)
            self.tasks = self._load_table(conn, "tasks", TaskRunRecord)
            self.artifacts = self._load_table(conn, "artifacts", ArtifactRecord)
            self.access_events = self._load_table(conn, "access_events", AccessEventRecord)
            self.run_memories = self._load_table(conn, "run_memories", RunMemoryRecord)
            self.smart_launch_sessions = self._load_table(conn, "smart_launch_sessions", SmartLaunchSessionRecord)
            self.smart_token_states = self._load_table(conn, "smart_token_states", SmartTokenStateRecord)

    def _load_table(self, conn: sqlite3.Connection, table: str, model_cls):
        rows = conn.execute(f"SELECT payload FROM {table}").fetchall()
        return {
            model_cls.model_validate_json(row["payload"]).id: model_cls.model_validate_json(row["payload"])
            for row in rows
        }

    def _upsert(self, table: str, id_value: str, payload: str, **columns: str | None) -> None:
        with self._connect() as conn:
            fields = ["id", *columns.keys(), "payload"]
            placeholders = ", ".join("?" for _ in fields)
            updates = ", ".join(f"{field}=excluded.{field}" for field in fields[1:])
            values = [id_value, *columns.values(), payload]
            conn.execute(
                f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({placeholders}) "
                f"ON CONFLICT(id) DO UPDATE SET {updates}",
                values,
            )

    def bootstrap_demo_data(self, scenarios: list[ScenarioSpec]) -> None:
        if self.cases:
            return
        super().bootstrap_demo_data(scenarios)
        for case in self.cases.values():
            self._persist_case(case)
        for task in self.tasks.values():
            self._persist_task(task)
        for artifact in self.artifacts.values():
            self._persist_artifact(artifact)
        for event in self.access_events.values():
            self._persist_access_event(event)

    def _persist_case(self, case: CaseRecord) -> None:
        self._upsert("cases", case.id, case.model_dump_json())

    def _persist_task(self, task: TaskRunRecord) -> None:
        self._upsert(
            "tasks",
            task.id,
            task.model_dump_json(),
            scenario_id=task.scenario_id,
            status=task.status.value if hasattr(task.status, "value") else str(task.status),
            updated_at=task.updated_at.isoformat(),
        )

    def _persist_artifact(self, artifact: ArtifactRecord) -> None:
        self._upsert(
            "artifacts",
            artifact.id,
            artifact.model_dump_json(),
            task_run_id=artifact.task_run_id,
        )

    def _persist_access_event(self, event: AccessEventRecord) -> None:
        self._upsert(
            "access_events",
            event.id,
            event.model_dump_json(),
            task_run_id=event.task_run_id,
            created_at=event.created_at.isoformat(),
        )

    def _persist_run_memory(self, memory: RunMemoryRecord) -> None:
        self._upsert(
            "run_memories",
            memory.id,
            memory.model_dump_json(),
            scenario_id=memory.scenario_id,
            task_run_id=memory.task_run_id,
            outcome=memory.outcome.value if hasattr(memory.outcome, "value") else str(memory.outcome),
            created_at=memory.created_at.isoformat(),
        )

    def _persist_smart_launch_session(self, session: SmartLaunchSessionRecord) -> None:
        self._upsert(
            "smart_launch_sessions",
            session.id,
            session.model_dump_json(),
            iss=session.iss,
            state=session.state,
            created_at=session.created_at.isoformat(),
        )

    def _persist_smart_token_state(self, token_state: SmartTokenStateRecord) -> None:
        self._upsert(
            "smart_token_states",
            token_state.id,
            token_state.model_dump_json(),
            session_id=token_state.session_id,
            iss=token_state.iss,
            created_at=token_state.created_at.isoformat(),
        )

    def create_case_if_needed(self, request: CreateTaskRunRequest, scenarios: dict[str, ScenarioSpec]) -> str:
        case_id = super().create_case_if_needed(request, scenarios)
        self._persist_case(self.cases[case_id])
        return case_id

    def create_task(self, request: CreateTaskRunRequest, scenarios: dict[str, ScenarioSpec]) -> TaskRunRecord:
        task = super().create_task(request, scenarios)
        self._persist_task(task)
        return task

    def update_task_status(self, task_id: str, status: str, note: str | None = None) -> TaskRunRecord:
        task = super().update_task_status(task_id, status, note=note)
        self._persist_task(task)
        for artifact_id in task.artifact_ids:
            artifact = self.artifacts.get(artifact_id)
            if artifact:
                self._persist_artifact(artifact)
        return task

    def add_access_event(self, event: AccessEventRecord) -> AccessEventRecord:
        event = super().add_access_event(event)
        self._persist_access_event(event)
        if event.task_run_id and event.task_run_id in self.tasks:
            self._persist_task(self.tasks[event.task_run_id])
        return event

    def add_artifact(self, artifact: ArtifactRecord) -> ArtifactRecord:
        artifact = super().add_artifact(artifact)
        self._persist_artifact(artifact)
        if artifact.task_run_id and artifact.task_run_id in self.tasks:
            self._persist_task(self.tasks[artifact.task_run_id])
        return artifact

    def add_run_memory(self, memory: RunMemoryRecord) -> RunMemoryRecord:
        memory = super().add_run_memory(memory)
        self._persist_run_memory(memory)
        return memory

    def save_smart_launch_session(self, session: SmartLaunchSessionRecord) -> SmartLaunchSessionRecord:
        session = super().save_smart_launch_session(session)
        self._persist_smart_launch_session(session)
        return session

    def save_smart_token_state(self, token_state: SmartTokenStateRecord) -> SmartTokenStateRecord:
        token_state = super().save_smart_token_state(token_state)
        self._persist_smart_token_state(token_state)
        return token_state
