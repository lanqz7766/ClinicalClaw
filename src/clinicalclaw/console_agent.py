from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from clinicalclaw.engine import create_claw_agent
from clinicalclaw.engine.providers.llm import LLMMessage, LLMProvider
from clinicalclaw.engine.tools.registry import ToolResult
from clinicalclaw.console_workspace import WORKFLOWS, rank_workflows, route_general_query
from clinicalclaw.demo_workspace import demo_workspace_store
from clinicalclaw.findings_closure import findings_closure_store
from clinicalclaw.missed_diagnosis import missed_diagnosis_store
from clinicalclaw.neuro_longitudinal_proteas import (
    DEFAULT_NEURO_DATA_ENV,
    build_neuro_longitudinal_workspace,
    summarize_neuro_longitudinal_workspace,
)
from clinicalclaw.queue_triage import queue_triage_store
from clinicalclaw.screening_gap import screening_gap_store
from clinicalclaw.safety_monitor import KNOWLEDGE_BASE, safety_monitor_store

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = str(REPO_ROOT / "skills")


def _is_proteas_patient_id(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and text.upper().startswith("P")


def _resolve_neuro_patient_id(args: dict[str, Any]) -> str | None:
    if _is_proteas_patient_id(args.get("patient_id")):
        return str(args["patient_id"]).strip().upper()
    if _is_proteas_patient_id(args.get("case_id")):
        return str(args["case_id"]).strip().upper()
    return None


def _bool_arg(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _build_neuro_workspace_payload(args: dict[str, Any], *, prefer_proteas: bool = False) -> dict[str, Any] | None:
    patient_id = _resolve_neuro_patient_id(args) or "P28"
    data_root = args.get("data_root")
    compact = _bool_arg(args.get("compact"), default=True)
    materialize_assets = _bool_arg(args.get("materialize_assets"), default=True)

    if prefer_proteas or data_root or os.getenv(DEFAULT_NEURO_DATA_ENV):
        try:
            workspace = build_neuro_longitudinal_workspace(
                data_root=data_root,
                patient_id=patient_id,
                materialize_assets=materialize_assets,
            )
            return summarize_neuro_longitudinal_workspace(workspace) if compact else workspace.model_dump()
        except Exception:
            return None
    return None


class WorkflowCatalogTool:
    name = "workflow_catalog"
    description = "Return the available ClinicalClaw workflows, their module ids, and supported tools."
    parameters: dict[str, dict[str, Any]] = {}
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, output=json.dumps(WORKFLOWS, indent=2))


class NeuroWorkspaceTool:
    name = "get_neuro_workspace"
    description = "Return the current neuro longitudinal review workspace, including treatment-aligned MRI timeline, lesion burden trend, and the current physician brief."
    parameters = {
        "case_id": {
            "type": "string",
            "description": "Optional neuro case id. Defaults to the main mock longitudinal case.",
            "required": False,
        }
    }
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        payload = _build_neuro_workspace_payload(args, prefer_proteas=False)
        if payload is not None:
            return ToolResult(success=True, output=json.dumps(payload, indent=2))

        case_id = args.get("case_id") or demo_workspace_store.snapshot()["default_case_id"]
        workspace = demo_workspace_store.get_case(case_id)
        compact = {
            "id": workspace["id"],
            "title": workspace["title"],
            "patient": workspace["patient"],
            "analysis": workspace["analysis"],
            "report": {
                "title": workspace["report"]["title"],
                "summary": workspace["report"]["summary"],
                "risk_level": workspace["report"]["risk_level"],
            },
            "timeline": workspace["timeline"],
        }
        return ToolResult(success=True, output=json.dumps(compact, indent=2))


class DicomSeriesSelectorTool:
    name = "dicom_series_selector"
    description = "Select the preferred longitudinal MRI series for a neuro review case and summarize the chosen sequence family at each timepoint."
    parameters = {
        "case_id": {
            "type": "string",
            "description": "Optional neuro case id. Defaults to the current longitudinal neuro demo case.",
            "required": False,
        }
    }
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        payload = _build_neuro_workspace_payload({**args, "compact": False}, prefer_proteas=True)
        if payload is None:
            case_id = args.get("case_id") or demo_workspace_store.snapshot()["default_case_id"]
            payload = demo_workspace_store.get_case(case_id)
        case_id = payload["id"]
        series = [
            {
                "timepoint": item["timepoint"],
                "study_date": item["study_date"],
                "preferred_sequence": item.get("sequence") or next(
                    (series["modality"] for series in item.get("series", []) if series.get("modality") == "T1C"),
                    "T1C",
                ),
                "source_type": item.get("source_type", ""),
            }
            for item in payload["timeline"]
        ]
        return ToolResult(success=True, output=json.dumps({"case_id": case_id, "series": series}, indent=2))


class BrainMetResponseTrackerTool:
    name = "brain_met_response_tracker"
    description = "Return the longitudinal lesion response metrics for a neuro review case, including burden trend and recent interval change."
    parameters = {
        "case_id": {
            "type": "string",
            "description": "Optional neuro case id. Defaults to the current longitudinal neuro demo case.",
            "required": False,
        }
    }
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        payload = _build_neuro_workspace_payload({**args, "compact": False}, prefer_proteas=True)
        if payload is None:
            case_id = args.get("case_id") or demo_workspace_store.snapshot()["default_case_id"]
            payload = demo_workspace_store.get_case(case_id)
        case_id = payload["id"]
        analysis = payload["analysis"]
        points = [
            {
                "timepoint": item["timepoint"],
                "study_date": item["study_date"],
                "lesion_volume_ml": item["lesion_volume_ml"],
                "tumor_volume_ml": item.get("tumor_volume_ml"),
                "all_volume_ml": item.get("all_volume_ml"),
                "oedema_volume_ml": item.get("oedema_volume_ml"),
                "percent_change_from_baseline": item.get("cumulative_change_pct") or item.get("percent_change_from_baseline"),
                "percent_change_from_prior": item.get("interval_change_pct") or item.get("percent_change_from_prior"),
                "source_type": item.get("source_type"),
            }
            for item in payload["timeline"]
        ]
        compact = {
            "case_id": case_id,
            "risk_level": analysis.get("risk_level"),
            "risk_reason": analysis.get("risk_reason"),
            "baseline_total_ml": analysis.get("baseline_total_ml", analysis.get("baseline_volume_ml")),
            "latest_total_ml": analysis.get("latest_total_ml", analysis.get("latest_volume_ml")),
            "recent_segment_pct": analysis.get("recent_segment_pct", analysis.get("recent_interval_change_pct")),
            "delta_pct": analysis.get("delta_pct", analysis.get("cumulative_change_pct")),
            "points": points,
        }
        return ToolResult(success=True, output=json.dumps(compact, indent=2))


class RTTimelineAlignerTool:
    name = "rt_timeline_aligner"
    description = "Return a treatment-aligned timeline for the neuro review case, anchoring serial MRI studies to the radiotherapy event."
    parameters = {
        "case_id": {
            "type": "string",
            "description": "Optional neuro case id. Defaults to the current longitudinal neuro demo case.",
            "required": False,
        }
    }
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        payload = _build_neuro_workspace_payload({**args, "compact": False}, prefer_proteas=True)
        if payload is None:
            case_id = args.get("case_id") or demo_workspace_store.snapshot()["default_case_id"]
            payload = demo_workspace_store.get_case(case_id)
        case_id = payload["id"]
        events = payload.get("workflow", {}).get("events", [])
        rt_date = next((event.get("date") for event in events if event.get("label") == "Radiotherapy"), "N/A")
        timeline = [
            {
                "label": "Radiotherapy event",
                "date": rt_date,
                "type": "treatment",
            }
        ]
        timeline.extend(
            {
                "label": item["timepoint"],
                "date": item["study_date"],
                "type": "imaging",
                "sequence": item["sequence"],
            }
            for item in payload["timeline"]
        )
        return ToolResult(success=True, output=json.dumps({"case_id": case_id, "timeline": timeline}, indent=2))


class SlicePreviewRendererTool:
    name = "slice_preview_renderer"
    description = "Return the current preview image payload for the neuro review case, including caption and display title."
    parameters = {
        "case_id": {
            "type": "string",
            "description": "Optional neuro case id. Defaults to the current longitudinal neuro demo case.",
            "required": False,
        }
    }
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        payload = _build_neuro_workspace_payload({**args, "compact": False}, prefer_proteas=True)
        if payload is None:
            case_id = args.get("case_id") or demo_workspace_store.snapshot()["default_case_id"]
            payload = demo_workspace_store.get_case(case_id)
        case_id = payload["id"]
        compact = {
            "case_id": case_id,
            "preview": payload["imaging_preview"],
        }
        return ToolResult(success=True, output=json.dumps(compact, indent=2))


class LesionTrendPlotterTool:
    name = "lesion_trend_plotter"
    description = "Return the visual trend payload and headline metrics for a longitudinal neuro-oncology case."
    parameters = {
        "patient_id": {"type": "string", "description": "Optional PROTEAS patient id such as P28.", "required": False},
        "data_root": {"type": "string", "description": "Optional PROTEAS data root.", "required": False},
    }
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        payload = _build_neuro_workspace_payload({**args, "compact": False}, prefer_proteas=True)
        if payload is None:
            return ToolResult(success=False, output="", error=f"Configure {DEFAULT_NEURO_DATA_ENV} or pass data_root.")
        return ToolResult(
            success=True,
            output=json.dumps(
                {
                    "id": payload.get("id"),
                    "trend_svg": payload.get("visualizations", {}).get("trend_svg"),
                    "baseline_volume_ml": payload.get("analysis", {}).get("baseline_volume_ml"),
                    "latest_volume_ml": payload.get("analysis", {}).get("latest_volume_ml"),
                    "cumulative_change_pct": payload.get("analysis", {}).get("cumulative_change_pct"),
                    "risk_level": payload.get("analysis", {}).get("risk_level"),
                },
                indent=2,
            ),
        )


class TreatmentEventTimelineRendererTool:
    name = "treatment_event_timeline_renderer"
    description = "Return the treatment-aligned timeline visual and recorded clinical events for a longitudinal neuro case."
    parameters = {
        "patient_id": {"type": "string", "description": "Optional PROTEAS patient id such as P28.", "required": False},
        "data_root": {"type": "string", "description": "Optional PROTEAS data root.", "required": False},
    }
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        payload = _build_neuro_workspace_payload({**args, "compact": False}, prefer_proteas=True)
        if payload is None:
            return ToolResult(success=False, output="", error=f"Configure {DEFAULT_NEURO_DATA_ENV} or pass data_root.")
        return ToolResult(
            success=True,
            output=json.dumps(
                {
                    "id": payload.get("id"),
                    "timeline_svg": payload.get("visualizations", {}).get("timeline_svg"),
                    "events": payload.get("workflow", {}).get("events", []),
                    "timepoints": [
                        {"timepoint": item.get("timepoint"), "study_date": item.get("study_date")}
                        for item in payload.get("timeline", [])
                    ],
                },
                indent=2,
            ),
        )


class KeySliceSelectorTool:
    name = "key_slice_selector"
    description = "Return the key longitudinal checkpoints selected for representative comparison in a neuro longitudinal case."
    parameters = {
        "patient_id": {"type": "string", "description": "Optional PROTEAS patient id such as P28.", "required": False},
        "data_root": {"type": "string", "description": "Optional PROTEAS data root.", "required": False},
    }
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        payload = _build_neuro_workspace_payload({**args, "compact": False}, prefer_proteas=True)
        if payload is None:
            return ToolResult(success=False, output="", error=f"Configure {DEFAULT_NEURO_DATA_ENV} or pass data_root.")
        timeline = payload.get("timeline", [])
        if not timeline:
            selected = []
        else:
            selected = [timeline[0], timeline[len(timeline) // 2], timeline[-1]]
        return ToolResult(
            success=True,
            output=json.dumps(
                {
                    "id": payload.get("id"),
                    "selected_timepoints": [
                        {
                            "timepoint": item.get("timepoint"),
                            "study_date": item.get("study_date"),
                            "lesion_volume_ml": item.get("lesion_volume_ml"),
                            "mask_member": item.get("mask_member"),
                        }
                        for item in selected
                    ],
                },
                indent=2,
            ),
        )


class OverlayComposerTool:
    name = "overlay_composer"
    description = "Return the representative preview payload and mask references used for neuro image comparison."
    parameters = {
        "patient_id": {"type": "string", "description": "Optional PROTEAS patient id such as P28.", "required": False},
        "data_root": {"type": "string", "description": "Optional PROTEAS data root.", "required": False},
    }
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        payload = _build_neuro_workspace_payload({**args, "compact": False}, prefer_proteas=True)
        if payload is None:
            return ToolResult(success=False, output="", error=f"Configure {DEFAULT_NEURO_DATA_ENV} or pass data_root.")
        return ToolResult(
            success=True,
            output=json.dumps(
                {
                    "id": payload.get("id"),
                    "imaging_preview": payload.get("imaging_preview", {}),
                    "comparison_svg": payload.get("visualizations", {}).get("comparison_svg"),
                },
                indent=2,
            ),
        )


class LongitudinalComparisonPanelBuilderTool:
    name = "longitudinal_comparison_panel_builder"
    description = "Return the compact baseline-midpoint-latest comparison panel payload for a longitudinal neuro case."
    parameters = {
        "patient_id": {"type": "string", "description": "Optional PROTEAS patient id such as P28.", "required": False},
        "data_root": {"type": "string", "description": "Optional PROTEAS data root.", "required": False},
    }
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        payload = _build_neuro_workspace_payload({**args, "compact": False}, prefer_proteas=True)
        if payload is None:
            return ToolResult(success=False, output="", error=f"Configure {DEFAULT_NEURO_DATA_ENV} or pass data_root.")
        timeline = payload.get("timeline", [])
        selected = [timeline[0], timeline[len(timeline) // 2], timeline[-1]] if timeline else []
        return ToolResult(
            success=True,
            output=json.dumps(
                {
                    "id": payload.get("id"),
                    "comparison_svg": payload.get("visualizations", {}).get("comparison_svg"),
                    "panels": [
                        {
                            "timepoint": item.get("timepoint"),
                            "study_date": item.get("study_date"),
                            "lesion_volume_ml": item.get("lesion_volume_ml"),
                            "tumor_volume_ml": item.get("tumor_volume_ml"),
                        }
                        for item in selected
                    ],
                },
                indent=2,
            ),
        )


class RiskSignalRendererTool:
    name = "risk_signal_renderer"
    description = "Return the compact headline risk signal used in the neuro longitudinal review."
    parameters = {
        "patient_id": {"type": "string", "description": "Optional PROTEAS patient id such as P28.", "required": False},
        "data_root": {"type": "string", "description": "Optional PROTEAS data root.", "required": False},
    }
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        payload = _build_neuro_workspace_payload({**args, "compact": False}, prefer_proteas=True)
        if payload is None:
            return ToolResult(success=False, output="", error=f"Configure {DEFAULT_NEURO_DATA_ENV} or pass data_root.")
        analysis = payload.get("analysis", {})
        return ToolResult(
            success=True,
            output=json.dumps(
                {
                    "id": payload.get("id"),
                    "risk_level": analysis.get("risk_level"),
                    "response_label": analysis.get("response_label"),
                    "risk_reason": analysis.get("risk_reason"),
                    "baseline_volume_ml": analysis.get("baseline_volume_ml"),
                    "latest_volume_ml": analysis.get("latest_volume_ml"),
                    "recent_interval_change_pct": analysis.get("recent_interval_change_pct"),
                    "annualized_change_pct": analysis.get("annualized_change_pct"),
                },
                indent=2,
            ),
        )


class NeuroLongitudinalWorkspaceTool:
    name = "get_neuro_longitudinal_workspace"
    description = "Return a PROTEAS-backed longitudinal neuro-oncology workspace with timeline, response tracking, report, and visualizations."
    parameters = {
        "patient_id": {
            "type": "string",
            "description": "Optional PROTEAS patient id such as P28. Defaults to the main local longitudinal case.",
            "required": False,
        },
        "data_root": {
            "type": "string",
            "description": "Optional PROTEAS data root. Defaults to the configured local longitudinal data root.",
            "required": False,
        },
        "compact": {
            "type": "boolean",
            "description": "Return the compact presentation payload instead of the full workspace object.",
            "required": False,
        },
        "materialize_assets": {
            "type": "boolean",
            "description": "Write SVG visualization assets to the local derived output directory.",
            "required": False,
        },
    }
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        payload = _build_neuro_workspace_payload(args, prefer_proteas=True)
        if payload is None:
            return ToolResult(
                success=False,
                output="",
                error=(
                    f"Configure {DEFAULT_NEURO_DATA_ENV} or pass data_root to use the PROTEAS-backed neuro longitudinal workspace."
                ),
            )
        return ToolResult(success=True, output=json.dumps(payload, indent=2))


class NeuroLongitudinalVisualsTool:
    name = "get_neuro_longitudinal_visuals"
    description = "Return the SVG trend, timeline, and comparison visuals for the longitudinal neuro-oncology workspace."
    parameters = {
        "patient_id": {
            "type": "string",
            "description": "Optional PROTEAS patient id such as P28.",
            "required": False,
        },
        "data_root": {
            "type": "string",
            "description": "Optional PROTEAS data root.",
            "required": False,
        },
    }
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        payload = _build_neuro_workspace_payload({**args, "compact": False}, prefer_proteas=True)
        if payload is None:
            return ToolResult(
                success=False,
                output="",
                error=(
                    f"Configure {DEFAULT_NEURO_DATA_ENV} or pass data_root to render the longitudinal neuro visuals."
                ),
            )
        visualizations = payload.get("visualizations", {})
        output_root = payload.get("source", {}).get("output_root")
        patient_id = str(args.get("patient_id") or args.get("case_id") or payload.get("source", {}).get("patient_id") or "P28").strip().upper()
        asset_root = str(
            Path(output_root)
            if output_root
            else REPO_ROOT / ".clinicalclaw" / "derived" / "neuro_longitudinal" / patient_id
        )
        compact = {
            "id": payload.get("id"),
            "title": payload.get("title"),
            "dataset": payload.get("dataset"),
            "risk_level": payload.get("analysis", {}).get("risk_level"),
            "visualizations": visualizations,
            "asset_paths": {
                "trend_svg": f"{asset_root}/trend.svg",
                "timeline_svg": f"{asset_root}/timeline.svg",
                "comparison_svg": f"{asset_root}/comparison.svg",
            },
        }
        return ToolResult(success=True, output=json.dumps(compact, indent=2))


class NeuroLongitudinalSeriesCatalogTool:
    name = "get_neuro_longitudinal_series_catalog"
    description = "Return the series catalog and timepoint alignment for a PROTEAS-backed neuro longitudinal case."
    parameters = {
        "patient_id": {
            "type": "string",
            "description": "Optional PROTEAS patient id such as P28.",
            "required": False,
        },
        "data_root": {
            "type": "string",
            "description": "Optional PROTEAS data root.",
            "required": False,
        },
    }
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        payload = _build_neuro_workspace_payload({**args, "compact": False}, prefer_proteas=True)
        if payload is None:
            return ToolResult(
                success=False,
                output="",
                error=(
                    f"Configure {DEFAULT_NEURO_DATA_ENV} or pass data_root to inspect the longitudinal series catalog."
                ),
            )
        compact = {
            "id": payload.get("id"),
            "title": payload.get("title"),
            "patient": payload.get("patient"),
            "analysis": payload.get("analysis", {}),
            "timeline": payload.get("timeline", []),
            "series_catalog": payload.get("series_catalog", []),
            "radiomics": payload.get("radiomics", {}),
        }
        return ToolResult(success=True, output=json.dumps(compact, indent=2))


class FindingsWorkspaceTool:
    name = "get_findings_workspace"
    description = "Return the current findings closure workspace, including the lead finding, closure state, and recommended actions."
    parameters = {
        "case_id": {
            "type": "string",
            "description": "Optional findings case id. Defaults to the main critical-lab demo case.",
            "required": False,
        }
    }
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        case_id = args.get("case_id") or findings_closure_store.snapshot()["default_case_id"]
        payload = findings_closure_store.get_case(case_id)
        compact = {
            "id": payload["id"],
            "title": payload["title"],
            "workflow_title": payload["workflow_title"],
            "risk_label": payload["risk_label"],
            "risk_reason": payload["risk_reason"],
            "disposition": payload["disposition"],
            "focus_metric": payload["focus_metric"],
            "recommended_actions": payload["recommended_actions"],
            "evidence_grid": payload["evidence_grid"],
        }
        return ToolResult(success=True, output=json.dumps(compact, indent=2))


class QueueWorkspaceTool:
    name = "get_queue_workspace"
    description = "Return the current queue triage workspace, including urgency signal, queue recommendation, and recommended actions."
    parameters = {
        "case_id": {
            "type": "string",
            "description": "Optional queue case id. Defaults to the main referral triage demo case.",
            "required": False,
        }
    }
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        case_id = args.get("case_id") or queue_triage_store.snapshot()["default_case_id"]
        payload = queue_triage_store.get_case(case_id)
        compact = {
            "id": payload["id"],
            "title": payload["title"],
            "workflow_title": payload["workflow_title"],
            "risk_label": payload["risk_label"],
            "risk_reason": payload["risk_reason"],
            "disposition": payload["disposition"],
            "queue_recommendation": payload["queue_recommendation"],
            "focus_metric": payload["focus_metric"],
            "recommended_actions": payload["recommended_actions"],
            "evidence_grid": payload["evidence_grid"],
        }
        return ToolResult(success=True, output=json.dumps(compact, indent=2))


class DiagnosisWorkspaceTool:
    name = "get_diagnosis_workspace"
    description = "Return the current missed diagnosis workspace, including the gap signal, review recommendation, and key evidence."
    parameters = {
        "case_id": {
            "type": "string",
            "description": "Optional diagnosis case id. Defaults to the main missed vertebral fracture demo case.",
            "required": False,
        }
    }
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        case_id = args.get("case_id") or missed_diagnosis_store.snapshot()["default_case_id"]
        payload = missed_diagnosis_store.get_case(case_id)
        compact = {
            "id": payload["id"],
            "title": payload["title"],
            "workflow_title": payload["workflow_title"],
            "risk_label": payload["risk_label"],
            "risk_reason": payload["risk_reason"],
            "disposition": payload["disposition"],
            "gap_recommendation": payload["gap_recommendation"],
            "focus_metric": payload["focus_metric"],
            "recommended_actions": payload["recommended_actions"],
            "evidence_grid": payload["evidence_grid"],
        }
        return ToolResult(success=True, output=json.dumps(compact, indent=2))


class ScreeningWorkspaceTool:
    name = "get_screening_workspace"
    description = "Return the current screening gap workspace, including the gap signal, closure recommendation, and key evidence."
    parameters = {
        "case_id": {
            "type": "string",
            "description": "Optional screening case id. Defaults to the main positive FIT follow-up demo case.",
            "required": False,
        }
    }
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        case_id = args.get("case_id") or screening_gap_store.snapshot()["default_case_id"]
        payload = screening_gap_store.get_case(case_id)
        compact = {
            "id": payload["id"],
            "title": payload["title"],
            "workflow_title": payload["workflow_title"],
            "risk_label": payload["risk_label"],
            "risk_reason": payload["risk_reason"],
            "disposition": payload["disposition"],
            "gap_recommendation": payload["gap_recommendation"],
            "focus_metric": payload["focus_metric"],
            "recommended_actions": payload["recommended_actions"],
            "evidence_grid": payload["evidence_grid"],
        }
        return ToolResult(success=True, output=json.dumps(compact, indent=2))


class SafetyQueueTool:
    name = "get_safety_queue"
    description = "Return the current radiation safety queue summary and the incoming cases with risk tiers."
    parameters: dict[str, dict[str, Any]] = {}
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        payload = safety_monitor_store.snapshot()
        compact = {
            "queue_summary": payload["queue_summary"],
            "cases": payload["cases"],
        }
        return ToolResult(success=True, output=json.dumps(compact, indent=2))


class SafetyCaseTool:
    name = "get_safety_case"
    description = "Return a specific safety case with intake, top match, mitigation playbook, review questions, and review state."
    parameters = {
        "case_id": {
            "type": "string",
            "description": "Safety case id to inspect. Defaults to the first incoming case.",
            "required": False,
        }
    }
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        case_id = args.get("case_id") or safety_monitor_store.snapshot()["default_case_id"]
        payload = safety_monitor_store.get_case(case_id)
        compact = {
            "id": payload["id"],
            "title": payload["title"],
            "risk_label": payload["risk_label"],
            "risk_reason": payload["risk_reason"],
            "fields": payload["fields"],
            "playbook": payload["playbook"],
            "review_questions": payload["review_questions"],
            "matched_incidents": payload["matched_incidents"][:3],
            "review": payload["review"],
        }
        return ToolResult(success=True, output=json.dumps(compact, indent=2))


class SafetyKnowledgeSearchTool:
    name = "search_safety_knowledge"
    description = "Search the local radiation safety knowledge base for failure modes relevant to a query."
    parameters = {
        "query": {
            "type": "string",
            "description": "User query or short description of a safety concern.",
            "required": True,
        }
    }
    cacheable = True

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        query = (args.get("query") or "").lower()
        if not query:
            return ToolResult(success=False, output="", error="query is required")
        ranked: list[dict[str, Any]] = []
        for item in KNOWLEDGE_BASE:
            haystack = " ".join(
                [
                    item["title"],
                    item["summary"],
                    item["category"],
                    item["process_step"],
                    " ".join(item["signals"]),
                    " ".join(item["tags"]),
                ]
            ).lower()
            score = sum(1 for token in query.split() if token and token in haystack)
            if score:
                ranked.append(
                    {
                        "id": item["id"],
                        "title": item["title"],
                        "category": item["category"],
                        "process_step": item["process_step"],
                        "score": score,
                        "source": item["source"],
                    }
                )
        ranked.sort(key=lambda entry: entry["score"], reverse=True)
        return ToolResult(success=True, output=json.dumps(ranked[:5], indent=2))


def _extract_json(content: str) -> dict[str, Any] | None:
    text = content.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


async def route_with_llm(llm: LLMProvider, message: str) -> dict[str, Any]:
    ranked = rank_workflows(message)
    heuristic_alternatives = [
        {"module": item["module"], "title": item["workflow"]["title"], "score": item["score"]}
        for item in ranked
        if item["score"] > 0
    ]
    system_prompt = (
        "You are the ClinicalClaw router. "
        "Classify the user's request into one workflow_id from "
        "general_chat, findings_closure, queue_triage, missed_diagnosis_detection, screening_gap_closure, neuro_longitudinal, radiation_safety_monitor. "
        "Return strict JSON with keys: workflow_id, confidence, reason, next_action, alternatives. "
        "alternatives must be an array of 0-2 workflow_id values that are also plausible. "
        "If uncertain, choose general_chat."
    )
    user_prompt = (
        "User request:\n"
        f"{message}\n\n"
        "Workflow boundaries:\n"
        "- neuro_longitudinal: brain MRI follow-up, longitudinal tumor review, brain metastasis response, treatment response, progression, tumor-board brief\n"
        "- findings_closure: critical lab, positive result follow-up, actionable report finding, abnormal pap, suspicious nodule\n"
        "- queue_triage: referral urgency, queue reprioritization, post-discharge follow-up triage, same-day review, outreach queue\n"
        "- missed_diagnosis_detection: missed fracture workup, vertebral fracture gap, unrecognized condition, undiagnosed condition\n"
        "- screening_gap_closure: screening follow-up gap, positive FIT, overdue colonoscopy, preventive care gap, open screening follow-up\n"
        "- radiation_safety_monitor: incident, QA, alert, radiation, dosimetry, timeout, adaptive planning\n"
        "- general_chat: anything else or uncertain\n"
    )
    try:
        response = await llm.chat(
            [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt),
            ]
        )
        parsed = _extract_json(response.content)
        if parsed and parsed.get("workflow_id") in {
            "general_chat",
            "findings_closure",
            "queue_triage",
            "missed_diagnosis_detection",
            "screening_gap_closure",
            "neuro_longitudinal",
            "radiation_safety_monitor",
        }:
            workflow_id = parsed["workflow_id"]
            module_map = {
                "general_chat": "home",
                "findings_closure": "findings",
                "queue_triage": "queue",
                "missed_diagnosis_detection": "diagnosis",
                "screening_gap_closure": "screening",
                "neuro_longitudinal": "neuro",
                "radiation_safety_monitor": "safety",
            }
            workflow = next(item for item in WORKFLOWS if item["id"] == workflow_id)
            confidence = float(parsed.get("confidence", 0.0) or 0.0)
            suggested_module = module_map[workflow_id] if workflow_id != "general_chat" else None
            target_module = module_map[workflow_id]
            if workflow_id != "general_chat" and confidence < 0.6:
                target_module = "home"
            parsed_alternatives = parsed.get("alternatives") or []
            alternatives = []
            for alt in parsed_alternatives:
                if alt in {"general_chat", "findings_closure", "queue_triage", "missed_diagnosis_detection", "screening_gap_closure", "neuro_longitudinal", "radiation_safety_monitor"} and alt != workflow_id:
                    alt_wf = next(item for item in WORKFLOWS if item["id"] == alt)
                    alternatives.append({"module": alt_wf["module"], "title": alt_wf["title"]})
            if not alternatives:
                alternatives = [
                    {"module": item["module"], "title": item["title"]}
                    for item in heuristic_alternatives
                    if item["module"] != suggested_module
                ][:2]
            return {
                "workflow_id": workflow_id,
                "workflow": workflow,
                "target_module": target_module,
                "suggested_module": suggested_module,
                "confidence": confidence,
                "reason": parsed.get("reason", "Router selected the closest workflow."),
                "next_action": parsed.get("next_action", "Open the selected module."),
                "alternatives": alternatives,
                "fallback": False,
            }
    except Exception:
        pass

    fallback = route_general_query(message)
    workflow = fallback["workflow"]
    return {
        "workflow_id": workflow["id"],
        "workflow": workflow,
        "target_module": fallback["target_module"],
        "suggested_module": fallback["target_module"] if fallback["target_module"] != "home" else None,
        "confidence": 0.0,
        "reason": fallback["assistant"]["content"],
        "next_action": "Use the recommended workflow or stay in general chat.",
        "alternatives": [
            {"module": item["module"], "title": item["title"]}
            for item in fallback.get("alternatives", [])
        ],
        "fallback": True,
    }


def build_console_agent(llm: LLMProvider):
    tools = [
        WorkflowCatalogTool(),
        FindingsWorkspaceTool(),
        QueueWorkspaceTool(),
        DiagnosisWorkspaceTool(),
        ScreeningWorkspaceTool(),
        NeuroWorkspaceTool(),
        NeuroLongitudinalWorkspaceTool(),
        NeuroLongitudinalVisualsTool(),
        NeuroLongitudinalSeriesCatalogTool(),
        DicomSeriesSelectorTool(),
        BrainMetResponseTrackerTool(),
        RTTimelineAlignerTool(),
        SlicePreviewRendererTool(),
        LesionTrendPlotterTool(),
        TreatmentEventTimelineRendererTool(),
        KeySliceSelectorTool(),
        OverlayComposerTool(),
        LongitudinalComparisonPanelBuilderTool(),
        RiskSignalRendererTool(),
        SafetyQueueTool(),
        SafetyCaseTool(),
        SafetyKnowledgeSearchTool(),
    ]
    instruction = (
        "You are the ClinicalClaw console agent. "
        "Help the user accomplish clinical workflow tasks using the available tools. "
        "Be concise, grounded, and operational. "
        "Before producing any user-facing report, summary, or polished chat answer, you must first call "
        "use_skill for the required presentation skill or skills. "
        "Always load clinical_report_presentation first. "
        "If the workflow is findings_closure, also load findings_brief_presenter. "
        "If the workflow is queue_triage, also load queue_triage_presenter. "
        "If the workflow is missed_diagnosis_detection, also load missed_diagnosis_presenter. "
        "If the workflow is screening_gap_closure, also load screening_gap_presenter. "
        "If the workflow is neuro_longitudinal, also load neuro_report_presenter and use the longitudinal neuro tools to inspect series selection, risk signal, trend, timeline, and preview assets. "
        "If the workflow is radiation_safety_monitor, also load safety_brief_presenter. "
        "Silently organize your facts before writing, but never reveal hidden planning or chain-of-thought. "
        "For neuro requests, inspect the neuro workspace before answering. "
        "For findings-closure requests, inspect the findings workspace before answering. "
        "For queue triage requests, inspect the queue workspace before answering. "
        "For missed diagnosis requests, inspect the diagnosis workspace before answering. "
        "For screening gap requests, inspect the screening workspace before answering. "
        "For safety requests, inspect the safety queue or a safety case before answering. "
        "Do not invent patient data or incident details. "
        "Do not expose internal tool names or routing details in the final answer. "
        "Summarize what you found and recommend the next action clearly."
    )
    agent = create_claw_agent(
        model=llm,
        instruction=instruction,
        tools=tools,
        skills=[SKILLS_DIR],
        streaming=True,
    )
    agent.allow_only_tools(
        "think",
        "write_todos",
        "update_todo",
        "list_skills",
        "use_skill",
        "workflow_catalog",
        "get_findings_workspace",
        "get_queue_workspace",
        "get_diagnosis_workspace",
        "get_screening_workspace",
        "get_neuro_workspace",
        "get_neuro_longitudinal_workspace",
        "get_neuro_longitudinal_visuals",
        "get_neuro_longitudinal_series_catalog",
        "dicom_series_selector",
        "brain_met_response_tracker",
        "rt_timeline_aligner",
        "slice_preview_renderer",
        "lesion_trend_plotter",
        "treatment_event_timeline_renderer",
        "key_slice_selector",
        "overlay_composer",
        "longitudinal_comparison_panel_builder",
        "risk_signal_renderer",
        "get_safety_queue",
        "get_safety_case",
        "search_safety_knowledge",
    )
    return agent


def build_routed_task(route: dict[str, Any], message: str) -> str:
    workflow_id = route["workflow_id"]
    if workflow_id == "findings_closure":
        return (
            "Workflow: findings_closure\n"
            "Required pre-answer tool calls:\n"
            "1. use_skill(name='clinical_report_presentation')\n"
            "2. use_skill(name='findings_brief_presenter')\n"
            "Use the findings workspace tool to inspect the current case before answering.\n"
            "Present the final answer as a polished findings closure brief with sections for Finding Summary, "
            "Closure Check, Recommended Next Step, and Review Status.\n"
            f"User request: {message}"
        )
    if workflow_id == "queue_triage":
        return (
            "Workflow: queue_triage\n"
            "Required pre-answer tool calls:\n"
            "1. use_skill(name='clinical_report_presentation')\n"
            "2. use_skill(name='queue_triage_presenter')\n"
            "Use the queue workspace tool to inspect the current case before answering.\n"
            "Present the final answer as a compact triage brief with sections for Queue Signal, Priority Shift, "
            "Recommended Queue Move, and Review Status.\n"
            f"User request: {message}"
        )
    if workflow_id == "missed_diagnosis_detection":
        return (
            "Workflow: missed_diagnosis_detection\n"
            "Required pre-answer tool calls:\n"
            "1. use_skill(name='clinical_report_presentation')\n"
            "2. use_skill(name='missed_diagnosis_presenter')\n"
            "Use the diagnosis workspace tool to inspect the current case before answering.\n"
            "Present the final answer as a compact missed-diagnosis brief with sections for Gap Signal, "
            "Follow-up Check, Recommended Workup, and Review Status.\n"
            f"User request: {message}"
        )
    if workflow_id == "screening_gap_closure":
        return (
            "Workflow: screening_gap_closure\n"
            "Required pre-answer tool calls:\n"
            "1. use_skill(name='clinical_report_presentation')\n"
            "2. use_skill(name='screening_gap_presenter')\n"
            "Use the screening workspace tool to inspect the current case before answering.\n"
            "Present the final answer as a compact screening-gap brief with sections for Screening Signal, "
            "Gap Check, Recommended Next Step, and Review Status.\n"
            f"User request: {message}"
        )
    if workflow_id == "neuro_longitudinal":
        return (
            "Workflow: neuro_longitudinal\n"
            "Required pre-answer tool calls:\n"
            "1. use_skill(name='clinical_report_presentation')\n"
            "2. use_skill(name='neuro_report_presenter')\n"
            "Use the neuro longitudinal workspace tools to inspect the case before answering.\n"
            "Present the final answer as a polished clinician-facing markdown brief with sections for Timeline, "
            "Trend Interpretation, Imaging Context, Recommendations, and a one-line Risk Tier.\n"
            f"User request: {message}"
        )
    if workflow_id == "radiation_safety_monitor":
        return (
            "Workflow: radiation_safety_monitor\n"
            "Required pre-answer tool calls:\n"
            "1. use_skill(name='clinical_report_presentation')\n"
            "2. use_skill(name='safety_brief_presenter')\n"
            "Use the safety queue and safety case tools before answering. "
            "If incident pattern matching is relevant, search the local safety knowledge base.\n"
            "Present the final answer as a polished clinical operations brief with sections for Risk Summary, "
            "Matched Failure Patterns, Recommended Checks, and a one-line Escalation.\n"
            f"User request: {message}"
        )
    return (
        "Workflow: general_chat\n"
        "Use the clinical_report_presentation skill before the final answer.\n"
        "Use the workflow catalog and any relevant module tool if it helps clarify the user's request.\n"
        "Keep the final answer concise and product-ready, without exposing internal tool or routing names.\n"
        f"User request: {message}"
    )
