from __future__ import annotations

import logging
from dataclasses import dataclass

from clinicalclaw.connectors.base import EHRConnector
from clinicalclaw.models import SmartTokenStateRecord


logger = logging.getLogger(__name__)


@dataclass
class SmartReauthRequiredError(RuntimeError):
    reason: str
    action: str = "launch SMART auth"
    iss: str | None = None

    def __post_init__(self) -> None:
        super().__init__(self.reason)

    def to_payload(self) -> dict[str, str]:
        return {
            "status": "reauth_required",
            "reason": self.reason,
            "action": self.action,
        }


class TokenManager:
    def __init__(
        self,
        *,
        connector: EHRConnector,
        store,
    ) -> None:
        self.connector = connector
        self.store = store

    def get_latest_token_state(self, *, iss: str | None = None) -> SmartTokenStateRecord | None:
        for token_state in self.store.list_smart_token_states(limit=20):
            if iss and token_state.iss.rstrip("/") != iss.rstrip("/"):
                continue
            return token_state
        return None

    def is_expired(self, token_state: SmartTokenStateRecord, skew_seconds: int = 60) -> bool:
        return token_state.is_expired(skew_seconds=skew_seconds)

    def has_refresh_token(self, token_state: SmartTokenStateRecord) -> bool:
        return bool(token_state.refresh_token)

    async def refresh_if_needed(
        self,
        *,
        iss: str | None = None,
        skew_seconds: int = 60,
    ) -> SmartTokenStateRecord:
        token_state = self.get_latest_token_state(iss=iss)
        if not token_state:
            logger.warning("SMART token lookup found no token state; re-authentication required", extra={"iss": iss or ""})
            raise SmartReauthRequiredError(
                reason="No SMART token is available for this environment.",
                iss=iss,
            )

        self.connector.access_token = token_state.access_token
        if not self.is_expired(token_state, skew_seconds=skew_seconds):
            logger.info(
                "SMART token is still valid; reusing existing access token",
                extra={"token_id": token_state.id, "iss": token_state.iss},
            )
            return token_state

        if not self.has_refresh_token(token_state):
            logger.warning(
                "SMART token expired without a refresh_token; environment is no-refresh-capable",
                extra={"token_id": token_state.id, "iss": token_state.iss},
            )
            raise SmartReauthRequiredError(
                reason="SMART token expired and no refresh_token is available.",
                iss=token_state.iss,
            )

        logger.info(
            "Attempting SMART token refresh",
            extra={"token_id": token_state.id, "iss": token_state.iss},
        )
        try:
            refreshed = await self.connector.refresh_access_token(
                refresh_token=token_state.refresh_token or "",
                scope=token_state.scope,
                iss=token_state.iss,
            )
        except Exception as exc:
            logger.error(
                "SMART token refresh failed; re-authentication required",
                extra={"token_id": token_state.id, "iss": token_state.iss, "error": str(exc)},
            )
            raise SmartReauthRequiredError(
                reason=f"SMART token refresh failed: {type(exc).__name__}",
                iss=token_state.iss,
            ) from exc

        refreshed_state = self.store.save_smart_token_state(
            SmartTokenStateRecord(
                session_id=token_state.session_id,
                iss=token_state.iss,
                token_type=refreshed.token_type,
                access_token=refreshed.access_token,
                refresh_token=refreshed.refresh_token,
                scope=refreshed.scope,
                expires_in=refreshed.expires_in,
                patient_id=refreshed.patient_id or token_state.patient_id,
                encounter_id=refreshed.encounter_id or token_state.encounter_id,
                metadata={
                    "mode": refreshed.metadata.get("mode", ""),
                    "refreshed_from": token_state.id,
                    "refresh_capable": bool(refreshed.refresh_token),
                },
            )
        )
        self.connector.access_token = refreshed_state.access_token
        logger.info(
            "SMART token refresh succeeded",
            extra={
                "source_token_id": token_state.id,
                "refreshed_token_id": refreshed_state.id,
                "iss": token_state.iss,
            },
        )
        return refreshed_state

    async def get_valid_access_token(
        self,
        *,
        iss: str | None = None,
        skew_seconds: int = 60,
    ) -> str:
        token_state = await self.refresh_if_needed(iss=iss, skew_seconds=skew_seconds)
        if not token_state.access_token:
            raise SmartReauthRequiredError(
                reason="SMART token state exists but access_token is empty.",
                iss=token_state.iss,
            )
        return token_state.access_token
