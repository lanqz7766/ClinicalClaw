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


class EHRConnector(Protocol):
    connector_name: str
    mode: ConnectorMode

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

    async def get_series_metadata(
        self,
        *,
        study_instance_uid: str,
        series_instance_uid: str,
    ) -> dict[str, Any]:
        ...


@dataclass
class ConnectorBundle:
    ehr: EHRConnector
    imaging: ImagingConnector
