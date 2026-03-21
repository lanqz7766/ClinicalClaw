from __future__ import annotations

import gzip
import json
import math
import os
import re
import shutil
import struct
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, Field

from clinicalclaw.neuro_report_generator import build_neuro_report_bundle
from clinicalclaw.neuro_visualization import (
    build_neuro_visualization_bundle,
    materialize_privacy_preserving_viewer_assets,
)
from clinicalclaw.reporting import build_report_document_from_workspace, export_report_bundle


DEFAULT_NEURO_DATA_ENV = "CLINICALCLAW_NEURO_LONGITUDINAL_DATA_ROOT"
DEFAULT_PATIENT_ID = "P28"
DEFAULT_OUTPUT_ROOT = Path(".clinicalclaw") / "derived" / "neuro_longitudinal"

_TIMEPOINT_ORDER = ["baseline", "fu1", "fu2", "fu3", "fu4", "fu5", "fu6", "fu7", "fu8"]
_SERIES_DIR_RE = re.compile(
    r"^(?P<prefix>[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*)_(?P<date>\d{4}[-_]\d{2}[-_]\d{2})(?:[_/].*)?$"
)

_NIFTI_DTYPES = {
    2: ("B", 1),
    4: ("h", 2),
    8: ("i", 4),
    16: ("f", 4),
    64: ("d", 8),
    256: ("b", 1),
    512: ("H", 2),
    768: ("I", 4),
    1024: ("q", 8),
    1280: ("Q", 8),
}


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_key(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _parse_date_token(value: str) -> str:
    return value.replace("_", "-")


def _canonical_timepoint(token: str) -> str:
    lowered = _safe_text(token).lower()
    if lowered in {"baseline", "base", "bl"}:
        return "baseline"
    match = re.search(r"(?:follow[_ -]?up[_ -]?|fu)(\d+)", lowered)
    if match:
        return f"fu{int(match.group(1))}"
    return _normalize_key(lowered)


def _timepoint_rank(label: str) -> int:
    key = _normalize_key(label)
    if key in _TIMEPOINT_ORDER:
        return _TIMEPOINT_ORDER.index(key)
    match = re.search(r"fu(\d+)", key)
    if match:
        return 10 + int(match.group(1))
    return 999


def _series_modality(prefix: str) -> str:
    upper = prefix.upper()
    if upper.startswith("T1C"):
        return "T1C"
    if upper.startswith("TIC"):
        return "T1C"
    if upper.startswith("FLR"):
        return "FLAIR"
    if upper.startswith("T1W"):
        return "T1W"
    if upper.startswith("T2W"):
        return "T2W"
    if upper.startswith("RTP"):
        return "RTP"
    return prefix


def _series_role(prefix: str) -> str:
    upper = prefix.upper()
    if upper.startswith("T1C"):
        return "post-contrast"
    if upper.startswith("TIC"):
        return "post-contrast"
    if upper.startswith("FLR"):
        return "fluid-attenuated"
    if upper.startswith("T1W"):
        return "pre-contrast"
    if upper.startswith("T2W"):
        return "T2-weighted"
    if upper.startswith("RTP"):
        return "radiotherapy-plan"
    return "unknown"


def _excel_serial_to_iso(value: Any) -> str:
    text = _safe_text(value)
    if not text:
        return ""
    for fmt in ("%m/%d/%Y", "%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    try:
        number = float(text)
    except ValueError:
        return text
    if number <= 0:
        return text
    base = datetime(1899, 12, 30, tzinfo=UTC)
    return (base + timedelta(days=number)).date().isoformat()


class NeuroSeriesReference(BaseModel):
    modality: str
    role: str
    date: str
    series_name: str
    series_member_root: str
    file_count: int
    representative_file: str | None = None


class NeuroTimepointRecord(BaseModel):
    timepoint: str
    study_date: str
    clinical_label: str | None = None
    age_years: int | None = None
    diagnosis: str | None = None
    lesion_volume_ml: float
    lesion_voxels: int
    source_type: str = "radiomics_t1c_mesh_volume"
    tumor_volume_ml: float | None = None
    all_volume_ml: float | None = None
    oedema_volume_ml: float | None = None
    necrosis_volume_ml: float | None = None
    interval_change_pct: float | None = None
    cumulative_change_pct: float | None = None
    interval_days: int | None = None
    days_from_baseline: int | None = None
    trend_label: str
    series: list[NeuroSeriesReference] = Field(default_factory=list)
    mask_member: str | None = None


class NeuroResponseSummary(BaseModel):
    baseline_volume_ml: float
    latest_volume_ml: float
    previous_volume_ml: float | None = None
    cumulative_change_pct: float
    annualized_change_pct: float
    recent_interval_change_pct: float | None = None
    recent_annualized_change_pct: float | None = None
    response_label: str
    risk_level: str
    risk_reason: str
    next_checks: list[str] = Field(default_factory=list)


class NeuroVisualizationPayload(BaseModel):
    trend_svg: str
    timeline_svg: str
    comparison_svg: str
    viewer_manifest: dict[str, Any] = Field(default_factory=dict)
    preview_assets: list[dict[str, Any]] = Field(default_factory=list)
    comparison_panels: list[dict[str, Any]] = Field(default_factory=list)
    asset_paths: dict[str, str] = Field(default_factory=dict)


class NeuroLongitudinalWorkspace(BaseModel):
    id: str
    title: str
    dataset: str
    patient: dict[str, Any]
    timeline: list[NeuroTimepointRecord]
    analysis: NeuroResponseSummary
    workflow: dict[str, Any]
    imaging_preview: dict[str, Any]
    report: dict[str, Any]
    review: dict[str, Any]
    source: dict[str, Any]
    series_catalog: list[dict[str, Any]] = Field(default_factory=list)
    radiomics: dict[str, Any] = Field(default_factory=dict)
    visualizations: NeuroVisualizationPayload | None = None
    viewer: dict[str, Any] = Field(default_factory=dict)


def _read_zip_names(archive: Path) -> list[str]:
    with zipfile.ZipFile(archive) as zf:
        return zf.namelist()


def _detect_patient_archives(data_root: Path) -> list[Path]:
    if not data_root.exists():
        return []
    if data_root.is_file():
        return [data_root]
    archives = sorted(data_root.glob("P*.zip"))
    if archives:
        return archives
    archives = sorted(p for p in data_root.iterdir() if p.is_dir() and re.fullmatch(r"P\d+[ab]?", p.name))
    return archives


def discover_proteas_patient_ids(data_root: str | Path) -> list[str]:
    root = Path(data_root)
    ids: list[str] = []
    for archive in _detect_patient_archives(root):
        if archive.suffix == ".zip":
            ids.append(archive.stem)
        else:
            ids.append(archive.name)
    return sorted(dict.fromkeys(ids))


def _derived_assets_root() -> Path:
    return (Path(__file__).resolve().parents[2] / ".clinicalclaw" / "derived").resolve()


def _derived_asset_url(path: Path) -> str | None:
    try:
        relative = path.resolve().relative_to(DEFAULT_OUTPUT_ROOT.resolve())
    except ValueError:
        return None
    return f"/neuro-assets/{relative.as_posix()}"


def resolve_proteas_data_root(data_root: str | Path | None = None) -> Path | None:
    candidates: list[str | Path | None] = [data_root, os.getenv(DEFAULT_NEURO_DATA_ENV)]
    for candidate in candidates:
        if not candidate:
            continue
        root = Path(candidate).expanduser()
        if root.exists():
            return root.resolve()
    return None


def _extract_xlsx_rows(xlsx_path: Path, sheet_name: str | None = None) -> list[dict[str, str]]:
    import xml.etree.ElementTree as ET

    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    rel_ns = "{http://schemas.openxmlformats.org/package/2006/relationships}"

    with zipfile.ZipFile(xlsx_path) as zf:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            shared_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in shared_root.findall(f"{ns}si"):
                shared_strings.append("".join(t.text or "" for t in si.iterfind(f".//{ns}t")))

        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        relmap = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels.findall(f"{rel_ns}Relationship")}

        sheets = workbook.find(f"{ns}sheets")
        if sheets is None:
            return []

        target_sheet = None
        for sheet in sheets:
            if sheet_name is None or sheet.attrib.get("name") == sheet_name:
                rid = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
                target_sheet = "xl/" + relmap[rid]
                break
        if target_sheet is None:
            return []

        root = ET.fromstring(zf.read(target_sheet))
        rows: list[list[str]] = []
        for row in root.iterfind(f".//{ns}sheetData/{ns}row"):
            values: list[str] = []
            for cell in row.findall(f"{ns}c"):
                t = cell.attrib.get("t")
                v = cell.find(f"{ns}v")
                if v is None:
                    values.append("")
                elif t == "s":
                    values.append(shared_strings[int(v.text)])
                elif t == "inlineStr":
                    values.append("".join(t_.text or "" for t_ in cell.iterfind(f".//{ns}t")))
                else:
                    values.append(v.text or "")
            rows.append(values)

    if not rows:
        return []

    header = [(_safe_text(cell) or f"col_{idx}") for idx, cell in enumerate(rows[0])]
    records: list[dict[str, str]] = []
    for row in rows[1:]:
        record = {header[idx]: _safe_text(value) for idx, value in enumerate(row) if idx < len(header)}
        if any(record.values()):
            records.append(record)
    return records


def _load_patient_row(data_root: Path, patient_id: str) -> dict[str, str]:
    workbook = data_root / "PROTEAS-Clinical_and_demographic_data.xlsx"
    if not workbook.exists():
        return {}
    rows = _extract_xlsx_rows(workbook, sheet_name="PROTEAS")
    for row in rows:
        if _safe_text(row.get("Patient ID (Zenodo)")) == patient_id:
            return row
    return {}


def _load_radiomics_snapshot(data_root: Path, patient_id: str, limit: int = 12) -> dict[str, Any]:
    workbook = data_root / "PROTEAS-MRI_radiomics_data.xlsx"
    if not workbook.exists():
        return {}
    rows = _extract_xlsx_rows(workbook, sheet_name=patient_id)
    if not rows:
        return {}
    features: list[dict[str, Any]] = []
    masks: set[str] = set()
    modalities: set[str] = set()
    followups: set[str] = set()
    for row in rows[: max(limit * 6, 40)]:
        feature_name = _safe_text(row.get("RadiomicsFeature"))
        value = _safe_text(row.get("RadiomicsValue"))
        if not feature_name:
            continue
        parts = feature_name.split("__")
        if len(parts) >= 4:
            masks.add(parts[0])
            modalities.add(parts[1])
            followups.add(parts[2])
        features.append({"feature": feature_name, "value": value})
    return {
        "feature_count": len(rows),
        "sample_features": features[:limit],
        "mask_types": sorted(masks),
        "modalities": sorted(modalities),
        "followups": sorted(followups),
    }


def _extract_radiomics_timeseries(data_root: Path, patient_id: str) -> dict[str, dict[str, float]]:
    workbook = data_root / "PROTEAS-MRI_radiomics_data.xlsx"
    if not workbook.exists():
        return {}
    rows = _extract_xlsx_rows(workbook, sheet_name=patient_id)
    if not rows:
        return {}

    pattern = re.compile(
        r"^mask_(?P<mask>all|tumor|oedema|necrosis)__"
        r"(?P<modality>t1c|t1|t2|fla)__"
        r"(?P<timepoint>[^_]+(?:_[^_]+)?)__"
        r"original_shape_(?P<feature>MeshVolume|VoxelVolume|Maximum3DDiameter)$",
        re.IGNORECASE,
    )
    metrics: dict[str, dict[str, float]] = {}
    for row in rows:
        feature_name = _safe_text(row.get("RadiomicsFeature"))
        value = _safe_float(row.get("RadiomicsValue"))
        if not feature_name or value is None:
            continue
        match = pattern.match(feature_name)
        if not match:
            continue
        if match.group("modality").lower() != "t1c":
            continue
        timepoint = _canonical_timepoint(match.group("timepoint"))
        bucket = metrics.setdefault(timepoint, {})
        bucket[f"{match.group('mask').lower()}_{match.group('feature')}"] = value
    return metrics


def _parse_series_name(series_name: str) -> tuple[str, str] | None:
    match = _SERIES_DIR_RE.match(series_name)
    if not match:
        return None
    return match.group("prefix"), _parse_date_token(match.group("date"))


def _collect_series_catalog(names: Iterable[str], patient_id: str) -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    prefix = f"{patient_id}/DICOM/"
    for name in names:
        if not name.startswith(prefix):
            continue
        suffix = name[len(prefix) :]
        if "/" not in suffix:
            continue
        series_name, member = suffix.split("/", 1)
        parsed = _parse_series_name(series_name)
        if not parsed:
            continue
        raw_prefix, date = parsed
        modality = _series_modality(raw_prefix)
        role = _series_role(raw_prefix)
        entry = catalog.setdefault(
            date,
            {
                "date": date,
                "series": {},
            },
        )
        series_entry = entry["series"].setdefault(
            modality,
            {
                "modality": modality,
                "role": role,
                "series_name": series_name,
                "series_member_root": f"{patient_id}/DICOM/{series_name}",
                "file_count": 0,
                "representative_file": None,
            },
        )
        series_entry["file_count"] += 1
        if not series_entry["representative_file"]:
            series_entry["representative_file"] = f"{patient_id}/DICOM/{series_name}/{member}"
    return catalog


def _extract_timepoint_members(names: Iterable[str], patient_id: str) -> dict[str, str]:
    prefix = f"{patient_id}/tumor_segmentation/"
    mapping: dict[str, str] = {}
    for name in names:
        if not name.startswith(prefix) or not name.endswith(".nii.gz"):
            continue
        stem = Path(name).name
        token = stem.replace(f"{patient_id}_tumor_mask_", "").replace(".nii.gz", "")
        mapping[token] = name
    return mapping


def _extract_brats_members(names: Iterable[str], patient_id: str, modality: str = "t1c") -> dict[str, str]:
    mapping: dict[str, str] = {}
    suffix = f"/{modality.lower()}.nii.gz"
    prefix = f"{patient_id}/BraTS/"
    for name in names:
        if not name.startswith(prefix) or not name.endswith(suffix):
            continue
        token = name[len(prefix) :].split("/", 1)[0]
        mapping[_canonical_timepoint(token)] = name
    return mapping


def _materialize_archive_member(archive_path: Path, member: str, target: Path) -> Path:
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    if archive_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(archive_path) as archive:
            with archive.open(member) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
        return target
    source = archive_path / member
    shutil.copyfile(source, target)
    return target


def _build_viewer_manifest(
    *,
    archive_path: Path,
    names: list[str],
    patient_id: str,
    timeline: list[NeuroTimepointRecord],
    output_base: Path,
    materialize_assets: bool,
    visualizations: NeuroVisualizationPayload,
    imaging_preview: dict[str, Any],
) -> dict[str, Any]:
    t1c_members = _extract_brats_members(names, patient_id, modality="t1c")
    flair_members = _extract_brats_members(names, patient_id, modality="fla")
    viewer_root = output_base / "viewer"
    timepoints: list[dict[str, Any]] = []

    for point in timeline:
        image_member = t1c_members.get(point.timepoint)
        flair_member = flair_members.get(point.timepoint)
        mask_member = point.mask_member
        payload = {
            "timepoint": point.timepoint,
            "study_date": point.study_date,
            "label": point.clinical_label or point.timepoint.replace("_", " ").title(),
            "clinical_label": point.clinical_label or point.timepoint.replace("_", " ").title(),
            "available": bool(image_member),
            "image_url": None,
            "mask_url": None,
            "flair_url": None,
            "privacy_mode": "focus_crop_defaced",
        }
        if materialize_assets and image_member:
            base_target = viewer_root / point.timepoint / "t1c.nii.gz"
            overlay_target = viewer_root / point.timepoint / "tumor_mask.nii.gz"
            flair_target = viewer_root / point.timepoint / "flair.nii.gz"
            materialize_privacy_preserving_viewer_assets(
                archive_path=archive_path,
                image_member=image_member,
                output_image_path=base_target,
                mask_member=mask_member,
                output_mask_path=overlay_target if mask_member else None,
                flair_member=flair_member,
                output_flair_path=flair_target if flair_member else None,
            )
            payload["image_url"] = _derived_asset_url(base_target)
            if mask_member:
                payload["mask_url"] = _derived_asset_url(overlay_target)
            if flair_member:
                payload["flair_url"] = _derived_asset_url(flair_target)
        timepoints.append(payload)

    default_timepoint = timeline[-1].timepoint if timeline else "baseline"
    comparison_svg = _derived_asset_url(output_base / "comparison.svg") if materialize_assets else None
    return {
        "available": any(item.get("available") for item in timepoints),
        "enabled": any(item.get("image_url") for item in timepoints),
        "library": "niivue",
        "default_timepoint": default_timepoint,
        "timepoints": timepoints,
        "fallback_image_url": imaging_preview.get("image_url"),
        "fallback_comparison_svg": comparison_svg or visualizations.comparison_svg,
        "loading_label": "Loading the longitudinal imaging review",
        "fallback_label": "Interactive viewing is unavailable. Falling back to the static longitudinal preview.",
        "privacy_mode": "focus_crop_defaced",
    }


def _select_timepoint_order(labels: Iterable[str]) -> list[str]:
    return sorted({label for label in labels}, key=_timepoint_rank)


def _read_nifti_mask_volume_from_bytes(raw: bytes) -> tuple[int, float, int, tuple[int, int, int]]:
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    header = raw[:352]
    if len(header) < 112:
        raise ValueError("NIfTI header is too short")

    sizeof_hdr = struct.unpack("<i", header[:4])[0]
    if sizeof_hdr != 348:
        raise ValueError(f"Unsupported NIfTI header size: {sizeof_hdr}")

    dim = struct.unpack("<8h", header[40:56])
    pixdim = struct.unpack("<8f", header[76:108])
    vox_offset = int(struct.unpack("<f", header[108:112])[0])
    datatype = struct.unpack("<h", header[70:72])[0]
    bitpix = struct.unpack("<h", header[72:74])[0]
    dims = (max(int(dim[1]), 1), max(int(dim[2]), 1), max(int(dim[3]), 1))
    nvox = math.prod(dims)
    dtype = _NIFTI_DTYPES.get(datatype)
    if not dtype:
        raise ValueError(f"Unsupported NIfTI datatype: {datatype}")
    fmt, width = dtype
    if width != max(bitpix // 8, 1):
        width = max(bitpix // 8, 1)

    payload = raw[vox_offset : vox_offset + (nvox * width)]
    usable = payload[: (len(payload) // width) * width]
    nonzero = 0
    for (value,) in struct.iter_unpack("<" + fmt, usable):
        if value != 0:
            nonzero += 1
    voxel_mm3 = abs(pixdim[1] * pixdim[2] * pixdim[3]) or 1.0
    return nonzero, voxel_mm3, datatype, dims


def _read_nifti_mask_volume(member_bytes: bytes) -> dict[str, Any]:
    nonzero, voxel_mm3, datatype, dims = _read_nifti_mask_volume_from_bytes(member_bytes)
    return {
        "voxels": nonzero,
        "voxel_volume_mm3": voxel_mm3,
        "datatype": datatype,
        "dimensions": dims,
        "volume_ml": round((nonzero * voxel_mm3) / 1000.0, 3),
    }


def _extract_timepoint_volumes(archive: Path, patient_id: str, names: list[str]) -> dict[str, dict[str, Any]]:
    timepoint_members = _extract_timepoint_members(names, patient_id)
    volumes: dict[str, dict[str, Any]] = {}
    if archive.suffix.lower() != ".zip":
        for label, member in timepoint_members.items():
            path = archive / member
            if path.exists():
                volumes[label] = _read_nifti_mask_volume(path.read_bytes())
                volumes[label]["member"] = member
        return volumes

    with zipfile.ZipFile(archive) as zf:
        for label, member in timepoint_members.items():
            try:
                volumes[label] = _read_nifti_mask_volume(zf.read(member))
                volumes[label]["member"] = member
            except KeyError:
                continue
    return volumes


def _read_archive_member_bytes(archive: Path, member: str) -> bytes | None:
    if archive.suffix.lower() != ".zip":
        path = archive / member
        if not path.exists():
            return None
        return path.read_bytes()
    with zipfile.ZipFile(archive) as zf:
        try:
            return zf.read(member)
        except KeyError:
            return None


def _materialize_viewer_assets(
    archive: Path,
    patient_id: str,
    points: list[NeuroTimepointRecord],
    output_base: Path,
) -> dict[str, Any]:
    viewer_root = output_base / "viewer"
    viewer_root.mkdir(parents=True, exist_ok=True)
    timepoints: list[dict[str, Any]] = []
    for point in points:
        timepoint = point.timepoint
        image_member = f"{patient_id}/BraTS/{timepoint}/t1c.nii.gz"
        mask_member = f"{patient_id}/tumor_segmentation/{patient_id}_tumor_mask_{timepoint}.nii.gz"
        image_bytes = _read_archive_member_bytes(archive, image_member)
        mask_bytes = _read_archive_member_bytes(archive, mask_member)
        if not image_bytes or not mask_bytes:
            continue
        point_dir = viewer_root / timepoint
        point_dir.mkdir(parents=True, exist_ok=True)
        image_path = point_dir / "t1c.nii.gz"
        mask_path = point_dir / "mask.nii.gz"
        image_path.write_bytes(image_bytes)
        mask_path.write_bytes(mask_bytes)
        timepoints.append(
            {
                "timepoint": timepoint,
                "clinical_label": point.clinical_label or point.timepoint,
                "study_date": point.study_date,
                "image_url": f"/neuro-assets/{patient_id}/viewer/{timepoint}/t1c.nii.gz",
                "mask_url": f"/neuro-assets/{patient_id}/viewer/{timepoint}/mask.nii.gz",
                "volume_ml": point.lesion_volume_ml,
                "trend_label": point.trend_label,
            }
        )
    return {
        "available": bool(timepoints),
        "default_timepoint": timepoints[-1]["timepoint"] if timepoints else None,
        "timepoints": timepoints,
        "root": str(viewer_root),
    }


def _ordered_imaging_dates(series_catalog: dict[str, dict[str, Any]]) -> list[str]:
    dates: list[str] = []
    for date, payload in sorted(series_catalog.items()):
        modalities = set(payload.get("series", {}).keys())
        imaging_modalities = modalities - {"RTP"}
        if not imaging_modalities:
            continue
        if "T1C" in imaging_modalities or "FLAIR" in imaging_modalities or "T1W" in imaging_modalities:
            dates.append(date)
    return dates


def _radiotherapy_event_date(series_catalog: dict[str, dict[str, Any]]) -> str:
    for date, payload in sorted(series_catalog.items()):
        if "RTP" in payload.get("series", {}):
            return date
    return ""


def _primary_volume_source(
    radiomics_metrics: dict[str, float],
    mask_volume: dict[str, Any],
) -> tuple[float, int, str, dict[str, float]]:
    primary_mm3 = (
        radiomics_metrics.get("tumor_MeshVolume")
        or radiomics_metrics.get("tumor_VoxelVolume")
        or radiomics_metrics.get("all_MeshVolume")
        or radiomics_metrics.get("all_VoxelVolume")
    )
    source = "radiomics_t1c_mesh_volume"
    if primary_mm3 is None:
        primary_ml = float(mask_volume.get("volume_ml", 0.0))
        voxels = int(mask_volume.get("voxels", 0))
        source = "mask_volume_fallback"
        return primary_ml, voxels, source, {
            "tumor_volume_ml": 0.0,
            "all_volume_ml": primary_ml,
            "oedema_volume_ml": 0.0,
            "necrosis_volume_ml": 0.0,
        }

    tumor_ml = (radiomics_metrics.get("tumor_MeshVolume") or radiomics_metrics.get("tumor_VoxelVolume") or 0.0) / 1000.0
    all_ml = (radiomics_metrics.get("all_MeshVolume") or radiomics_metrics.get("all_VoxelVolume") or 0.0) / 1000.0
    oedema_ml = (radiomics_metrics.get("oedema_MeshVolume") or radiomics_metrics.get("oedema_VoxelVolume") or 0.0) / 1000.0
    necrosis_ml = (radiomics_metrics.get("necrosis_MeshVolume") or radiomics_metrics.get("necrosis_VoxelVolume") or 0.0) / 1000.0
    voxels = int(radiomics_metrics.get("tumor_VoxelVolume") or radiomics_metrics.get("all_VoxelVolume") or mask_volume.get("voxels", 0))
    return round(primary_mm3 / 1000.0, 3), voxels, source, {
        "tumor_volume_ml": round(tumor_ml, 3),
        "all_volume_ml": round(all_ml, 3),
        "oedema_volume_ml": round(oedema_ml, 3),
        "necrosis_volume_ml": round(necrosis_ml, 3),
    }


def _interval_days(previous_date: str | None, current_date: str | None) -> int | None:
    if not previous_date or not current_date:
        return None
    try:
        prev = datetime.fromisoformat(previous_date)
        curr = datetime.fromisoformat(current_date)
    except ValueError:
        return None
    return max((curr - prev).days, 0)


def _trend_label(change_pct: float) -> str:
    if change_pct >= 20:
        return "progressive"
    if change_pct <= -15:
        return "response"
    return "stable_watch"


def _visual_points_from_timeline(points: list[NeuroTimepointRecord]) -> list[dict[str, Any]]:
    visual_points: list[dict[str, Any]] = []
    for point in points:
        visual_points.append(
            {
                "timepoint": point.timepoint,
                "study_date": point.study_date,
                "volume_ml": point.lesion_volume_ml,
                "trend_label": point.trend_label,
                "interval_change_pct": point.interval_change_pct,
                "cumulative_change_pct": point.cumulative_change_pct,
                "days_from_baseline": point.days_from_baseline,
                "interval_days": point.interval_days,
            }
        )
    return visual_points


def _timeline_svg(points: list[dict[str, Any]]) -> str:
    width = 940
    height = 180
    margin = 34
    inner = width - margin * 2
    if not points:
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"></svg>'
    step = inner / max(len(points) - 1, 1)
    y = 94
    min_volume = min(p["volume_ml"] for p in points)
    max_volume = max(p["volume_ml"] for p in points)
    volume_span = max(max_volume - min_volume, 1.0)
    cards = []
    for index, point in enumerate(points):
        x = margin + step * index
        dot_color = "#7dd3fc" if point["timepoint"] == "baseline" else "#67e8f9"
        if point.get("trend_label") == "progressive":
            dot_color = "#fb7185"
        elif point.get("trend_label") == "response":
            dot_color = "#4ade80"
        rel = (point["volume_ml"] - min_volume) / volume_span
        bar_h = 10 + rel * 48
        cards.append(
            f'<g><line x1="{x}" y1="{y - 40}" x2="{x}" y2="{y + 40}" stroke="rgba(148,163,184,0.2)" stroke-width="1"/>'
            f'<circle cx="{x}" cy="{y}" r="8" fill="{dot_color}"/>'
            f'<rect x="{x - 8}" y="{y - bar_h}" width="16" height="{bar_h}" rx="8" fill="{dot_color}" opacity="0.25"/>'
            f'<text x="{x}" y="{y + 60}" text-anchor="middle" font-size="12" fill="#dbeafe">{point["timepoint"]}</text>'
            f'<text x="{x}" y="{y + 76}" text-anchor="middle" font-size="11" fill="#94a3b8">{point["volume_ml"]:.1f} mL</text>'
            f'</g>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<rect x="0" y="0" width="{width}" height="{height}" rx="20" fill="#0f172a"/>'
        f'<text x="24" y="32" font-size="16" fill="#f8fafc" font-weight="600">Longitudinal response timeline</text>'
        + "".join(cards)
        + "</svg>"
    )


def _trend_svg(points: list[dict[str, Any]], response: NeuroResponseSummary) -> str:
    width = 940
    height = 300
    margin_x = 54
    margin_y = 46
    inner_w = width - margin_x * 2
    inner_h = height - margin_y * 2
    if not points:
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"></svg>'
    volumes = [p["volume_ml"] for p in points]
    min_v = min(volumes)
    max_v = max(volumes)
    span = max(max_v - min_v, 1.0)

    def sx(idx: int) -> float:
        return margin_x + (inner_w * idx / max(len(points) - 1, 1))

    def sy(volume: float) -> float:
        return margin_y + inner_h - ((volume - min_v) / span) * inner_h

    path = " ".join(
        f"{'M' if idx == 0 else 'L'} {sx(idx):.1f} {sy(point['volume_ml']):.1f}"
        for idx, point in enumerate(points)
    )
    dots = []
    for idx, point in enumerate(points):
        dot_color = "#67e8f9"
        if point.get("trend_label") == "progressive":
            dot_color = "#fb7185"
        elif point.get("trend_label") == "response":
            dot_color = "#4ade80"
        dots.append(
            f'<circle cx="{sx(idx):.1f}" cy="{sy(point["volume_ml"]):.1f}" r="6.5" fill="{dot_color}"/>'
            f'<text x="{sx(idx):.1f}" y="{height - 18}" text-anchor="middle" font-size="11" fill="#cbd5e1">{point["timepoint"]}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<defs><linearGradient id="trendFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#38bdf8" stop-opacity="0.28"/><stop offset="100%" stop-color="#38bdf8" stop-opacity="0.02"/></linearGradient></defs>'
        f'<rect x="0" y="0" width="{width}" height="{height}" rx="24" fill="#08111f"/>'
        f'<text x="24" y="30" font-size="16" fill="#f8fafc" font-weight="600">Lesion burden vs time</text>'
        f'<text x="24" y="50" font-size="12" fill="#94a3b8">Baseline {response.baseline_volume_ml:.1f} mL · Latest {response.latest_volume_ml:.1f} mL · {response.cumulative_change_pct:+.1f}%</text>'
        f'<line x1="{margin_x}" y1="{height - margin_y}" x2="{width - margin_x}" y2="{height - margin_y}" stroke="rgba(148,163,184,0.18)" stroke-width="1"/>'
        f'<path d="{path}" fill="none" stroke="#38bdf8" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<path d="M {sx(0):.1f} {height - margin_y} {path[2:] if path else ""} L {sx(len(points) - 1):.1f} {height - margin_y} Z" fill="url(#trendFill)" opacity="0.9"/>'
        + "".join(dots)
        + "</svg>"
    )


def _comparison_svg(points: list[dict[str, Any]], response: NeuroResponseSummary) -> str:
    width = 940
    height = 240
    panels = []
    if not points:
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"></svg>'
    selected = [points[0], points[len(points) // 2], points[-1]]
    labels = ["baseline", "midpoint", "latest"]
    x_positions = [28, 320, 612]
    for x, label, point in zip(x_positions, labels, selected):
        panels.append(
            f'<rect x="{x}" y="46" width="260" height="152" rx="22" fill="#0f172a" stroke="rgba(148,163,184,0.16)"/>'
            f'<text x="{x + 18}" y="76" font-size="13" fill="#94a3b8">{label}</text>'
            f'<text x="{x + 18}" y="112" font-size="24" fill="#f8fafc" font-weight="700">{point["volume_ml"]:.1f} mL</text>'
            f'<text x="{x + 18}" y="140" font-size="12" fill="#cbd5e1">{point["study_date"]}</text>'
            f'<text x="{x + 18}" y="164" font-size="12" fill="#94a3b8">{point["trend_label"].replace("_", " ").title()}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<rect x="0" y="0" width="{width}" height="{height}" rx="24" fill="#0b1220"/>'
        f'<text x="24" y="30" font-size="16" fill="#f8fafc" font-weight="600">Key comparison cards</text>'
        + "".join(panels)
        + "</svg>"
    )


def _analysis_from_points(points: list[dict[str, Any]]) -> NeuroResponseSummary:
    if not points:
        return NeuroResponseSummary(
            baseline_volume_ml=0.0,
            latest_volume_ml=0.0,
            cumulative_change_pct=0.0,
            annualized_change_pct=0.0,
            response_label="unknown",
            risk_level="Unknown",
            risk_reason="No imaging timepoints were found.",
        )
    baseline = points[0]
    latest = points[-1]
    previous = points[-2] if len(points) > 1 else None
    baseline_volume = baseline["volume_ml"]
    latest_volume = latest["volume_ml"]
    previous_volume = previous["volume_ml"] if previous else None
    cumulative_change_pct = 0.0 if baseline_volume == 0 else round(((latest_volume - baseline_volume) / baseline_volume) * 100.0, 1)
    interval_days = latest.get("days_from_baseline") or 0
    annualized_change_pct = 0.0
    if interval_days:
        annualized_change_pct = round(cumulative_change_pct * 365.25 / interval_days, 1)
    recent_interval_change_pct = None
    recent_annualized_change_pct = None
    if previous_volume not in (None, 0):
        recent_interval_change_pct = round(((latest_volume - previous_volume) / previous_volume) * 100.0, 1)
        recent_days = latest.get("interval_days") or 0
        if recent_days:
            recent_annualized_change_pct = round(recent_interval_change_pct * 365.25 / recent_days, 1)
    response_label = _trend_label(cumulative_change_pct)
    if cumulative_change_pct >= 25 or (recent_interval_change_pct is not None and recent_interval_change_pct >= 15):
        risk_level = "High attention"
        response_label = "progressive"
        if recent_interval_change_pct is not None and recent_interval_change_pct < 0:
            risk_reason = (
                "Enhancing tumor burden remains far above baseline despite a modest decrease in the latest interval, "
                "so the case should stay in a high-attention review lane."
            )
            next_checks = [
                "Confirm whether the latest decrease reflects early treatment response or measurement variability.",
                "Review the latest T1C series side by side with baseline and the prior peak follow-up.",
                "Correlate with clinical symptoms and the radiotherapy timeline before final sign-off.",
            ]
        else:
            risk_reason = "The most recent tumor burden is higher than the baseline trend and the latest interval is not reassuring."
            next_checks = [
                "Review the latest T1C series side by side with the baseline scan.",
                "Check whether the follow-up window is post-treatment and whether the increase is expected disease evolution.",
                "Correlate with clinical symptoms and the radiotherapy timeline before final sign-off.",
            ]
    elif cumulative_change_pct <= -20:
        risk_level = "Low attention"
        risk_reason = "Tumor burden is lower than baseline and the follow-up curve is directionally favorable."
        response_label = "response"
        next_checks = [
            "Confirm the lesion segmentation still aligns with the enhancing target.",
            "Keep the follow-up cadence aligned with local neuro-oncology review practice.",
        ]
    else:
        risk_level = "Moderate attention"
        risk_reason = "The follow-up curve is mixed enough to warrant review, but not so unstable that it is clearly urgent."
        next_checks = [
            "Compare the latest scan against the prior follow-up instead of relying on baseline only.",
            "Correlate the MRI change with treatment timing and symptom trajectory.",
        ]
    return NeuroResponseSummary(
        baseline_volume_ml=round(baseline_volume, 3),
        latest_volume_ml=round(latest_volume, 3),
        previous_volume_ml=round(previous_volume, 3) if previous_volume is not None else None,
        cumulative_change_pct=cumulative_change_pct,
        annualized_change_pct=annualized_change_pct,
        recent_interval_change_pct=recent_interval_change_pct,
        recent_annualized_change_pct=recent_annualized_change_pct,
        response_label=response_label,
        risk_level=risk_level,
        risk_reason=risk_reason,
        next_checks=next_checks,
    )


def _build_report_sections(patient: dict[str, Any], response: NeuroResponseSummary) -> list[dict[str, str]]:
    return [
        {
            "title": "Exam overview",
            "body": (
                f"Longitudinal review for {patient.get('display_name', patient.get('id', 'the patient'))} "
                f"tracks a treated brain metastasis over multiple MRI timepoints."
            ),
        },
        {
            "title": "Response trend",
            "body": (
                f"Enhancing tumor burden changed from {response.baseline_volume_ml:.2f} mL at baseline to "
                f"{response.latest_volume_ml:.2f} mL at the latest follow-up, a net change of "
                f"{response.cumulative_change_pct:+.1f}%."
            ),
        },
        {
            "title": "Interpretation",
            "body": (
                f"The response label is {response.response_label.replace('_', ' ')} and the current risk tier is "
                f"{response.risk_level.lower()}. The trend warrants clinical correlation rather than automatic "
                "closure."
            ),
        },
        {
            "title": "Recommended next checks",
            "body": " ".join(response.next_checks),
        },
    ]


def _build_patient_summary(row: dict[str, str], patient_id: str, response: NeuroResponseSummary) -> dict[str, Any]:
    lesion_count = row.get("Number of metastases", "")
    lesion_location = row.get("Lesion(s) location", "")
    intervention = row.get("Type & characteristics of intervention", "")
    histology = row.get("Tumour Histology ", row.get("Tumour Histology", ""))
    sex = row.get("Gender", "")
    age = row.get("Age (yrs)", "")
    karnofsky = row.get("Karnofsky PS (%)", "")
    ps = row.get("WHO PS", "")
    return {
        "id": patient_id,
        "display_name": f"Subject {patient_id}",
        "sex": sex or "Unknown",
        "age": int(float(age)) if _safe_text(age).replace(".", "", 1).isdigit() else None,
        "histology": histology or "Unknown",
        "intervention": intervention or "Unknown",
        "lesion_count": lesion_count or "Unknown",
        "lesion_location": lesion_location or "Unknown",
        "who_ps": ps or "Unknown",
        "karnofsky_ps": karnofsky or "Unknown",
        "summary": (
            f"{histology or 'Brain metastasis'} longitudinal follow-up with {lesion_count or 'unknown'} lesion(s) "
            f"and a {response.risk_level.lower()} response signal."
        ),
    }


def _build_radiotherapy_event(row: dict[str, str], ordered_dates: list[str]) -> dict[str, Any]:
    intervention = row.get("Type & characteristics of intervention", "")
    start_date = ordered_dates[0] if ordered_dates else ""
    if not start_date:
        start_date = _excel_serial_to_iso(row.get("Brain Mets Imaging Date", ""))
    return {
        "label": "Radiotherapy",
        "date": start_date,
        "detail": intervention or "RT course recorded in clinical metadata.",
    }


def _build_timeline(
    patient_id: str,
    row: dict[str, str],
    radiomics_timeseries: dict[str, dict[str, float]],
    volumes: dict[str, dict[str, Any]],
    series_catalog: dict[str, dict[str, Any]],
) -> list[NeuroTimepointRecord]:
    labels = _select_timepoint_order(radiomics_timeseries.keys() or volumes.keys())
    ordered_dates = _ordered_imaging_dates(series_catalog)
    if len(labels) != len(ordered_dates):
        count = min(len(labels), len(ordered_dates))
        labels = labels[:count]
        ordered_dates = ordered_dates[:count]
    points: list[NeuroTimepointRecord] = []
    baseline_date = None
    previous_date = None
    for idx, (label, date) in enumerate(zip(labels, ordered_dates, strict=False)):
        volume = volumes.get(label, {})
        radiomics = radiomics_timeseries.get(label, {})
        series_for_date = series_catalog.get(date, {})
        series_refs = [
            NeuroSeriesReference(
                modality=item["modality"],
                role=item["role"],
                date=date,
                series_name=item["series_name"],
                series_member_root=item["series_member_root"],
                file_count=item["file_count"],
                representative_file=item.get("representative_file"),
            )
            for item in series_for_date.get("series", {}).values()
            if item["modality"] != "RTP"
        ]
        clinical_followup_label = {
            "baseline": "Baseline",
            "fu1": "Follow-up 1",
            "fu2": "Follow-up 2",
            "fu3": "Follow-up 3",
            "fu4": "Follow-up 4",
            "fu5": "Follow-up 5",
            "fu6": "Follow-up 6",
        }.get(label, label)
        if baseline_date is None:
            baseline_date = date
        days_from_baseline = _interval_days(baseline_date, date) if baseline_date else None
        days_from_previous = _interval_days(previous_date, date) if previous_date else None
        lesion_volume_ml, lesion_voxels, source_type, components = _primary_volume_source(radiomics, volume)
        cumulative_pct = None
        if points:
            baseline_volume = points[0].lesion_volume_ml
            cumulative_pct = 0.0 if baseline_volume == 0 else round(((lesion_volume_ml - baseline_volume) / baseline_volume) * 100.0, 1)
        interval_pct = None
        if points and points[-1].lesion_volume_ml != 0:
            interval_pct = round(((lesion_volume_ml - points[-1].lesion_volume_ml) / points[-1].lesion_volume_ml) * 100.0, 1)
        trend_source = cumulative_pct if cumulative_pct is not None else 0.0
        point = NeuroTimepointRecord(
            timepoint=label,
            study_date=date,
            clinical_label=clinical_followup_label,
            age_years=None,
            diagnosis=_safe_text(row.get("Neurocognitive status")) or None,
            lesion_volume_ml=lesion_volume_ml,
            lesion_voxels=lesion_voxels,
            source_type=source_type,
            tumor_volume_ml=components["tumor_volume_ml"],
            all_volume_ml=components["all_volume_ml"],
            oedema_volume_ml=components["oedema_volume_ml"],
            necrosis_volume_ml=components["necrosis_volume_ml"],
            interval_change_pct=interval_pct,
            cumulative_change_pct=cumulative_pct,
            interval_days=days_from_previous,
            days_from_baseline=days_from_baseline,
            trend_label=_trend_label(trend_source),
            series=series_refs,
            mask_member=volume.get("member"),
        )
        points.append(point)
        previous_date = date
    return points


def build_neuro_longitudinal_workspace(
    *,
    data_root: str | Path | None = None,
    patient_id: str = DEFAULT_PATIENT_ID,
    output_root: str | Path | None = None,
    materialize_assets: bool = True,
) -> NeuroLongitudinalWorkspace:
    resolved_root = resolve_proteas_data_root(data_root)
    if resolved_root is None:
        raise FileNotFoundError(
            f"No neuro longitudinal data root was found. Set {DEFAULT_NEURO_DATA_ENV} or pass data_root explicitly."
        )
    patient_id = _safe_text(patient_id).upper() or DEFAULT_PATIENT_ID

    archive_path = None
    for candidate in _detect_patient_archives(resolved_root):
        if candidate.name == f"{patient_id}.zip" or candidate.stem == patient_id:
            archive_path = candidate
            break
    if archive_path is None:
        raise FileNotFoundError(f"Could not find a case archive for {patient_id} under {resolved_root}")

    if archive_path.suffix.lower() == ".zip":
        names = _read_zip_names(archive_path)
    else:
        names = [str(path.relative_to(archive_path)).replace("\\", "/") for path in archive_path.rglob("*")]

    row = _load_patient_row(resolved_root, patient_id)
    radiomics = _load_radiomics_snapshot(resolved_root, patient_id)
    radiomics_timeseries = _extract_radiomics_timeseries(resolved_root, patient_id)
    series_catalog = _collect_series_catalog(names, patient_id)
    mask_volumes = _extract_timepoint_volumes(archive_path, patient_id, names)
    timeline = _build_timeline(patient_id, row, radiomics_timeseries, mask_volumes, series_catalog)
    visual_points = _visual_points_from_timeline(timeline)
    response = _analysis_from_points(visual_points)
    patient = _build_patient_summary(row, patient_id, response)
    radiotherapy = _build_radiotherapy_event(
        row,
        [_radiotherapy_event_date(series_catalog)] if _radiotherapy_event_date(series_catalog) else _ordered_imaging_dates(series_catalog),
    )

    output_base = Path(output_root or DEFAULT_OUTPUT_ROOT).expanduser().resolve() / patient_id
    trend_svg = _trend_svg(visual_points, response)
    timeline_svg = _timeline_svg(visual_points)
    comparison_svg = _comparison_svg(visual_points, response)
    viewer_payload: dict[str, Any] = {
        "available": False,
        "enabled": False,
        "default_timepoint": None,
        "timepoints": [],
        "root": str(output_base / "viewer"),
    }
    if materialize_assets:
        output_base.mkdir(parents=True, exist_ok=True)
        (output_base / "trend.svg").write_text(trend_svg, encoding="utf-8")
        (output_base / "timeline.svg").write_text(timeline_svg, encoding="utf-8")
        (output_base / "comparison.svg").write_text(comparison_svg, encoding="utf-8")
    viewer_payload = _build_viewer_manifest(
        archive_path=archive_path,
        names=names,
        patient_id=patient_id,
        timeline=timeline,
        output_base=output_base,
        materialize_assets=materialize_assets,
        visualizations=NeuroVisualizationPayload(
            trend_svg=trend_svg,
            timeline_svg=timeline_svg,
            comparison_svg=comparison_svg,
        ),
        imaging_preview={"image_url": None},
    )

    workflow = {
        "id": "post_rt_brain_met_longitudinal_review",
        "title": "Post-radiotherapy brain metastasis longitudinal review",
        "status": "ready_for_review",
        "objective": (
            "Compare longitudinal MRI timepoints, quantify treated lesion burden, align the radiotherapy event, "
            "and prepare a concise physician-facing brief."
        ),
        "last_run_at": _utc_now_iso(),
        "steps": [
            {
                "name": "Load case context",
                "tool": "neuro_longitudinal_workspace",
                "status": "completed",
                "detail": "Patient metadata, imaging series catalog, and radiomics snapshot were loaded.",
            },
            {
                "name": "Align longitudinal timeline",
                "tool": "rt_timeline_aligner",
                "status": "completed",
                "detail": "Brain MRI follow-up dates were aligned with the available radiotherapy event.",
            },
            {
                "name": "Track response trend",
                "tool": "brain_met_response_tracker",
                "status": "completed",
                "detail": "Radiomics-derived T1C tumor burden was aligned to follow-up MRI timepoints and validated against the mask assets.",
            },
            {
                "name": "Render visual summary",
                "tool": "lesion_trend_plotter",
                "status": "completed",
                "detail": "Trend, timeline, and comparison visuals were materialized as SVG payloads.",
            },
        ],
        "events": [radiotherapy],
    }

    imaging_preview = {
        "title": "Representative T1C follow-up view",
        "caption": "Longitudinal imaging review uses privacy-preserving, lesion-focused T1C views as the primary response canvas, with aligned overlay support for follow-up comparison.",
        "primary_modality": "T1C",
        "secondary_modalities": ["FLAIR", "T1W", "T2W"],
        "series_catalog": series_catalog,
        "mask_members": mask_volumes,
        "viewer": viewer_payload,
        "image_url": viewer_payload.get("fallback_image_url"),
    }

    report_sections = _build_report_sections(patient, response)
    report_context = {
        "id": f"proteas-{patient_id.lower()}-longitudinal-review",
        "title": "PROTEAS longitudinal brain metastasis review",
        "dataset": "PROTEAS / Zenodo 17253793",
        "patient": patient,
        "analysis": response.model_dump(),
        "workflow": workflow,
        "imaging_preview": {
            "title": "Representative T1C follow-up view",
            "caption": "Longitudinal imaging review uses privacy-preserving, lesion-focused T1C views as the primary response canvas, with aligned overlay support for follow-up comparison.",
            "primary_modality": "T1C",
            "secondary_modalities": ["FLAIR", "T1W", "T2W"],
            "series_catalog": series_catalog,
            "mask_members": mask_volumes,
            "viewer": viewer_payload,
        },
        "report": {
            "title": "AI longitudinal neuro-oncology review",
            "subtitle": "Concise physician-facing summary for a treated brain metastasis case",
            "risk_level": response.risk_level,
            "summary": (
                f"Longitudinal post-RT MRI review shows a {response.response_label.replace('_', ' ')} signal with "
                f"{response.cumulative_change_pct:+.1f}% net change in enhancing tumor burden from baseline and a {response.annualized_change_pct:+.1f}% annualized slope."
            ),
            "sections": report_sections,
            "physician_questions": [
                "Does the latest MRI pattern match the expected post-treatment course?",
                "Should the follow-up interval be shortened based on the latest interval slope?",
                "Are there symptoms or treatment changes that should reinterpret the imaging trend?",
            ],
        },
        "timeline": [point.model_dump() for point in timeline],
        "visualizations": {
            "trend_svg": trend_svg,
            "timeline_svg": timeline_svg,
            "comparison_svg": comparison_svg,
        },
    }
    report_bundle = build_neuro_report_bundle(report_context)
    formatted_report = export_report_bundle(
        build_report_document_from_workspace(report_context, default_title="AI longitudinal neuro-oncology review"),
        output_base / "report",
        stem="report",
        export_pdf=True,
    )
    report = {
        "title": "AI longitudinal neuro-oncology review",
        "subtitle": "Concise physician-facing summary for a treated brain metastasis case",
        "risk_level": response.risk_level,
        "summary": (
            f"Longitudinal post-RT MRI review shows a {response.response_label.replace('_', ' ')} signal with "
            f"{response.cumulative_change_pct:+.1f}% net change in enhancing tumor burden from baseline and a {response.annualized_change_pct:+.1f}% annualized slope."
        ),
        "sections": report_sections,
        "rendered_html": str(report_bundle["html"]).strip(),
        "rendered_document_html": str(formatted_report.html).strip(),
        "rendered_markdown": str(report_bundle["markdown"]).strip(),
        "rendered_bundle": formatted_report.model_dump(),
        "html_path": formatted_report.html_path,
        "json_path": formatted_report.json_path,
        "pdf_path": formatted_report.pdf_path,
        "physician_questions": [
            "Does the latest MRI pattern match the expected post-treatment course?",
            "Should the follow-up interval be shortened based on the latest interval slope?",
            "Are there symptoms or treatment changes that should reinterpret the imaging trend?",
        ],
    }

    visualization_bundle = build_neuro_visualization_bundle(
        archive_path=archive_path,
        patient_id=patient_id,
        timeline=[point.model_dump() for point in timeline],
        output_dir=output_base,
        title="PROTEAS longitudinal brain metastasis review",
    )
    visualization_payload = NeuroVisualizationPayload(
        trend_svg=trend_svg,
        timeline_svg=timeline_svg,
        comparison_svg=comparison_svg,
        viewer_manifest=visualization_bundle.viewer_manifest,
        preview_assets=[asset.model_dump() for asset in visualization_bundle.preview_assets],
        comparison_panels=visualization_bundle.comparison_panels,
        asset_paths={
            "trend_svg": str(output_base / "trend.svg"),
            "timeline_svg": str(output_base / "timeline.svg"),
            "comparison_svg": str(output_base / "comparison.svg"),
            **visualization_bundle.asset_paths,
            "report_html": formatted_report.html_path or "",
            "report_json": formatted_report.json_path or "",
            "report_pdf": formatted_report.pdf_path or "",
        },
    )

    review = {
        "status": "in_review",
        "reviewer": "Neuro-oncology reviewer",
        "comment": "Awaiting physician sign-off on the longitudinal trend and follow-up recommendation.",
        "updated_at": _utc_now_iso(),
    }

    audit = [
        {
            "id": "audit_seed_1",
            "title": "PROTEAS case loaded",
            "detail": f"Loaded {patient_id} from {archive_path.name} with longitudinal DICOM and tumor-mask assets.",
        },
        {
            "id": "audit_seed_2",
            "title": "Response payload prepared",
            "detail": "Generated longitudinal timeline, response metrics, and visualization-ready SVG payloads.",
        },
    ]

    workspace = NeuroLongitudinalWorkspace(
        id=f"proteas-{patient_id.lower()}-longitudinal-review",
        title="PROTEAS longitudinal brain metastasis review",
        dataset="PROTEAS / Zenodo 17253793",
        patient=patient,
        timeline=timeline,
        analysis=response,
        workflow=workflow,
        imaging_preview=imaging_preview,
        report=report,
        review=review,
        source={
            "data_root": str(resolved_root),
            "archive_path": str(archive_path),
            "clinical_workbook": str(resolved_root / "PROTEAS-Clinical_and_demographic_data.xlsx"),
            "radiomics_workbook": str(resolved_root / "PROTEAS-MRI_radiomics_data.xlsx"),
            "output_root": str(output_base),
            "patient_id": patient_id,
            "report_html_path": formatted_report.html_path,
            "report_json_path": formatted_report.json_path,
            "report_pdf_path": formatted_report.pdf_path,
            "visualization_manifest_path": visualization_bundle.asset_paths.get("manifest"),
        },
        series_catalog=[
            {
                "date": date,
                "series": list(info["series"].values()),
            }
            for date, info in sorted(series_catalog.items())
        ],
        radiomics=radiomics,
        visualizations=visualization_payload,
        viewer=viewer_payload,
    )
    return workspace


def summarize_neuro_longitudinal_workspace(workspace: NeuroLongitudinalWorkspace | dict[str, Any]) -> dict[str, Any]:
    payload = workspace.model_dump() if isinstance(workspace, NeuroLongitudinalWorkspace) else dict(workspace)
    timeline = payload.get("timeline", [])
    analysis = payload.get("analysis", {})
    return {
        "id": payload.get("id"),
        "title": payload.get("title"),
        "dataset": payload.get("dataset"),
        "patient": payload.get("patient", {}),
        "analysis": {
            "baseline_volume_ml": analysis.get("baseline_volume_ml"),
            "latest_volume_ml": analysis.get("latest_volume_ml"),
            "cumulative_change_pct": analysis.get("cumulative_change_pct"),
            "annualized_change_pct": analysis.get("annualized_change_pct"),
            "recent_interval_change_pct": analysis.get("recent_interval_change_pct"),
            "response_label": analysis.get("response_label"),
            "risk_level": analysis.get("risk_level"),
            "risk_reason": analysis.get("risk_reason"),
        },
        "timeline": [
            {
                "timepoint": point.get("timepoint"),
                "study_date": point.get("study_date"),
                "volume_ml": point.get("lesion_volume_ml"),
                "tumor_volume_ml": point.get("tumor_volume_ml"),
                "all_volume_ml": point.get("all_volume_ml"),
                "oedema_volume_ml": point.get("oedema_volume_ml"),
                "trend_label": point.get("trend_label"),
                "interval_change_pct": point.get("interval_change_pct"),
                "cumulative_change_pct": point.get("cumulative_change_pct"),
                "days_from_baseline": point.get("days_from_baseline"),
                "source_type": point.get("source_type"),
                "series": [
                    {
                        "modality": series.get("modality"),
                        "date": series.get("date"),
                        "series_name": series.get("series_name"),
                        "file_count": series.get("file_count"),
                    }
                    for series in point.get("series", [])
                ],
            }
            for point in timeline
        ],
        "visualizations": payload.get("visualizations", {}),
        "viewer": payload.get("viewer", {}),
        "report": {
            "title": payload.get("report", {}).get("title"),
            "summary": payload.get("report", {}).get("summary"),
            "risk_level": payload.get("report", {}).get("risk_level"),
            "sections": payload.get("report", {}).get("sections", []),
            "rendered_html": payload.get("report", {}).get("rendered_html"),
            "rendered_markdown": payload.get("report", {}).get("rendered_markdown"),
        },
        "workflow": payload.get("workflow", {}),
        "review": payload.get("review", {}),
        "source": payload.get("source", {}),
    }


def load_default_neuro_longitudinal_workspace(
    *,
    data_root: str | Path | None = None,
    patient_id: str = DEFAULT_PATIENT_ID,
) -> dict[str, Any] | None:
    resolved = resolve_proteas_data_root(data_root)
    if resolved is None:
        return None
    try:
        return summarize_neuro_longitudinal_workspace(
            build_neuro_longitudinal_workspace(data_root=resolved, patient_id=patient_id)
        )
    except Exception:
        return None
