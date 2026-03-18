import asyncio
from pprint import pprint

from clinicalclaw.execution import ClinicalClawService


async def main():
    service = ClinicalClawService()

    session = await service.begin_smart_launch(
        iss="https://your-smart-sandbox.example.org/fhir/R4",
        launch="replace-with-launch-token-if-you-have-one",
    )
    print("Authorize URL:")
    print(session.authorize_url)
    print()
    print("After you receive the redirect callback URL, set it below and rerun the completion section.")

    callback_url = ""
    if callback_url:
        token_state, launch_context = await service.complete_smart_launch(
            session_id=session.id,
            callback_url=callback_url,
        )
        print("Saved token state:")
        pprint(token_state.model_dump())
        print("Launch context:")
        pprint(launch_context)


if __name__ == "__main__":
    asyncio.run(main())
