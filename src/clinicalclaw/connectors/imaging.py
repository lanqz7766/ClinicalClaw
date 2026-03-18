from __future__ import annotations

import re
from typing import Any

import httpx

from clinicalclaw.connectors.base import (
    ConnectorError,
    ConnectorMode,
    InstanceSummary,
    ImagingStudySummary,
    RetrievedObject,
    SeriesSummary,
    StudyMetadata,
)


class DICOMWebConnector:
    connector_name = "dicomweb"

    def __init__(
        self,
        *,
        mode: ConnectorMode,
        base_url: str = "",
        access_token: str = "",
        timeout_s: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.mode = mode
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.timeout_s = timeout_s
        self.transport = transport

    async def search_studies(
        self,
        *,
        patient_id: str | None = None,
        accession_number: str | None = None,
        modality: str | None = None,
    ) -> list[ImagingStudySummary]:
        if self.mode == ConnectorMode.mock:
            pid = patient_id or "mock-patient-001"
            modality_value = modality or "CT"
            return [
                ImagingStudySummary(
                    study_instance_uid="1.2.840.113619.2.55.3.604688435.781.1710000000.10",
                    patient_id=pid,
                    modality=modality_value,
                    description="Mock chest imaging study",
                    study_date="2026-03-10",
                    series_count=2,
                    metadata={"source": "mock"},
                )
            ]

        params = {}
        if patient_id:
            params["PatientID"] = patient_id
        if accession_number:
            params["AccessionNumber"] = accession_number
        if modality:
            params["ModalitiesInStudy"] = modality

        payload = await self._get_json("studies", params=params)
        studies: list[ImagingStudySummary] = []
        for item in payload:
            studies.append(
                ImagingStudySummary(
                    study_instance_uid=_dicom_value(item, "0020000D"),
                    patient_id=_dicom_value(item, "00100020"),
                    modality=_dicom_value(item, "00080061"),
                    description=_dicom_value(item, "00081030"),
                    study_date=_dicom_value(item, "00080020"),
                    series_count=int(_dicom_value(item, "00201206") or 0),
                    metadata={"source": self.mode.value},
                )
            )
        return studies

    async def search_series(
        self,
        *,
        study_instance_uid: str,
        modality: str | None = None,
    ) -> list[SeriesSummary]:
        if self.mode == ConnectorMode.mock:
            return [
                SeriesSummary(
                    study_instance_uid=study_instance_uid,
                    series_instance_uid="1.2.3.4.1",
                    modality=modality or "CT",
                    description="Mock axial series",
                    instance_count=120,
                    metadata={"source": "mock"},
                )
            ]

        params: dict[str, str] = {}
        if modality:
            params["Modality"] = modality
        payload = await self._get_json(f"studies/{study_instance_uid}/series", params=params or None)
        series: list[SeriesSummary] = []
        for item in payload:
            series.append(
                SeriesSummary(
                    study_instance_uid=study_instance_uid,
                    series_instance_uid=_dicom_value(item, "0020000E"),
                    modality=_dicom_value(item, "00080060"),
                    description=_dicom_value(item, "0008103E"),
                    instance_count=int(_dicom_value(item, "00201209") or 0),
                    metadata={"source": self.mode.value},
                )
            )
        return series

    async def search_instances(
        self,
        *,
        study_instance_uid: str,
        series_instance_uid: str,
    ) -> list[InstanceSummary]:
        if self.mode == ConnectorMode.mock:
            return [
                InstanceSummary(
                    study_instance_uid=study_instance_uid,
                    series_instance_uid=series_instance_uid,
                    sop_instance_uid="1.2.3.4.1.1",
                    instance_number="1",
                    metadata={"source": "mock"},
                )
            ]

        payload = await self._get_json(
            f"studies/{study_instance_uid}/series/{series_instance_uid}/instances"
        )
        instances: list[InstanceSummary] = []
        for item in payload:
            instances.append(
                InstanceSummary(
                    study_instance_uid=study_instance_uid,
                    series_instance_uid=series_instance_uid,
                    sop_instance_uid=_dicom_value(item, "00080018"),
                    instance_number=_dicom_value(item, "00200013"),
                    metadata={"source": self.mode.value},
                )
            )
        return instances

    async def get_study_metadata(self, study_instance_uid: str) -> StudyMetadata:
        if self.mode == ConnectorMode.mock:
            return StudyMetadata(
                study_instance_uid=study_instance_uid,
                series=[
                    {"series_instance_uid": "1.2.3.4.1", "modality": "CT", "instances": 120},
                    {"series_instance_uid": "1.2.3.4.2", "modality": "CT", "instances": 60},
                ],
                metadata={"source": "mock"},
            )

        payload = await self._get_json(f"studies/{study_instance_uid}/metadata")
        return StudyMetadata(
            study_instance_uid=study_instance_uid,
            series=payload if isinstance(payload, list) else [payload],
            metadata={"source": self.mode.value},
        )

    async def get_series_metadata(
        self,
        *,
        study_instance_uid: str,
        series_instance_uid: str,
    ) -> dict[str, Any]:
        if self.mode == ConnectorMode.mock:
            return {
                "study_instance_uid": study_instance_uid,
                "series_instance_uid": series_instance_uid,
                "modality": "CT",
                "instance_count": 120,
                "source": "mock",
            }

        payload = await self._get_json(
            f"studies/{study_instance_uid}/series/{series_instance_uid}/metadata"
        )
        return {
            "study_instance_uid": study_instance_uid,
            "series_instance_uid": series_instance_uid,
            "metadata": payload,
            "source": self.mode.value,
        }

    async def retrieve_instance(
        self,
        *,
        study_instance_uid: str,
        series_instance_uid: str,
        sop_instance_uid: str,
    ) -> RetrievedObject:
        if self.mode == ConnectorMode.mock:
            return RetrievedObject(
                content_type="application/dicom",
                data=b"MOCK-DICOM-BYTES",
                metadata={
                    "study_instance_uid": study_instance_uid,
                    "series_instance_uid": series_instance_uid,
                    "sop_instance_uid": sop_instance_uid,
                    "source": "mock",
                },
            )

        if not self.base_url:
            raise ConnectorError("DICOMweb base URL is not configured")

        headers = {"Accept": 'multipart/related; type="application/dicom"; transfer-syntax=*'}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        path = (
            f"{self.base_url}/studies/{study_instance_uid}"
            f"/series/{series_instance_uid}/instances/{sop_instance_uid}"
        )
        async with httpx.AsyncClient(
            timeout=self.timeout_s,
            headers=headers,
            transport=self.transport,
        ) as client:
            response = await client.get(path)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "application/dicom")
            data = response.content
            if content_type.lower().startswith("multipart/related"):
                content_type, data = _extract_first_multipart_part(content_type, data)
            return RetrievedObject(
                content_type=content_type,
                data=data,
                metadata={
                    "study_instance_uid": study_instance_uid,
                    "series_instance_uid": series_instance_uid,
                    "sop_instance_uid": sop_instance_uid,
                    "source": self.mode.value,
                },
            )

    async def _get_json(self, path: str, params: dict[str, str] | None = None) -> Any:
        if not self.base_url:
            raise ConnectorError("DICOMweb base URL is not configured")

        headers = {"Accept": "application/dicom+json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        async with httpx.AsyncClient(
            timeout=self.timeout_s,
            headers=headers,
            transport=self.transport,
        ) as client:
            response = await client.get(f"{self.base_url}/{path.lstrip('/')}", params=params)
            response.raise_for_status()
            return response.json()


def _dicom_value(item: dict[str, Any], tag: str) -> str:
    values = item.get(tag, {}).get("Value", [])
    if not values:
        return ""
    value = values[0]
    if isinstance(value, dict):
        return str(value.get("Alphabetic", ""))
    return str(value)


def _extract_first_multipart_part(content_type: str, payload: bytes) -> tuple[str, bytes]:
    match = re.search(r'boundary="?([^";]+)"?', content_type, flags=re.IGNORECASE)
    if not match:
        raise ConnectorError("Multipart DICOMweb response did not include a boundary")

    boundary = match.group(1).encode("utf-8")
    delimiter = b"--" + boundary
    for part in payload.split(delimiter):
        if not part or part in {b"--", b"--\r\n"}:
            continue
        segment = part.lstrip(b"\r\n")
        if segment.endswith(b"--\r\n"):
            segment = segment[:-4]
        elif segment.endswith(b"--"):
            segment = segment[:-2]
        if segment.endswith(b"\r\n"):
            segment = segment[:-2]

        header_blob, separator, body = segment.partition(b"\r\n\r\n")
        if not separator:
            continue

        part_content_type = "application/dicom"
        for line in header_blob.decode("latin-1", errors="ignore").split("\r\n"):
            if line.lower().startswith("content-type:"):
                part_content_type = line.split(":", 1)[1].strip()
                break
        return part_content_type, body

    raise ConnectorError("Multipart DICOMweb response did not contain a readable part")
