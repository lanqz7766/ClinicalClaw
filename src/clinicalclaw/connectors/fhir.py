from __future__ import annotations

from typing import Any

import httpx

from clinicalclaw.connectors.base import (
    ConnectorError,
    ConnectorMode,
    EncounterSummary,
    LaunchContext,
    PatientChartBundle,
    PatientSummary,
    ResourceReference,
)


class SmartFHIRConnector:
    connector_name = "smart_fhir"

    def __init__(
        self,
        *,
        mode: ConnectorMode,
        base_url: str = "",
        access_token: str = "",
        timeout_s: float = 15.0,
    ) -> None:
        self.mode = mode
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.timeout_s = timeout_s

    async def get_launch_context(
        self,
        *,
        iss: str | None = None,
        launch: str | None = None,
        patient_id: str | None = None,
        encounter_id: str | None = None,
    ) -> LaunchContext:
        if self.mode == ConnectorMode.mock:
            return LaunchContext(
                iss=iss or "https://mock-fhir.example.org/fhir/R4",
                launch=launch or "mock-launch-token",
                patient_id=patient_id or "mock-patient-001",
                encounter_id=encounter_id or "mock-encounter-001",
                scope="launch/patient patient/*.read",
                metadata={"mode": self.mode.value},
            )

        return LaunchContext(
            iss=iss or self.base_url,
            launch=launch,
            patient_id=patient_id,
            encounter_id=encounter_id,
            scope="launch/patient patient/*.read",
            metadata={"mode": self.mode.value},
        )

    async def fetch_patient(self, patient_id: str) -> PatientSummary:
        if self.mode == ConnectorMode.mock:
            return PatientSummary(
                patient_id=patient_id,
                display_name="Demo, Patient",
                birth_date="1978-04-16",
                sex="female",
                mrn="MRN-CLINICALCLAW-001",
                metadata={"source": "mock"},
            )

        payload = await self._get_json(f"Patient/{patient_id}")
        names = payload.get("name", [])
        display_name = "Unknown Patient"
        if names:
            first = names[0]
            given = " ".join(first.get("given", []))
            family = first.get("family", "")
            display_name = ", ".join(part for part in [family, given] if part)
        return PatientSummary(
            patient_id=payload.get("id", patient_id),
            display_name=display_name,
            birth_date=payload.get("birthDate"),
            sex=payload.get("gender"),
            metadata={"source": self.mode.value},
        )

    async def fetch_encounter(self, encounter_id: str) -> EncounterSummary:
        if self.mode == ConnectorMode.mock:
            return EncounterSummary(
                encounter_id=encounter_id,
                status="in-progress",
                encounter_class="AMB",
                start="2026-03-18T09:00:00Z",
                metadata={"source": "mock"},
            )

        payload = await self._get_json(f"Encounter/{encounter_id}")
        encounter_class = None
        if isinstance(payload.get("class"), dict):
            encounter_class = payload["class"].get("code")
        period = payload.get("period", {})
        return EncounterSummary(
            encounter_id=payload.get("id", encounter_id),
            status=payload.get("status", "unknown"),
            encounter_class=encounter_class,
            start=period.get("start"),
            end=period.get("end"),
            metadata={"source": self.mode.value},
        )

    async def fetch_patient_chart(
        self,
        *,
        patient_id: str,
        encounter_id: str | None = None,
    ) -> PatientChartBundle:
        if self.mode == ConnectorMode.mock:
            return PatientChartBundle(
                patient=await self.fetch_patient(patient_id),
                encounter=await self.fetch_encounter(encounter_id or "mock-encounter-001"),
                diagnostic_reports=[
                    ResourceReference("DiagnosticReport", "dr-001", "Chest CT narrative"),
                    ResourceReference("DiagnosticReport", "dr-002", "Pulmonary follow-up report"),
                ],
                imaging_studies=[
                    ResourceReference("ImagingStudy", "img-001", "CT Chest without contrast"),
                    ResourceReference("ImagingStudy", "img-002", "Chest X-ray PA/LAT"),
                ],
                medications=["Lisinopril 10 mg daily", "Metformin 500 mg BID"],
                problems=["Hypertension", "Type 2 diabetes"],
                observations=["Latest A1c 6.9%", "Creatinine normal"],
                metadata={"mode": self.mode.value},
            )

        patient = await self.fetch_patient(patient_id)
        encounter = await self.fetch_encounter(encounter_id) if encounter_id else None
        reports = await self._search_resource_refs("DiagnosticReport", patient_id)
        imaging = await self._search_resource_refs("ImagingStudy", patient_id)

        return PatientChartBundle(
            patient=patient,
            encounter=encounter,
            diagnostic_reports=reports,
            imaging_studies=imaging,
            metadata={"mode": self.mode.value},
        )

    async def _search_resource_refs(self, resource_type: str, patient_id: str) -> list[ResourceReference]:
        payload = await self._get_json(f"{resource_type}?patient={patient_id}")
        entries = payload.get("entry", [])
        references: list[ResourceReference] = []
        for entry in entries:
            resource = entry.get("resource", {})
            references.append(
                ResourceReference(
                    resource_type=resource.get("resourceType", resource_type),
                    resource_id=resource.get("id", ""),
                    display=resource.get("status", ""),
                )
            )
        return references

    async def _get_json(self, path: str) -> dict[str, Any]:
        if not self.base_url:
            raise ConnectorError("FHIR base URL is not configured")

        headers = {"Accept": "application/fhir+json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        async with httpx.AsyncClient(timeout=self.timeout_s, headers=headers) as client:
            response = await client.get(f"{self.base_url}/{path.lstrip('/')}")
            response.raise_for_status()
            return response.json()
