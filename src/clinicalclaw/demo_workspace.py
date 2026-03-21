from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from clinicalclaw.neuro_longitudinal import neuro_longitudinal_store as fallback_neuro_store
from clinicalclaw.neuro_longitudinal_proteas import (
    DEFAULT_PATIENT_ID,
    build_neuro_longitudinal_workspace,
    discover_proteas_patient_ids,
    resolve_proteas_data_root,
)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _safe_number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class DemoWorkspaceStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._cases = self._build_cases()

    def _build_cases(self) -> dict[str, dict[str, Any]]:
        resolved_root = resolve_proteas_data_root()
        if resolved_root is None:
            return {
                case["id"]: fallback_neuro_store.get_case(case["id"])
                for case in fallback_neuro_store.snapshot()["cases"]
            }

        patient_ids = discover_proteas_patient_ids(resolved_root)
        preferred = DEFAULT_PATIENT_ID if DEFAULT_PATIENT_ID in patient_ids else (patient_ids[0] if patient_ids else DEFAULT_PATIENT_ID)
        ordered = [preferred] + [pid for pid in patient_ids if pid != preferred]
        cases: dict[str, dict[str, Any]] = {}
        for patient_id in ordered[:3]:
            try:
                workspace = build_neuro_longitudinal_workspace(data_root=resolved_root, patient_id=patient_id).model_dump()
            except Exception:
                continue
            cases[workspace["id"]] = workspace
        return cases

    def _all_cases(self) -> dict[str, dict[str, Any]]:
        return self._cases

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            cases = self._all_cases()
            default_case_id = next(iter(cases))
            return {
                "cases": [
                    {
                        "id": case["id"],
                        "title": case["title"],
                        "dataset": case["dataset"],
                        "patient": case["patient"],
                        "review": case["review"],
                        "risk_level": case["analysis"]["risk_level"],
                    }
                    for case in cases.values()
                ],
                "default_case_id": default_case_id,
                "workspace": deepcopy(cases[default_case_id]),
            }

    def get_case(self, case_id: str) -> dict[str, Any]:
        with self._lock:
            cases = self._all_cases()
            case = cases.get(case_id)
            if not case:
                raise KeyError(case_id)
            return deepcopy(case)

    def add_upload(self, case_id: str, filename: str) -> dict[str, Any]:
        with self._lock:
            workspace = self._cases.get(case_id)
            if not workspace:
                raise KeyError(case_id)
            workspace.setdefault("uploads", []).append(
                {
                    "id": f"upload_{len(workspace.get('uploads', [])) + 1}",
                    "filename": filename,
                    "added_at": _utc_now_iso(),
                }
            )
            workspace.setdefault("audit", []).insert(
                0,
                {
                    "id": f"audit_upload_{len(workspace.get('audit', [])) + 1}",
                    "title": "Local file attached",
                    "detail": f"Registered local upload: {filename}",
                    "severity": "info",
                    "created_at": _utc_now_iso(),
                },
            )
            return deepcopy(workspace)

    def chat(self, case_id: str, message: str) -> dict[str, Any]:
        with self._lock:
            workspace = self._cases.get(case_id)
            if not workspace:
                raise KeyError(case_id)
            messages = workspace.setdefault("messages", [])
            messages.append(
                {
                    "id": f"msg_user_{len(messages) + 1}",
                    "role": "user",
                    "content": message,
                    "created_at": _utc_now_iso(),
                }
            )
            lowered = message.lower()
            analysis = workspace.get("analysis", {})
            latest_volume = _safe_number(analysis.get("latest_volume_ml"))
            cumulative_change = _safe_number(analysis.get("cumulative_change_pct"))
            recent_change = _safe_number(
                analysis.get("recent_interval_change_pct", analysis.get("recent_segment_pct"))
            )
            if any(token in lowered for token in {"report", "brief", "summary", "summarize", "tumor board"}):
                content = (
                    f"The treated lesion remains in a {str(analysis.get('risk_level', 'in review')).lower()} lane. "
                    f"Enhancing tumor burden is {latest_volume:.2f} mL at the latest follow-up, "
                    f"with {cumulative_change:+.1f}% change from baseline and "
                    f"{recent_change:+.1f}% change in the latest interval."
                )
                title = "Longitudinal report refreshed"
                detail = "Regenerated the clinician-facing longitudinal review brief."
            elif any(token in lowered for token in {"risk", "progress", "response", "signal", "concern"}):
                content = (
                    f"The current concern is {analysis.get('risk_level', 'in review')}. "
                    f"Recent interval change is {recent_change:+.1f}%, "
                    f"but overall burden remains {cumulative_change:+.1f}% above baseline."
                )
                title = "Risk explanation requested"
                detail = "Explained the current longitudinal response signal."
            else:
                content = (
                    "I can summarize the longitudinal response review, explain the current signal, or generate a concise tumor-board brief."
                )
                title = "General neuro guidance"
                detail = "Returned supported longitudinal neuro-oncology actions."
            assistant = {
                "id": f"msg_assistant_{len(messages) + 1}",
                "role": "assistant",
                "content": content,
                "created_at": _utc_now_iso(),
            }
            messages.append(assistant)
            workspace.setdefault("audit", []).insert(
                0,
                {
                    "id": f"audit_chat_{len(workspace.get('audit', [])) + 1}",
                    "title": title,
                    "detail": detail,
                    "severity": "info",
                    "created_at": _utc_now_iso(),
                },
            )
            workspace.setdefault("review", {})["status"] = "in_review"
            workspace["review"]["comment"] = "AI review refreshed and awaiting clinician sign-off."
            workspace["review"]["updated_at"] = _utc_now_iso()
            return {"assistant": assistant, "workspace": deepcopy(workspace)}

    def review(self, case_id: str, action: str, comment: str | None = None) -> dict[str, Any]:
        with self._lock:
            workspace = self._cases.get(case_id)
            if not workspace:
                raise KeyError(case_id)
            normalized = action.strip().lower()
            review = workspace.setdefault("review", {})
            status_map = {"approve": "approved", "reject": "rejected", "comment": review.get("status", "in_review")}
            review["status"] = status_map.get(normalized, review.get("status", "in_review"))
            review["comment"] = comment or review.get("comment") or ""
            review["updated_at"] = _utc_now_iso()
            workspace.setdefault("audit", []).insert(
                0,
                {
                    "id": f"audit_review_{len(workspace.get('audit', [])) + 1}",
                    "title": f"Reviewer action: {normalized}",
                    "detail": comment or f"Review status changed to {review['status']}.",
                    "severity": "success" if normalized == "approve" else "warning" if normalized == "reject" else "info",
                    "created_at": _utc_now_iso(),
                },
            )
            return deepcopy(workspace)


demo_workspace_store = DemoWorkspaceStore()
