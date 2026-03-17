from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_loaded = False
_env_file: Path | None = None


def _discover_env_file() -> None:
    global _loaded, _env_file
    if _loaded:
        return
    _loaded = True

    explicit = os.environ.get("CLINICALCLAW_ENV_FILE") or os.environ.get("CLAWAGENTS_ENV_FILE")
    cwd = Path.cwd()
    local_env = cwd / ".env"
    parent_env = cwd.parent / ".env"

    if explicit and Path(explicit).exists():
        _env_file = Path(explicit)
    elif local_env.exists():
        _env_file = local_env
    elif parent_env.exists():
        _env_file = parent_env

    if _env_file:
        from dotenv import load_dotenv

        load_dotenv(_env_file, override=True)


class ClinicalClawSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="ClinicalClaw", alias="CLINICALCLAW_APP_NAME")
    environment: str = Field(default="development", alias="CLINICALCLAW_ENVIRONMENT")
    host: str = Field(default="127.0.0.1", alias="CLINICALCLAW_HOST")
    port: int = Field(default=8000, alias="CLINICALCLAW_PORT")
    api_prefix: str = Field(default="/v1", alias="CLINICALCLAW_API_PREFIX")
    default_model: str = Field(default="gpt-5-mini", alias="CLINICALCLAW_DEFAULT_MODEL")
    scenario_dir: str = Field(default="scenarios", alias="CLINICALCLAW_SCENARIO_DIR")
    artifact_dir: str = Field(default=".clinicalclaw/artifacts", alias="CLINICALCLAW_ARTIFACT_DIR")
    log_level: str = Field(default="info", alias="CLINICALCLAW_LOG_LEVEL")


def load_settings() -> ClinicalClawSettings:
    _discover_env_file()
    return ClinicalClawSettings(_env_file=_env_file) if _env_file else ClinicalClawSettings()

