from __future__ import annotations

import uvicorn

from clinicalclaw.api import create_app
from clinicalclaw.config import load_settings


def main() -> None:
    settings = load_settings()
    uvicorn.run(
        create_app(),
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    main()
