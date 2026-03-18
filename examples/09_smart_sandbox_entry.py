import asyncio
from dataclasses import asdict
from dataclasses import is_dataclass
from pprint import pprint

from clinicalclaw.config import load_settings
from clinicalclaw.execution import ClinicalClawService
from clinicalclaw.smart_launcher import complete_demo_authorize_redirect
from clinicalclaw.store import SQLiteStore


async def main():
    settings = load_settings()
    service = ClinicalClawService(settings=settings)
    iss = settings.fhir_base_url.strip()
    if not iss:
        raise RuntimeError(
            "SMART issuer is not configured. Set CLINICALCLAW_FHIR_BASE_URL or SMART launcher env vars in .env."
        )

    session = await service.begin_smart_launch(
        iss=iss,
    )
    print("Session ID:")
    print(session.id)
    print()
    print("Authorize URL:")
    print(session.authorize_url)
    print()
    print(f"Resolved issuer/base FHIR URL: {iss}")

    callback_url = ""
    if settings.smart_launcher_auto_callback:
        callback_url = await complete_demo_authorize_redirect(
            session.authorize_url,
            patient_id=settings.smart_launcher_patient_id,
            provider_id=settings.smart_launcher_provider_id,
            timeout_s=settings.connector_timeout_s,
        )
        print()
        print("Auto-generated callback URL:")
        print(callback_url)
    else:
        print()
        print("After you receive the redirect callback URL, set it below and rerun the completion section.")

    if not callback_url:
        return

    token_state, launch_context = await service.complete_smart_launch(
        session_id=session.id,
        callback_url=callback_url,
    )
    print()
    print("Saved token state:")
    pprint(token_state.model_dump())
    print()
    print("Launch context:")
    pprint(launch_context)

    chart = await service.validate_smart_read(
        patient_id=launch_context.patient_id or settings.smart_launcher_patient_id,
        encounter_id=launch_context.encounter_id,
        iss=launch_context.iss,
    )
    print()
    print("Fetched patient chart summary:")
    pprint(asdict(chart) if is_dataclass(chart) else chart)

    reloaded = SQLiteStore(settings.database_path)
    persisted_session = reloaded.get_smart_launch_session(session.id)
    persisted_token = reloaded.list_smart_token_states(limit=1)[0]
    print()
    print("SQLite persistence check:")
    pprint(
        {
            "database_path": settings.database_path,
            "launch_session_id": persisted_session.id if persisted_session else None,
            "token_state_id": persisted_token.id,
            "token_patient_id": persisted_token.patient_id,
        }
    )


if __name__ == "__main__":
    asyncio.run(main())
