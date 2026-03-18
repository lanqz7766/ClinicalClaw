from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class ConnectorMode(str, Enum):
    mock = "mock"
    sandbox = "sandbox"
    live = "live"


class ConnectorError(RuntimeError):
    pass


@dataclass
class ResourceReference:
    resource_type: str
    resource_id: str
    display: str = ""


@dataclass
class SmartEndpoints:
    iss: str
    authorize_url: str
    token_url: str
    introspection_url: str | None = None
    revocation_url: str | None = None
    capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SmartLaunchRequest:
    iss: str
    client_id: str
    redirect_uri: str
    scope: str
    launch: str | None = None
    aud: str | None = None
    state: str = ""
    code_challenge: str | None = None
    code_challenge_method: str = "S256"
    patient_id: str | None = None
    encounter_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SmartTokenSet:
    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
    scope: str = ""
    refresh_token: str | None = None
    patient_id: str | None = None
    encounter_id: str | None = None
    id_token: str | None = None
    issued_token_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SmartLaunchSession:
    request: SmartLaunchRequest
    endpoints: SmartEndpoints
    state: str
    code_verifier: str | None = None
    authorize_url: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SmartCallbackParams:
    code: str | None = None
    state: str | None = None
    iss: str | None = None
    launch: str | None = None
    error: str | None = None
    error_description: str | None = None
    patient_id: str | None = None
    encounter_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LaunchContext:
    iss: str
    launch: str | None = None
    patient_id: str | None = None
    encounter_id: str | None = None
    scope: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PatientSummary:
    patient_id: str
    display_name: str
    birth_date: str | None = None
    sex: str | None = None
    mrn: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EncounterSummary:
    encounter_id: str
    status: str
    encounter_class: str | None = None
    start: str | None = None
    end: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PatientChartBundle:
    patient: PatientSummary
    encounter: EncounterSummary | None = None
    diagnostic_reports: list[ResourceReference] = field(default_factory=list)
    imaging_studies: list[ResourceReference] = field(default_factory=list)
    medications: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImagingStudySummary:
    study_instance_uid: str
    patient_id: str
    modality: str
    description: str
    study_date: str | None = None
    series_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StudyMetadata:
    study_instance_uid: str
    series: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SeriesSummary:
    study_instance_uid: str
    series_instance_uid: str
    modality: str = ""
    description: str = ""
    instance_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class InstanceSummary:
    study_instance_uid: str
    series_instance_uid: str
    sop_instance_uid: str
    instance_number: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievedObject:
    content_type: str
    data: bytes
    metadata: dict[str, Any] = field(default_factory=dict)


class EHRConnector(Protocol):
    connector_name: str
    mode: ConnectorMode

    async def discover_endpoints(self, iss: str | None = None) -> SmartEndpoints:
        ...

    async def build_authorize_url(self, request: SmartLaunchRequest) -> str:
        ...

    async def exchange_authorization_code(
        self,
        *,
        code: str,
        redirect_uri: str | None = None,
        client_id: str | None = None,
        code_verifier: str | None = None,
        iss: str | None = None,
    ) -> SmartTokenSet:
        ...

    async def validate_capabilities(self, required: list[str], iss: str | None = None) -> list[str]:
        ...

    async def refresh_access_token(
        self,
        *,
        refresh_token: str,
        scope: str | None = None,
        iss: str | None = None,
    ) -> SmartTokenSet:
        ...

    async def begin_sandbox_launch(
        self,
        *,
        iss: str,
        launch: str | None = None,
        patient_id: str | None = None,
        encounter_id: str | None = None,
        state: str | None = None,
    ) -> SmartLaunchSession:
        ...

    def parse_callback(self, callback_url: str) -> SmartCallbackParams:
        ...

    async def complete_sandbox_launch(
        self,
        *,
        callback_url: str,
        session: SmartLaunchSession,
    ) -> tuple[SmartTokenSet, LaunchContext]:
        ...

    async def get_launch_context(
        self,
        *,
        iss: str | None = None,
        launch: str | None = None,
        patient_id: str | None = None,
        encounter_id: str | None = None,
    ) -> LaunchContext:
        ...

    async def fetch_patient(self, patient_id: str) -> PatientSummary:
        ...

    async def fetch_encounter(self, encounter_id: str) -> EncounterSummary:
        ...

    async def fetch_patient_chart(
        self,
        *,
        patient_id: str,
        encounter_id: str | None = None,
    ) -> PatientChartBundle:
        ...


class ImagingConnector(Protocol):
    connector_name: str
    mode: ConnectorMode

    async def search_studies(
        self,
        *,
        patient_id: str | None = None,
        accession_number: str | None = None,
        modality: str | None = None,
    ) -> list[ImagingStudySummary]:
        ...

    async def get_study_metadata(self, study_instance_uid: str) -> StudyMetadata:
        ...

    async def search_series(
        self,
        *,
        study_instance_uid: str,
        modality: str | None = None,
    ) -> list[SeriesSummary]:
        ...

    async def search_instances(
        self,
        *,
        study_instance_uid: str,
        series_instance_uid: str,
    ) -> list[InstanceSummary]:
        ...

    async def get_series_metadata(
        self,
        *,
        study_instance_uid: str,
        series_instance_uid: str,
    ) -> dict[str, Any]:
        ...

    async def retrieve_instance(
        self,
        *,
        study_instance_uid: str,
        series_instance_uid: str,
        sop_instance_uid: str,
    ) -> RetrievedObject:
        ...


@dataclass
class ConnectorBundle:
    ehr: EHRConnector
    imaging: ImagingConnector
