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
    connector_timeout_s: float = Field(default=15.0, alias="CLINICALCLAW_CONNECTOR_TIMEOUT_S")
    ehr_connector_mode: str = Field(default="mock", alias="CLINICALCLAW_EHR_CONNECTOR_MODE")
    imaging_connector_mode: str = Field(default="mock", alias="CLINICALCLAW_IMAGING_CONNECTOR_MODE")
    fhir_base_url: str = Field(default="", alias="CLINICALCLAW_FHIR_BASE_URL")
    fhir_access_token: str = Field(default="", alias="CLINICALCLAW_FHIR_ACCESS_TOKEN")
    fhir_authorize_url: str = Field(default="", alias="CLINICALCLAW_FHIR_AUTHORIZE_URL")
    fhir_token_url: str = Field(default="", alias="CLINICALCLAW_FHIR_TOKEN_URL")
    fhir_client_id: str = Field(default="", alias="CLINICALCLAW_FHIR_CLIENT_ID")
    fhir_client_secret: str = Field(default="", alias="CLINICALCLAW_FHIR_CLIENT_SECRET")
    fhir_redirect_uri: str = Field(default="", alias="CLINICALCLAW_FHIR_REDIRECT_URI")
    fhir_scope: str = Field(
        default="launch/patient patient/*.read encounter/*.read openid fhirUser",
        alias="CLINICALCLAW_FHIR_SCOPE",
    )
    dicomweb_base_url: str = Field(default="", alias="CLINICALCLAW_DICOMWEB_BASE_URL")
    dicomweb_access_token: str = Field(default="", alias="CLINICALCLAW_DICOMWEB_ACCESS_TOKEN")


def load_settings() -> ClinicalClawSettings:
    _discover_env_file()
    return ClinicalClawSettings(_env_file=_env_file) if _env_file else ClinicalClawSettings()
