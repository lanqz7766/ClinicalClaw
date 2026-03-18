import asyncio
import os
from dataclasses import asdict
from dataclasses import is_dataclass
from pprint import pprint

from clinicalclaw.config import load_settings
from clinicalclaw.execution import ClinicalClawService


async def main():
    settings = load_settings()
    service = ClinicalClawService(settings=settings)
    patient_id = os.getenv("CLINICALCLAW_DICOMWEB_SAMPLE_PATIENT_ID", "").strip()
    if not patient_id:
        raise RuntimeError("Set CLINICALCLAW_DICOMWEB_SAMPLE_PATIENT_ID in .env to run the DICOMweb demo.")
    if not settings.dicomweb_base_url:
        raise RuntimeError("Set CLINICALCLAW_DICOMWEB_BASE_URL in .env to run the DICOMweb demo.")

    print("DICOMweb base URL:")
    print(settings.dicomweb_base_url)
    print()
    print("Sample patient ID:")
    print(patient_id)

    studies = await service.connectors.imaging.search_studies(patient_id=patient_id)
    if not studies:
        raise RuntimeError(f"No studies returned for patient {patient_id}")

    study = studies[0]
    series = await service.connectors.imaging.search_series(study_instance_uid=study.study_instance_uid)
    if not series:
        raise RuntimeError(f"No series returned for study {study.study_instance_uid}")

    first_series = series[0]
    instances = await service.connectors.imaging.search_instances(
        study_instance_uid=study.study_instance_uid,
        series_instance_uid=first_series.series_instance_uid,
    )
    if not instances:
        raise RuntimeError(f"No instances returned for series {first_series.series_instance_uid}")

    first_instance = instances[0]
    study_metadata = await service.connectors.imaging.get_study_metadata(study.study_instance_uid)
    series_metadata = await service.connectors.imaging.get_series_metadata(
        study_instance_uid=study.study_instance_uid,
        series_instance_uid=first_series.series_instance_uid,
    )
    retrieved = await service.connectors.imaging.retrieve_instance(
        study_instance_uid=study.study_instance_uid,
        series_instance_uid=first_series.series_instance_uid,
        sop_instance_uid=first_instance.sop_instance_uid,
    )

    print()
    print("Study summary:")
    pprint(asdict(study) if is_dataclass(study) else study)
    print()
    print("Series summary:")
    pprint(asdict(first_series) if is_dataclass(first_series) else first_series)
    print()
    print("Instance summary:")
    pprint(asdict(first_instance) if is_dataclass(first_instance) else first_instance)
    print()
    print("Study metadata sample:")
    pprint(
        {
            "study_instance_uid": study_metadata.study_instance_uid,
            "series_items": len(study_metadata.series),
        }
    )
    print()
    print("Series metadata sample:")
    pprint(
        {
            "study_instance_uid": series_metadata["study_instance_uid"],
            "series_instance_uid": series_metadata["series_instance_uid"],
            "metadata_items": len(series_metadata["metadata"]),
        }
    )
    print()
    print("Retrieved object sample:")
    pprint(
        {
            "content_type": retrieved.content_type,
            "bytes": len(retrieved.data),
            "sop_instance_uid": retrieved.metadata["sop_instance_uid"],
        }
    )


if __name__ == "__main__":
    asyncio.run(main())
