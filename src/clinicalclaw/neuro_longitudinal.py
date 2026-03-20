from __future__ import annotations

import base64
import gzip
import io
import math
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any

from pydantic import BaseModel, Field


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _title_case(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").title()


def _slugify(value: str) -> str:
    lowered = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return lowered or "item"


def _canonical_timepoint(token: str) -> str:
    lowered = token.strip().lower()
    if lowered in {"baseline", "base", "bl"}:
        return "baseline"
    match = re.search(r"(?:follow[_ -]?up[_ -]?|fu)(\d+)", lowered)
    if match:
        return f"fu{int(match.group(1))}"
    return _slugify(lowered)


def _timepoint_sort_key(token: str) -> tuple[int, int]:
    canonical = _canonical_timepoint(token)
    if canonical == "baseline":
        return (0, 0)
    match = re.match(r"fu(\d+)", canonical)
    if match:
        return (1, int(match.group(1)))
    return (2, 0)


def _excel_date_to_iso(value: Any) -> str:
    if value in {"", None, "N/A"}:
        return "N/A"
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return "N/A"
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return text
        for fmt in ("%m/%d/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                continue
        number = _safe_float(text)
        if number is None:
            return text
        value = number
    if isinstance(value, (int, float)):
        base = datetime(1899, 12, 30)
        return (base + timedelta(days=float(value))).date().isoformat()
    return str(value)


def _data_roots() -> list[Path]:
    roots: list[Path] = []
    env_root = os.getenv("CLINICALCLAW_NEURO_DEMO_ROOT", "").strip()
    if env_root:
        roots.append(Path(env_root).expanduser())
    repo_root = Path(__file__).resolve().parents[2]
    roots.append(repo_root / ".clinicalclaw" / "demo_data" / "proteas")
    return roots


@dataclass(frozen=True)
class NeuroTimelinePoint:
    study_id: str
    study_date: str
    timepoint: str
    sequence: str
    lesion_volume_ml: float
    enhancing_volume_ml: float | None
    edema_volume_ml: float | None
    interval_days: int | None
    percent_change_from_baseline: float
    percent_change_from_prior: float | None
    source_type: str


class NeuroMessage(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


class NeuroReviewState(BaseModel):
    status: str = "in_review"
    reviewer: str = "Neuro-oncology reviewer"
    comment: str = "Awaiting physician review."
    updated_at: str = Field(default_factory=_utc_now_iso)


class NeuroAuditEvent(BaseModel):
    id: str
    title: str
    detail: str
    severity: str = "info"
    created_at: str = Field(default_factory=_utc_now_iso)


class _XlsxReader:
    NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"

    def __init__(self, path: Path):
        self.path = path

    def iter_sheets(self) -> list[tuple[str, list[list[str]]]]:
        with zipfile.ZipFile(self.path) as archive:
            shared = self._read_shared_strings(archive)
            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            relmap = {
                rel.attrib["Id"]: rel.attrib["Target"]
                for rel in rels.findall(f"{self.REL_NS}Relationship")
            }
            sheets = workbook.find(f"{self.NS}sheets")
            if sheets is None:
                return []
            payload: list[tuple[str, list[list[str]]]] = []
            for sheet in sheets:
                name = sheet.attrib.get("name", "")
                rid = sheet.attrib.get(
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id",
                    "",
                )
                target = relmap.get(rid)
                if not target:
                    continue
                root = ET.fromstring(archive.read(f"xl/{target}"))
                payload.append((name, self._read_sheet_rows(root, shared)))
            return payload

    def _read_shared_strings(self, archive: zipfile.ZipFile) -> list[str]:
        if "xl/sharedStrings.xml" not in archive.namelist():
            return []
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        values: list[str] = []
        for item in root.findall(f"{self.NS}si"):
            parts = [node.text or "" for node in item.iterfind(f".//{self.NS}t")]
            values.append("".join(parts))
        return values

    def _read_sheet_rows(self, root: ET.Element, shared: list[str]) -> list[list[str]]:
        rows: list[list[str]] = []
        for row in root.iterfind(f".//{self.NS}sheetData/{self.NS}row"):
            current: list[str] = []
            for cell in row.findall(f"{self.NS}c"):
                cell_type = cell.attrib.get("t")
                value = cell.find(f"{self.NS}v")
                if value is None:
                    current.append("")
                elif cell_type == "s":
                    current.append(shared[int(value.text)])
                else:
                    current.append(value.text or "")
            rows.append(current)
        return rows


class ProteasDataset:
    def __init__(self, root: Path):
        self.root = root
        self.clinical_path = root / "PROTEAS-Clinical_and_demographic_data.xlsx"
        self.radiomics_path = root / "PROTEAS-MRI_radiomics_data.xlsx"

    @classmethod
    def discover(cls) -> "ProteasDataset | None":
        for root in _data_roots():
            if not root.exists():
                continue
            if (root / "PROTEAS-Clinical_and_demographic_data.xlsx").exists() and (
                root / "PROTEAS-MRI_radiomics_data.xlsx"
            ).exists():
                return cls(root)
        return None

    def list_available_cases(self) -> list[str]:
        return sorted(
            path.stem
            for path in self.root.glob("P*.zip")
            if path.is_file()
        )

    def build_case_workspace(self, case_id: str) -> dict[str, Any]:
        clinical = self._load_clinical_row(case_id)
        zip_path = self.root / f"{case_id}.zip"
        if not zip_path.exists():
            raise KeyError(case_id)
        zip_index = self._read_zip_index(zip_path, case_id)
        timeline = self._build_timeline(case_id, clinical, zip_index)
        preview_url = self._build_preview_data_url(case_id, timeline)
        workflow = self._build_workflow(timeline)
        analysis = self._build_analysis(case_id, clinical, timeline)
        report = self._build_report(case_id, clinical, timeline, analysis)
        patient = self._build_patient_summary(case_id, clinical, zip_index)
        return {
            "id": f"proteas-{case_id.lower()}",
            "title": f"PROTEAS longitudinal response review",
            "dataset": "PROTEAS brain metastasis longitudinal dataset",
            "patient": patient,
            "timeline": [point.__dict__ for point in timeline],
            "analysis": analysis,
            "workflow": workflow,
            "imaging_preview": {
                "title": "Representative longitudinal lesion preview",
                "caption": "Prototype visual derived from longitudinal lesion burden and review timeline.",
                "image_url": preview_url,
            },
            "report": report,
            "review": NeuroReviewState().model_dump(),
            "messages": [
                NeuroMessage(
                    id="msg_intro_1",
                    role="assistant",
                    content=(
                        "This workspace reviews a longitudinal neuro-oncology case across serial MRI follow-up. "
                        "Ask for a response summary, explain the current risk signal, or request a tumor-board brief."
                    ),
                    created_at=_utc_now_iso(),
                ).model_dump()
            ],
            "uploads": [],
            "audit": [
                NeuroAuditEvent(
                    id="audit_seed_1",
                    title="Dataset loaded",
                    detail=f"Loaded longitudinal PROTEAS case {case_id} with imaging, timing, and clinical metadata.",
                ).model_dump(),
                NeuroAuditEvent(
                    id="audit_seed_2",
                    title="Longitudinal response review prepared",
                    detail="Generated longitudinal burden trend, treatment-aligned timeline, and clinician-facing brief.",
                ).model_dump(),
            ],
        }

    def _load_clinical_row(self, case_id: str) -> dict[str, str]:
        reader = _XlsxReader(self.clinical_path)
        sheets = reader.iter_sheets()
        if not sheets:
            raise KeyError("clinical_sheet")
        _, rows = sheets[0]
        header = rows[0]
        for row in rows[1:]:
            if row and row[0] == case_id:
                return {
                    header[index]: row[index] if index < len(row) else ""
                    for index in range(len(header))
                }
        raise KeyError(case_id)

    def _read_zip_index(self, zip_path: Path, patient_id: str) -> dict[str, Any]:
        with zipfile.ZipFile(zip_path) as archive:
            names = archive.namelist()
        brats: dict[str, list[str]] = {}
        dicom: dict[str, list[str]] = {}
        masks: dict[str, str] = {}
        for name in names:
            brats_match = re.match(rf"{patient_id}/BraTS/([^/]+)/([^/]+)$", name)
            if brats_match:
                brats.setdefault(_canonical_timepoint(brats_match.group(1)), []).append(brats_match.group(2))
            dicom_match = re.match(rf"{patient_id}/DICOM/([^/]+)/", name)
            if dicom_match:
                series = dicom_match.group(1)
                date_match = re.search(r"(\d{4}-\d{2}-\d{2}|\d{4}_\d{2}_\d{2})", series)
                if date_match:
                    token = date_match.group(1).replace("_", "-")
                    dicom.setdefault(token, []).append(series)
            mask_match = re.match(rf"{patient_id}/tumor[_ ]segmentation/{patient_id}_tumor_mask_([^/]+)\.nii\.gz$", name)
            if mask_match:
                masks[_canonical_timepoint(mask_match.group(1))] = name
        return {"brats": brats, "dicom": dicom, "masks": masks}

    def _parse_radiomics_sheet(self, case_id: str) -> list[tuple[str, str]]:
        reader = _XlsxReader(self.radiomics_path)
        for name, rows in reader.iter_sheets():
            if name != case_id or len(rows) < 2:
                continue
            return [(row[0], row[1]) for row in rows[1:] if len(row) >= 2]
        return []

    def _extract_volume_series(self, case_id: str) -> dict[str, dict[str, float]]:
        entries = self._parse_radiomics_sheet(case_id)
        metrics: dict[str, dict[str, float]] = {}
        pattern = re.compile(
            r"^mask_(?P<mask>all|tumor|oedema|necrosis)__"
            r"(?P<modality>t1c|t1|t2|fla)__"
            r"(?P<timepoint>[^_]+(?:_[^_]+)?)__"
            r"original_shape_(?P<feature>MeshVolume|VoxelVolume|Maximum3DDiameter)$",
            re.IGNORECASE,
        )
        for feature_name, raw_value in entries:
            match = pattern.match(feature_name)
            if not match:
                continue
            value = _safe_float(raw_value)
            if value is None:
                continue
            modality = match.group("modality").lower()
            if modality != "t1c":
                continue
            timepoint = _canonical_timepoint(match.group("timepoint"))
            mask_name = match.group("mask").lower()
            feature = match.group("feature")
            bucket = metrics.setdefault(timepoint, {})
            key = f"{mask_name}_{feature}"
            bucket[key] = value
        return metrics

    def _build_timeline(
        self,
        case_id: str,
        clinical: dict[str, str],
        zip_index: dict[str, Any],
    ) -> list[NeuroTimelinePoint]:
        volume_series = self._extract_volume_series(case_id)
        date_map = {
            "baseline": _excel_date_to_iso(clinical.get("Brain Mets Imaging Date")),
            "fu1": self._first_date(zip_index, 1),
            "fu2": self._first_date(zip_index, 2),
            "fu3": self._first_date(zip_index, 3),
            "fu4": self._first_date(zip_index, 4),
            "fu5": self._first_date(zip_index, 5),
        }
        points: list[NeuroTimelinePoint] = []
        baseline_volume = None
        previous_volume = None
        previous_date = None
        for timepoint in sorted(volume_series, key=_timepoint_sort_key):
            metrics = volume_series[timepoint]
            mask_member = zip_index["masks"].get(timepoint)
            lesion_volume = self._mask_volume_mm3(case_id, mask_member)
            if lesion_volume is None:
                lesion_volume = metrics.get("all_MeshVolume") or metrics.get("tumor_MeshVolume") or 0.0
            if baseline_volume is None:
                baseline_volume = lesion_volume or 1.0
            current_date = date_map.get(timepoint) or "N/A"
            interval_days = None
            if previous_date and current_date != "N/A":
                try:
                    interval_days = (
                        datetime.fromisoformat(current_date) - datetime.fromisoformat(previous_date)
                    ).days
                except ValueError:
                    interval_days = None
            percent_change_from_baseline = round(((lesion_volume - baseline_volume) / max(baseline_volume, 0.001)) * 100, 1)
            percent_change_from_prior = None
            if previous_volume is not None:
                percent_change_from_prior = round(
                    ((lesion_volume - previous_volume) / max(previous_volume, 0.001)) * 100,
                    1,
                )
            points.append(
                NeuroTimelinePoint(
                    study_id=f"{case_id.lower()}-{timepoint}",
                    study_date=current_date,
                    timepoint=timepoint,
                    sequence=self._preferred_series_label(timepoint, zip_index),
                    lesion_volume_ml=round(lesion_volume / 1000.0, 2),
                    enhancing_volume_ml=self._as_ml(metrics.get("tumor_MeshVolume")),
                    edema_volume_ml=self._as_ml(metrics.get("oedema_MeshVolume")),
                    interval_days=interval_days,
                    percent_change_from_baseline=percent_change_from_baseline,
                    percent_change_from_prior=percent_change_from_prior,
                    source_type="radiomics_t1c_mesh_volume",
                )
            )
            previous_volume = lesion_volume
            previous_date = current_date if current_date != "N/A" else previous_date
        return points

    def _first_date(self, zip_index: dict[str, Any], follow_up_number: int) -> str:
        dates = sorted(zip_index["dicom"].keys())
        if follow_up_number - 1 < len(dates):
            return dates[follow_up_number - 1]
        return "N/A"

    def _preferred_series_label(self, timepoint: str, zip_index: dict[str, Any]) -> str:
        if timepoint == "baseline":
            date = self._first_date(zip_index, 1)
        else:
            match = re.match(r"fu(\d+)", timepoint)
            date = self._first_date(zip_index, int(match.group(1))) if match else "N/A"
        candidates = zip_index["dicom"].get(date, [])
        for prefix in ("T1C_HR", "T1C", "FLR_HR", "FLR", "T1W", "T2W"):
            for series in candidates:
                if series.startswith(prefix):
                    return prefix.replace("_", " ")
        return "T1C"

    def _as_ml(self, value: float | None) -> float | None:
        if value is None:
            return None
        return round(value / 1000.0, 2)

    def _build_patient_summary(self, case_id: str, clinical: dict[str, str], zip_index: dict[str, Any]) -> dict[str, Any]:
        age = _safe_int(clinical.get("Age (yrs)")) or 0
        lesion_count = clinical.get("Number of metastases") or "N/A"
        intervention = clinical.get("Type & characteristics of intervention") or "Not specified"
        location = clinical.get("Lesion(s) location") or "Not specified"
        return {
            "id": case_id,
            "display_name": f"Subject {case_id}",
            "sex": clinical.get("Gender") or "Unknown",
            "age": age,
            "diagnosis": f"Brain metastasis follow-up ({clinical.get('Tumour Histology ', 'Unknown histology')})",
            "mrn": f"PROTEAS-{case_id}",
            "summary": (
                f"{len(zip_index['brats'])} MRI follow-up points with {lesion_count} documented metastasis"
                f"{'' if lesion_count == '1' else 'es'}, primary histology {clinical.get('Tumour Histology ', 'unknown')}, "
                f"and prior intervention {intervention}."
            ),
            "histology": clinical.get("Tumour Histology ") or "Unknown",
            "intervention": intervention,
            "lesion_location": location,
            "metastasis_count": lesion_count,
            "karnofsky": clinical.get("Karnofsky PS (%)") or "N/A",
            "who_ps": clinical.get("WHO PS") or "N/A",
        }

    def _build_analysis(self, case_id: str, clinical: dict[str, str], timeline: list[NeuroTimelinePoint]) -> dict[str, Any]:
        baseline = timeline[0]
        latest = timeline[-1]
        previous = timeline[-2] if len(timeline) > 1 else timeline[-1]
        latest_change = latest.percent_change_from_prior or 0.0
        total_change = latest.percent_change_from_baseline
        duration_days = self._days_between(baseline.study_date, latest.study_date)
        annualized = round(total_change / max(duration_days / 365.25, 0.25), 1) if duration_days else total_change
        progressive = latest_change > 10 or total_change > 20
        risk_level = "Progressive" if progressive else "Watch" if latest_change > 0 else "Stable"
        risk_reason = (
            "The latest interval shows lesion growth compared with the prior follow-up and keeps the post-treatment case in a high-attention lane."
            if progressive
            else "The lesion burden remains under active review; current interval change is limited but still requires follow-up correlation."
        )
        return {
            "structure": "Treated brain metastasis",
            "baseline_total_ml": baseline.lesion_volume_ml,
            "latest_total_ml": latest.lesion_volume_ml,
            "previous_total_ml": previous.lesion_volume_ml,
            "annual_change_pct": annualized,
            "recent_segment_pct": latest_change,
            "delta_pct": total_change,
            "recent_delta_vs_overall_pct": round(latest_change - annualized, 1),
            "accelerated_decline": False,
            "accelerated_progression": progressive,
            "risk_level": risk_level,
            "risk_reason": risk_reason,
            "next_checks": [
                "Review the latest contrast-enhancing burden against the post-radiotherapy baseline.",
                "Correlate interval change with symptoms, steroid use, and systemic disease status.",
                "Confirm whether the next tumor-board or follow-up MRI interval should be shortened.",
            ],
            "days_since_baseline": duration_days,
            "lesion_count": clinical.get("Number of metastases") or "N/A",
            "rt_event_date": self._find_rt_event(case_id),
        }

    def _find_rt_event(self, case_id: str) -> str:
        zip_path = self.root / f"{case_id}.zip"
        with zipfile.ZipFile(zip_path) as archive:
            names = archive.namelist()
        for name in names:
            match = re.match(rf"{case_id}/DICOM/RTP_(\d{{4}}[-_]\d{{2}}[-_]\d{{2}})", name)
            if match:
                return match.group(1).replace("_", "-")
        return "N/A"

    def _build_workflow(self, timeline: list[NeuroTimelinePoint]) -> dict[str, Any]:
        return {
            "title": "Post-radiotherapy longitudinal response review",
            "status": "ready_for_review",
            "objective": (
                "Align serial brain MRI studies, quantify lesion burden change across time, place the radiotherapy event on the timeline, "
                "and prepare a concise neuro-oncology follow-up brief."
            ),
            "last_run_at": _utc_now_iso(),
            "steps": [
                {
                    "name": "Select the longitudinal MRI series",
                    "tool": "dicom_series_selector",
                    "status": "completed",
                    "detail": f"Selected a contrast-enhanced longitudinal sequence across {len(timeline)} timepoints.",
                },
                {
                    "name": "Align the treatment timeline",
                    "tool": "rt_timeline_aligner",
                    "status": "completed",
                    "detail": "Inserted the radiotherapy event and linked follow-up imaging intervals to the treatment anchor.",
                },
                {
                    "name": "Measure longitudinal lesion response",
                    "tool": "brain_met_response_tracker",
                    "status": "completed",
                    "detail": "Computed lesion burden change, interval deltas, and the current progression signal.",
                },
                {
                    "name": "Prepare the review brief and visuals",
                    "tool": "neuro_oncology_brief_presenter",
                    "status": "completed",
                    "detail": "Generated a concise physician-facing summary, timeline cards, and visualization-ready metrics.",
                },
            ],
        }

    def _build_report(
        self,
        case_id: str,
        clinical: dict[str, str],
        timeline: list[NeuroTimelinePoint],
        analysis: dict[str, Any],
    ) -> dict[str, Any]:
        baseline = timeline[0]
        latest = timeline[-1]
        duration_months = round((analysis["days_since_baseline"] or 0) / 30.4)
        return {
            "title": "AI longitudinal brain metastasis review",
            "subtitle": "Prototype physician-facing follow-up brief",
            "risk_level": analysis["risk_level"],
            "summary": (
                f"Serial post-treatment MRI review for {case_id} shows lesion burden change from {baseline.lesion_volume_ml:.2f} mL "
                f"at baseline to {latest.lesion_volume_ml:.2f} mL at the latest follow-up across approximately {duration_months} months. "
                f"Current status is {analysis['risk_level'].lower()} with interval change of {analysis['recent_segment_pct']}%."
            ),
            "sections": [
                {
                    "title": "Review context",
                    "body": (
                        f"{clinical.get('Tumour Histology ', 'Unknown histology')} with {clinical.get('Number of metastases', 'N/A')} documented metastasis"
                        f"{'' if clinical.get('Number of metastases') == '1' else 'es'}, lesion location {clinical.get('Lesion(s) location', 'not specified')}, "
                        f"and intervention {clinical.get('Type & characteristics of intervention', 'not specified')}."
                    ),
                },
                {
                    "title": "Longitudinal burden change",
                    "body": (
                        f"Lesion burden changed by {analysis['delta_pct']}% from baseline. The most recent interval changed by "
                        f"{analysis['recent_segment_pct']}% compared with the prior follow-up."
                    ),
                },
                {
                    "title": "Treatment-aligned interpretation",
                    "body": (
                        f"Radiotherapy is anchored at {analysis['rt_event_date']}. The review focuses on post-treatment response over serial "
                        "contrast-enhanced MRI follow-up rather than single-timepoint interpretation."
                    ),
                },
                {
                    "title": "Clinical attention level",
                    "body": analysis["risk_reason"],
                },
            ],
            "physician_questions": [
                "Does the latest interval change match the clinical symptom trajectory?",
                "Is the current appearance more concerning for progression, mixed response, or treatment effect?",
                "Should the next follow-up MRI or multidisciplinary review be accelerated?",
            ],
        }

    def _days_between(self, first: str, second: str) -> int | None:
        try:
            return (datetime.fromisoformat(second) - datetime.fromisoformat(first)).days
        except ValueError:
            return None

    def _build_preview_data_url(self, case_id: str, timeline: list[NeuroTimelinePoint]) -> str:
        real_preview = self._build_real_preview_data_url(case_id)
        if real_preview:
            return real_preview

        width = 720
        height = 400
        left = 72
        top = 64
        chart_width = 288
        chart_height = 168
        values = [point.lesion_volume_ml for point in timeline]
        low = min(values) * 0.9
        high = max(values) * 1.1 if max(values) > min(values) else min(values) + 1
        points = []
        for index, point in enumerate(timeline):
            x = left + (index / max(len(timeline) - 1, 1)) * chart_width
            ratio = (point.lesion_volume_ml - low) / max(high - low, 0.001)
            y = top + chart_height - ratio * chart_height
            points.append((x, y, point))
        path = " ".join(
            f"{'M' if idx == 0 else 'L'} {x:.1f} {y:.1f}"
            for idx, (x, y, _) in enumerate(points)
        )
        baseline = timeline[0].lesion_volume_ml
        latest = timeline[-1].lesion_volume_ml
        circle_radius = 24 + min(latest * 6.5, 78)
        circle_radius_base = 24 + min(baseline * 6.5, 78)
        latest_change = timeline[-1].percent_change_from_prior or 0.0
        svg = f"""
        <svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
          <defs>
            <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="#f8fbfd"/>
              <stop offset="100%" stop-color="#eef4f8"/>
            </linearGradient>
            <linearGradient id="lesion" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="#ff8a7a" stop-opacity="0.95"/>
              <stop offset="100%" stop-color="#d9475b" stop-opacity="0.88"/>
            </linearGradient>
          </defs>
          <rect width="{width}" height="{height}" rx="28" fill="url(#bg)"/>
          <text x="70" y="42" font-size="18" font-family="ui-sans-serif, system-ui" fill="#193245">{case_id} longitudinal lesion review</text>
          <text x="70" y="58" font-size="11" font-family="ui-sans-serif, system-ui" fill="#607386">Prototype preview derived from longitudinal response metrics</text>
          <g transform="translate(0,0)">
            <rect x="{left}" y="{top}" width="{chart_width}" height="{chart_height}" rx="18" fill="white" opacity="0.9"/>
            <line x1="{left+20}" y1="{top+chart_height-18}" x2="{left+chart_width-18}" y2="{top+chart_height-18}" stroke="#d5e0e8"/>
            <line x1="{left+20}" y1="{top+18}" x2="{left+20}" y2="{top+chart_height-18}" stroke="#d5e0e8"/>
            <path d="{path}" fill="none" stroke="#146f95" stroke-width="4" stroke-linecap="round"/>
            {''.join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5.5" fill="#146f95"/>' for x, y, _ in points)}
            <text x="{left+18}" y="{top+chart_height+18}" font-size="11" font-family="ui-sans-serif, system-ui" fill="#5e7487">Baseline</text>
            <text x="{left+chart_width-58}" y="{top+chart_height+18}" font-size="11" font-family="ui-sans-serif, system-ui" fill="#5e7487">Latest</text>
          </g>
          <g transform="translate(430,84)">
            <rect x="0" y="0" width="220" height="198" rx="20" fill="white" opacity="0.94"/>
            <ellipse cx="72" cy="94" rx="54" ry="72" fill="#dfe8ef"/>
            <circle cx="72" cy="94" r="{circle_radius_base:.1f}" fill="#f5bf9e" opacity="0.32"/>
            <circle cx="72" cy="94" r="{circle_radius:.1f}" fill="url(#lesion)"/>
            <ellipse cx="154" cy="94" rx="40" ry="58" fill="#dfe8ef"/>
            <text x="18" y="24" font-size="12" font-family="ui-sans-serif, system-ui" fill="#5e7487">Representative lesion signal</text>
            <text x="18" y="165" font-size="13" font-family="ui-sans-serif, system-ui" fill="#193245">Latest lesion burden</text>
            <text x="18" y="183" font-size="11" font-family="ui-sans-serif, system-ui" fill="#607386">{latest:.2f} mL | recent interval {latest_change:+.1f}%</text>
          </g>
          <g transform="translate(70,300)">
            <rect x="0" y="0" width="580" height="48" rx="16" fill="white" opacity="0.92"/>
            <text x="18" y="20" font-size="11" font-family="ui-sans-serif, system-ui" fill="#607386">Key timepoints</text>
            {''.join(
                f'<text x="{24 + index*92}" y="36" font-size="12" font-family="ui-sans-serif, system-ui" fill="#193245">{_title_case(point.timepoint)} · {point.study_date}</text>'
                for index, point in enumerate(timeline[:6])
            )}
          </g>
        </svg>
        """
        encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        return f"data:image/svg+xml;base64,{encoded}"

    def _build_real_preview_data_url(self, case_id: str) -> str | None:
        try:
            import nibabel as nib
            import numpy as np
            from PIL import Image
        except Exception:
            return None

        zip_path = self.root / f"{case_id}.zip"
        if not zip_path.exists():
            return None
        members = self._select_preview_members(case_id, zip_path)
        if not members:
            return None

        panels: list[Image.Image] = []
        labels: list[str] = []
        for label, image_member, mask_member in members:
            try:
                image_path = self._materialize_member(zip_path, image_member)
                mask_path = self._materialize_member(zip_path, mask_member)
                image_nii = nib.load(str(image_path))
                mask_nii = nib.load(str(mask_path))
                image_data = image_nii.get_fdata()
                mask_data = mask_nii.get_fdata()
            except Exception:
                continue
            if image_data.ndim < 3 or mask_data.ndim < 3:
                continue
            slice_index = int(np.argmax(mask_data.sum(axis=(0, 1))))
            image_slice = np.rot90(image_data[:, :, slice_index])
            mask_slice = np.rot90(mask_data[:, :, slice_index])
            panel = self._compose_overlay_panel(image_slice, mask_slice)
            if panel is not None:
                panels.append(panel)
                labels.append(label)

        if not panels:
            return None

        width = sum(panel.width for panel in panels) + 24 * (len(panels) - 1)
        height = max(panel.height for panel in panels) + 44
        canvas = Image.new("RGBA", (width, height), (248, 251, 253, 255))
        cursor = 0
        for label, panel in zip(labels, panels):
            canvas.alpha_composite(panel, (cursor, 28))
            cursor += panel.width + 24

        png = io.BytesIO()
        canvas.save(png, format="PNG")
        encoded = base64.b64encode(png.getvalue()).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    def _select_preview_members(self, case_id: str, zip_path: Path) -> list[tuple[str, str, str]]:
        with zipfile.ZipFile(zip_path) as archive:
            names = archive.namelist()
        timepoints = sorted(
            {
                _canonical_timepoint(match.group(1))
                for name in names
                for match in [re.match(rf"{case_id}/BraTS/([^/]+)/t1c\.nii\.gz$", name)]
                if match
            },
            key=_timepoint_sort_key,
        )
        if not timepoints:
            return []
        picks = [timepoints[0]]
        if len(timepoints) > 2:
            picks.append(timepoints[len(timepoints) // 2])
        if timepoints[-1] not in picks:
            picks.append(timepoints[-1])
        members: list[tuple[str, str, str]] = []
        for timepoint in picks:
            image_member = f"{case_id}/BraTS/{timepoint}/t1c.nii.gz"
            mask_name = "baseline" if timepoint == "baseline" else timepoint
            candidate_masks = [
                f"{case_id}/tumor_segmentation/{case_id}_tumor_mask_{mask_name}.nii.gz",
                f"{case_id}/tumor segmentation/{case_id}_tumor_mask_{mask_name}.nii.gz",
            ]
            mask_member = next((name for name in candidate_masks if name in names), None)
            if image_member in names and mask_member:
                members.append((_title_case(timepoint), image_member, mask_member))
        return members

    def _materialize_member(self, zip_path: Path, member: str) -> Path:
        cache_root = Path(__file__).resolve().parents[2] / ".clinicalclaw" / "cache" / "proteas"
        target = cache_root / member
        if target.exists():
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as archive:
            with archive.open(member) as src, open(target, "wb") as dst:
                dst.write(src.read())
        return target

    def _mask_volume_mm3(self, case_id: str, member: str | None) -> float | None:
        if not member:
            return None
        try:
            import nibabel as nib
            import numpy as np
        except Exception:
            return None
        zip_path = self.root / f"{case_id}.zip"
        if not zip_path.exists():
            return None
        try:
            mask_path = self._materialize_member(zip_path, member)
            nii = nib.load(str(mask_path))
            data = nii.get_fdata()
            voxel_volume = float(abs(np.linalg.det(nii.affine[:3, :3])))
            voxels = float((data > 0).sum())
            return voxels * voxel_volume
        except Exception:
            return None

    def _compose_overlay_panel(self, image_slice: Any, mask_slice: Any) -> Any | None:
        try:
            import numpy as np
            from PIL import Image, ImageDraw
        except Exception:
            return None

        if image_slice.size == 0 or mask_slice.size == 0:
            return None
        image = image_slice.astype(float)
        mask = mask_slice > 0
        nonzero = image[image > 0]
        if nonzero.size == 0:
            return None
        lo = float(np.percentile(nonzero, 5))
        hi = float(np.percentile(nonzero, 99))
        scaled = np.clip((image - lo) / max(hi - lo, 1e-6), 0, 1)
        gray = (scaled * 255).astype("uint8")
        rgba = np.stack([gray, gray, gray, np.full_like(gray, 255)], axis=-1)
        rgba[mask, 0] = 232
        rgba[mask, 1] = 78
        rgba[mask, 2] = 92
        rgba[mask, 3] = 210
        panel = Image.fromarray(rgba, mode="RGBA").resize((212, 212))
        frame = Image.new("RGBA", (236, 256), (255, 255, 255, 238))
        frame.alpha_composite(panel, (12, 16))
        draw = ImageDraw.Draw(frame)
        draw.rounded_rectangle((0, 0, 235, 255), radius=22, outline=(218, 227, 235, 255), width=1)
        return frame


class NeuroLongitudinalStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._dataset = ProteasDataset.discover()
        self._cases = self._build_cases()

    def _build_cases(self) -> dict[str, dict[str, Any]]:
        if self._dataset is None:
            return self._fallback_cases()
        preferred = os.getenv("CLINICALCLAW_NEURO_DEMO_CASE", "P28").strip() or "P28"
        case_ids = self._dataset.list_available_cases()
        if preferred in case_ids:
            ordered = [preferred] + [case for case in case_ids if case != preferred]
        else:
            ordered = case_ids
        cases: dict[str, dict[str, Any]] = {}
        for patient_id in ordered[:3]:
            try:
                workspace = self._dataset.build_case_workspace(patient_id)
            except Exception:
                continue
            cases[workspace["id"]] = workspace
        return cases or self._fallback_cases()

    def _fallback_cases(self) -> dict[str, dict[str, Any]]:
        fallback = {
            "id": "proteas-mock-p28",
            "title": "PROTEAS longitudinal response review",
            "dataset": "PROTEAS (mock fallback)",
            "patient": {
                "id": "P28",
                "display_name": "Subject P28",
                "sex": "Male",
                "age": 70,
                "diagnosis": "Brain metastasis follow-up",
                "mrn": "PROTEAS-P28",
                "summary": "Six follow-up MRI points after stereotactic radiotherapy with an active response review lane.",
                "histology": "NSCLC",
                "intervention": "RS",
                "lesion_location": "Lt temporoparietal",
                "metastasis_count": "1",
                "karnofsky": "80",
                "who_ps": "1",
            },
            "timeline": [
                {
                    "study_id": "p28-baseline",
                    "study_date": "2022-06-27",
                    "timepoint": "baseline",
                    "sequence": "T1C HR",
                    "lesion_volume_ml": 4.2,
                    "enhancing_volume_ml": 3.7,
                    "edema_volume_ml": 6.3,
                    "interval_days": None,
                    "percent_change_from_baseline": 0.0,
                    "percent_change_from_prior": None,
                    "source_type": "mock_proteas_response",
                },
                {
                    "study_id": "p28-fu1",
                    "study_date": "2022-08-04",
                    "timepoint": "fu1",
                    "sequence": "T1C HR",
                    "lesion_volume_ml": 3.4,
                    "enhancing_volume_ml": 2.8,
                    "edema_volume_ml": 5.8,
                    "interval_days": 38,
                    "percent_change_from_baseline": -19.0,
                    "percent_change_from_prior": -19.0,
                    "source_type": "mock_proteas_response",
                },
                {
                    "study_id": "p28-fu2",
                    "study_date": "2022-11-03",
                    "timepoint": "fu2",
                    "sequence": "T1C",
                    "lesion_volume_ml": 3.1,
                    "enhancing_volume_ml": 2.5,
                    "edema_volume_ml": 5.0,
                    "interval_days": 91,
                    "percent_change_from_baseline": -26.2,
                    "percent_change_from_prior": -8.8,
                    "source_type": "mock_proteas_response",
                },
                {
                    "study_id": "p28-fu3",
                    "study_date": "2023-02-06",
                    "timepoint": "fu3",
                    "sequence": "T1C HR",
                    "lesion_volume_ml": 3.8,
                    "enhancing_volume_ml": 3.0,
                    "edema_volume_ml": 6.1,
                    "interval_days": 95,
                    "percent_change_from_baseline": -9.5,
                    "percent_change_from_prior": 22.6,
                    "source_type": "mock_proteas_response",
                },
                {
                    "study_id": "p28-fu4",
                    "study_date": "2023-05-17",
                    "timepoint": "fu4",
                    "sequence": "T1C HR",
                    "lesion_volume_ml": 4.6,
                    "enhancing_volume_ml": 3.8,
                    "edema_volume_ml": 6.8,
                    "interval_days": 100,
                    "percent_change_from_baseline": 9.5,
                    "percent_change_from_prior": 21.1,
                    "source_type": "mock_proteas_response",
                },
                {
                    "study_id": "p28-fu5",
                    "study_date": "2023-08-28",
                    "timepoint": "fu5",
                    "sequence": "T1C HR",
                    "lesion_volume_ml": 5.3,
                    "enhancing_volume_ml": 4.4,
                    "edema_volume_ml": 7.5,
                    "interval_days": 103,
                    "percent_change_from_baseline": 26.2,
                    "percent_change_from_prior": 15.2,
                    "source_type": "mock_proteas_response",
                },
            ],
        }
        fallback["analysis"] = {
            "structure": "Treated brain metastasis",
            "baseline_total_ml": 4.2,
            "latest_total_ml": 5.3,
            "previous_total_ml": 4.6,
            "annual_change_pct": 21.3,
            "recent_segment_pct": 15.2,
            "delta_pct": 26.2,
            "recent_delta_vs_overall_pct": -6.1,
            "accelerated_decline": False,
            "accelerated_progression": True,
            "risk_level": "Progressive",
            "risk_reason": "The latest post-treatment follow-up remains above baseline burden with continued growth across recent intervals.",
            "next_checks": [
                "Correlate with steroid exposure and symptom change.",
                "Review whether progression versus treatment effect remains the leading interpretation.",
                "Consider whether next MRI or tumor-board review should be expedited.",
            ],
            "days_since_baseline": 427,
            "lesion_count": "1",
            "rt_event_date": "2022-06-30",
        }
        fallback["workflow"] = {
            "title": "Post-radiotherapy longitudinal response review",
            "status": "ready_for_review",
            "objective": "Align serial MRI follow-up, quantify lesion burden change, and prepare a concise neuro-oncology review brief.",
            "last_run_at": _utc_now_iso(),
            "steps": [
                {
                    "name": "Select the longitudinal MRI series",
                    "tool": "dicom_series_selector",
                    "status": "completed",
                    "detail": "Collected T1C and FLAIR follow-up series across six available timepoints.",
                },
                {
                    "name": "Align the treatment timeline",
                    "tool": "rt_timeline_aligner",
                    "status": "completed",
                    "detail": "Placed the stereotactic radiotherapy event on the longitudinal MRI timeline.",
                },
                {
                    "name": "Measure longitudinal lesion response",
                    "tool": "brain_met_response_tracker",
                    "status": "completed",
                    "detail": "Computed lesion burden trajectory and current progression signal.",
                },
                {
                    "name": "Prepare the review brief and visuals",
                    "tool": "neuro_oncology_brief_presenter",
                    "status": "completed",
                    "detail": "Drafted the clinician-facing brief and updated the presentation payload.",
                },
            ],
        }
        fallback["imaging_preview"] = {
            "title": "Representative longitudinal lesion preview",
            "caption": "Prototype visual derived from longitudinal lesion burden and review timeline.",
            "image_url": self._dataset.build_case_workspace("P28")["imaging_preview"]["image_url"] if self._dataset else "",
        }
        if not fallback["imaging_preview"]["image_url"]:
            fallback["imaging_preview"]["image_url"] = "data:image/svg+xml;base64," + base64.b64encode(
                b'<svg xmlns="http://www.w3.org/2000/svg" width="720" height="400"><rect width="720" height="400" rx="28" fill="#eff5f8"/><text x="56" y="80" font-size="28" fill="#173245" font-family="ui-sans-serif, system-ui">Neuro longitudinal preview</text><text x="56" y="116" font-size="16" fill="#5d7387" font-family="ui-sans-serif, system-ui">Fallback visual available when local PROTEAS data is not configured.</text></svg>'
            ).decode("ascii")
        fallback["report"] = {
            "title": "AI longitudinal brain metastasis review",
            "subtitle": "Prototype physician-facing follow-up brief",
            "risk_level": "Progressive",
            "summary": "The treated lesion shows interval regrowth after early post-treatment improvement, keeping the case in a progression-focused review lane.",
            "sections": [
                {
                    "title": "Review context",
                    "body": "Single left temporoparietal metastasis after stereotactic radiosurgery with serial MRI follow-up.",
                },
                {
                    "title": "Longitudinal burden change",
                    "body": "Lesion burden improved early, then rose across later follow-up intervals and now exceeds the post-treatment nadir.",
                },
                {
                    "title": "Treatment-aligned interpretation",
                    "body": "This review is framed around the post-radiotherapy course and is intended for physician review, not autonomous diagnosis.",
                },
                {
                    "title": "Clinical attention level",
                    "body": "Current trajectory warrants high-attention neuro-oncology follow-up and multidisciplinary correlation.",
                },
            ],
            "physician_questions": [
                "Does the latest increase reflect progression or treatment-related change?",
                "Should follow-up MRI or tumor-board review be accelerated?",
                "Are systemic disease and symptoms changing in parallel with the imaging trend?",
            ],
        }
        fallback["review"] = NeuroReviewState().model_dump()
        fallback["messages"] = [
            NeuroMessage(
                id="msg_intro_1",
                role="assistant",
                content=(
                    "This workspace reviews a post-radiotherapy brain metastasis case across serial MRI follow-up. "
                    "Ask for a response summary, current risk explanation, or a tumor-board brief."
                ),
                created_at=_utc_now_iso(),
            ).model_dump()
        ]
        fallback["uploads"] = []
        fallback["audit"] = [
            NeuroAuditEvent(
                id="audit_seed_1",
                title="Mock PROTEAS case loaded",
                detail="Initialized a fallback longitudinal brain metastasis review case for local development.",
            ).model_dump()
        ]
        return {fallback["id"]: fallback}

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            default_case_id = next(iter(self._cases))
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
                    for case in self._cases.values()
                ],
                "default_case_id": default_case_id,
                "workspace": deepcopy(self._cases[default_case_id]),
            }

    def get_case(self, case_id: str) -> dict[str, Any]:
        with self._lock:
            case = self._cases.get(case_id)
            if not case:
                raise KeyError(case_id)
            return deepcopy(case)

    def add_upload(self, case_id: str, filename: str) -> dict[str, Any]:
        with self._lock:
            case = self._cases[case_id]
            case["uploads"].append(
                {"id": f"upload_{len(case['uploads']) + 1}", "filename": filename, "added_at": _utc_now_iso()}
            )
            case["audit"].insert(
                0,
                NeuroAuditEvent(
                    id=f"audit_upload_{len(case['audit']) + 1}",
                    title="Local file attached",
                    detail=f"Registered local upload: {filename}",
                ).model_dump(),
            )
            return deepcopy(case)

    def chat(self, case_id: str, message: str) -> dict[str, Any]:
        with self._lock:
            case = self._cases[case_id]
            user_message = NeuroMessage(
                id=f"msg_user_{len(case['messages']) + 1}",
                role="user",
                content=message,
                created_at=_utc_now_iso(),
            )
            case["messages"].append(user_message.model_dump())

            lowered = message.lower()
            if any(token in lowered for token in {"report", "summary", "brief", "tumor board"}):
                assistant_text = (
                    f"I refreshed the longitudinal review for {case['patient']['display_name']}. "
                    f"The current burden moved from {case['analysis']['baseline_total_ml']:.2f} mL at baseline to "
                    f"{case['analysis']['latest_total_ml']:.2f} mL at the latest follow-up, with current risk labeled "
                    f"{case['analysis']['risk_level'].lower()}."
                )
                audit_title = "Longitudinal report refreshed"
                audit_detail = "Rebuilt the post-radiotherapy longitudinal response brief from the current case payload."
            elif any(token in lowered for token in {"risk", "progression", "response"}):
                assistant_text = (
                    f"The current risk signal is {case['analysis']['risk_level']}. "
                    f"Latest interval change is {case['analysis']['recent_segment_pct']}%, and the overall change from baseline is "
                    f"{case['analysis']['delta_pct']}%."
                )
                audit_title = "Risk explanation requested"
                audit_detail = "Explained the current progression/response signal using interval and baseline comparisons."
            else:
                assistant_text = (
                    "I can summarize the longitudinal response review, explain the current risk signal, or prepare a tumor-board style brief."
                )
                audit_title = "General neuro guidance"
                audit_detail = "Returned supported actions for the longitudinal neuro-oncology workflow."

            assistant_message = NeuroMessage(
                id=f"msg_assistant_{len(case['messages']) + 1}",
                role="assistant",
                content=assistant_text,
                created_at=_utc_now_iso(),
            )
            case["messages"].append(assistant_message.model_dump())
            case["audit"].insert(
                0,
                NeuroAuditEvent(
                    id=f"audit_chat_{len(case['audit']) + 1}",
                    title=audit_title,
                    detail=audit_detail,
                ).model_dump(),
            )
            case["workflow"]["last_run_at"] = _utc_now_iso()
            case["workflow"]["status"] = "ready_for_review"
            case["review"]["status"] = "in_review"
            case["review"]["comment"] = "AI review refreshed and waiting for clinician sign-off."
            case["review"]["updated_at"] = _utc_now_iso()
            return {"assistant": assistant_message.model_dump(), "workspace": deepcopy(case)}

    def review(self, case_id: str, action: str, comment: str | None = None) -> dict[str, Any]:
        with self._lock:
            case = self._cases[case_id]
            normalized = action.strip().lower()
            status_map = {"approve": "approved", "reject": "rejected", "comment": case["review"]["status"]}
            status = status_map.get(normalized, case["review"]["status"])
            case["review"]["status"] = status
            case["review"]["comment"] = comment or case["review"]["comment"]
            case["review"]["updated_at"] = _utc_now_iso()
            case["workflow"]["status"] = "approved" if normalized == "approve" else "rejected" if normalized == "reject" else "reviewer_commented"
            case["audit"].insert(
                0,
                NeuroAuditEvent(
                    id=f"audit_review_{len(case['audit']) + 1}",
                    title=f"Reviewer action: {normalized}",
                    detail=comment or f"Review status changed to {status}.",
                    severity="success" if normalized == "approve" else "warning" if normalized == "reject" else "info",
                ).model_dump(),
            )
            return deepcopy(case)


neuro_longitudinal_store = NeuroLongitudinalStore()
