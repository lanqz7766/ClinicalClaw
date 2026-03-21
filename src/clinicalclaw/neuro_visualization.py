from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any, Iterable

import nibabel as nib
import numpy as np
from PIL import Image
from pydantic import BaseModel, Field


class NeuroSlicePreview(BaseModel):
    timepoint: str
    study_date: str | None = None
    modality: str = "T1C"
    image_path: str
    mask_path: str | None = None
    slice_path: str
    overlay_path: str | None = None
    slice_index: int
    caption: str


class NeuroVisualizationBundle(BaseModel):
    viewer: str = "niivue"
    case_id: str
    title: str
    asset_root: str
    preview_assets: list[NeuroSlicePreview] = Field(default_factory=list)
    viewer_manifest: dict[str, Any] = Field(default_factory=dict)
    comparison_panels: list[dict[str, Any]] = Field(default_factory=list)
    asset_paths: dict[str, str] = Field(default_factory=dict)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _choose_timepoints(timeline: list[dict[str, Any]], limit: int | None = None) -> list[dict[str, Any]]:
    if not timeline:
        return []
    if limit is None or len(timeline) <= limit:
        return timeline
    if len(timeline) <= 3:
        return timeline
    selected = [timeline[0], timeline[len(timeline) // 2], timeline[-1]]
    if len(timeline) >= 4:
        for item in timeline:
            if item not in selected and item.get("timepoint") == "fu1":
                selected.insert(1, item)
                break
    return selected[:limit]


def _extract_member(archive: Path, member: str, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        if member not in zf.namelist():
            raise FileNotFoundError(member)
        extracted = zf.extract(member, target_dir)
    return Path(extracted).resolve()


def _load_volume(path: Path) -> np.ndarray:
    image = nib.load(str(path))
    data = image.get_fdata(dtype=np.float32)
    if data.ndim == 4:
        data = data[..., 0]
    return np.asarray(data)


def _select_axial_index(volume: np.ndarray, mask: np.ndarray | None = None) -> int:
    if mask is not None and mask.ndim >= 3 and np.any(mask > 0):
        coords = np.argwhere(mask > 0)
        return int(np.clip(np.round(coords[:, 2].mean()), 0, volume.shape[2] - 1))
    return int(volume.shape[2] // 2)


def _slice_to_image(volume: np.ndarray, index: int) -> Image.Image:
    slice_data = volume[:, :, index].astype(np.float32)
    finite = slice_data[np.isfinite(slice_data)]
    if finite.size:
        low = float(np.percentile(finite, 2))
        high = float(np.percentile(finite, 98))
        if high <= low:
            high = low + 1.0
    else:
        low, high = 0.0, 1.0
    clipped = np.clip(slice_data, low, high)
    normalized = ((clipped - low) / max(high - low, 1e-6) * 255.0).astype(np.uint8)
    return Image.fromarray(normalized, mode="L").convert("RGBA")


def _mask_to_overlay(mask: np.ndarray, index: int) -> Image.Image:
    mask_slice = mask[:, :, index] > 0
    overlay = Image.new("RGBA", (mask_slice.shape[1], mask_slice.shape[0]), (255, 255, 255, 0))
    pixels = overlay.load()
    for y in range(mask_slice.shape[0]):
        for x in range(mask_slice.shape[1]):
            if mask_slice[y, x]:
                pixels[x, y] = (197, 69, 83, 140)
    return overlay


def _save_preview_pair(volume_path: Path, mask_path: Path | None, output_dir: Path, stem: str) -> dict[str, Any]:
    volume = _load_volume(volume_path)
    mask = _load_volume(mask_path) if mask_path and mask_path.exists() else None
    slice_index = _select_axial_index(volume, mask)
    base = _slice_to_image(volume, slice_index)
    base = base.resize((320, 320), Image.Resampling.BILINEAR)
    slice_path = output_dir / f"{stem}_slice.png"
    base.save(slice_path)

    overlay_path = None
    if mask is not None:
        overlay = _mask_to_overlay(mask, slice_index)
        overlay = overlay.resize((320, 320), Image.Resampling.NEAREST)
        composite = base.copy()
        composite.alpha_composite(overlay)
        overlay_path = output_dir / f"{stem}_overlay.png"
        composite.save(overlay_path)
    else:
        overlay_path = slice_path

    return {
        "slice_index": slice_index,
        "slice_path": slice_path,
        "overlay_path": overlay_path,
    }


def _figure_caption(timepoint: str, modality: str, is_overlay: bool) -> str:
    if is_overlay:
        return f"{timepoint} {modality} with tumor overlay."
    return f"{timepoint} {modality} central slice."


def _infer_brats_member(patient_id: str, timepoint: str, modality: str) -> str:
    modality = modality.lower()
    if modality not in {"t1c", "t1", "t2", "fla", "flair"}:
        modality = "t1c"
    if modality == "flair":
        modality = "fla"
    return f"{patient_id}/BraTS/{timepoint}/{modality}.nii.gz"


def _infer_mask_member(patient_id: str, timepoint: str) -> str:
    return f"{patient_id}/tumor_segmentation/{patient_id}_tumor_mask_{timepoint}.nii.gz"


def build_neuro_visualization_bundle(
    *,
    archive_path: str | Path,
    patient_id: str,
    timeline: list[dict[str, Any]],
    output_dir: str | Path,
    title: str,
    primary_modality: str = "t1c",
    secondary_modality: str = "fla",
) -> NeuroVisualizationBundle:
    archive = Path(archive_path).expanduser().resolve()
    if not archive.exists():
        raise FileNotFoundError(str(archive))

    target_dir = Path(output_dir).expanduser().resolve() / "visuals" / patient_id.lower()
    extracted_dir = target_dir / "extracted"
    target_dir.mkdir(parents=True, exist_ok=True)

    selected = _choose_timepoints(timeline)
    preview_assets: list[NeuroSlicePreview] = []
    manifest_volumes: list[dict[str, Any]] = []
    manifest_overlays: list[dict[str, Any]] = []
    comparison_panels: list[dict[str, Any]] = []

    for item in selected:
        timepoint = _safe_text(item.get("timepoint"))
        study_date = _safe_text(item.get("study_date")) or None
        if not timepoint:
            continue
        image_member = _infer_brats_member(patient_id, timepoint, primary_modality)
        mask_member = _infer_mask_member(patient_id, timepoint)
        try:
            image_path = _extract_member(archive, image_member, extracted_dir)
        except FileNotFoundError:
            continue
        mask_path = None
        try:
            mask_path = _extract_member(archive, mask_member, extracted_dir)
        except FileNotFoundError:
            mask_path = None

        preview = _save_preview_pair(image_path, mask_path, target_dir, f"{timepoint}_{primary_modality}")
        preview_assets.append(
            NeuroSlicePreview(
                timepoint=timepoint,
                study_date=study_date,
                modality=primary_modality.upper(),
                image_path=str(image_path),
                mask_path=str(mask_path) if mask_path else None,
                slice_path=str(preview["slice_path"]),
                overlay_path=str(preview["overlay_path"]) if preview["overlay_path"] else None,
                slice_index=int(preview["slice_index"]),
                caption=_figure_caption(timepoint, primary_modality.upper(), bool(mask_path)),
            )
        )
        manifest_volumes.append(
            {
                "timepoint": timepoint,
                "study_date": study_date,
                "modality": primary_modality.upper(),
                "volume_path": str(image_path),
                "mask_path": str(mask_path) if mask_path else None,
                "display_name": f"{timepoint} {primary_modality.upper()}",
            }
        )
        if mask_path:
            manifest_overlays.append(
                {
                    "timepoint": timepoint,
                    "study_date": study_date,
                    "mask_path": str(mask_path),
                    "label": "Tumor mask",
                }
            )

    if preview_assets:
        first = preview_assets[0]
        latest = preview_assets[-1]
        comparison_panels.extend(
            [
                {
                    "label": "Baseline",
                    "timepoint": first.timepoint,
                    "image_path": first.image_path,
                    "overlay_path": first.overlay_path,
                    "preview_path": first.overlay_path or first.slice_path,
                },
                {
                    "label": "Latest",
                    "timepoint": latest.timepoint,
                    "image_path": latest.image_path,
                    "overlay_path": latest.overlay_path,
                    "preview_path": latest.overlay_path or latest.slice_path,
                },
            ]
        )

    manifest = {
        "viewer": "niivue",
        "case_id": patient_id,
        "title": title,
        "asset_root": str(target_dir),
        "volumes": manifest_volumes,
        "overlays": manifest_overlays,
        "selected_timepoints": [item.timepoint for item in preview_assets],
        "viewer_options": {
            "show3D": True,
            "crosshairColor": "#0d6ab8",
            "useInterpolation": False,
            "sliceType": "axial",
        },
    }
    manifest_path = target_dir / "niivue_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    asset_paths = {
        "manifest": str(manifest_path),
        "asset_root": str(target_dir),
        "extracted_root": str(extracted_dir),
    }
    for preview in preview_assets:
        asset_paths[f"{preview.timepoint}_slice"] = preview.slice_path
        if preview.overlay_path:
            asset_paths[f"{preview.timepoint}_overlay"] = preview.overlay_path

    return NeuroVisualizationBundle(
        viewer="niivue",
        case_id=patient_id,
        title=title,
        asset_root=str(target_dir),
        preview_assets=preview_assets,
        viewer_manifest=manifest,
        comparison_panels=comparison_panels,
        asset_paths=asset_paths,
    )
