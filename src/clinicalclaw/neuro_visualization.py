from __future__ import annotations

import json
import re
import tempfile
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


def _mask_bounds(mask: np.ndarray | None) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]] | None:
    if mask is None or mask.ndim < 3 or not np.any(mask > 0):
        return None
    coords = np.argwhere(mask > 0)
    mins = coords.min(axis=0)
    maxs = coords.max(axis=0) + 1
    return tuple((int(mins[idx]), int(maxs[idx])) for idx in range(3))


def _fallback_volume_bounds(volume: np.ndarray) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    shape = volume.shape[:3]
    finite = volume[np.isfinite(volume)]
    positive = finite[finite > 0]
    threshold = float(np.percentile(positive, 15)) if positive.size else 0.0
    active = np.argwhere(volume > threshold)
    if active.size == 0:
        return tuple((0, int(shape[idx])) for idx in range(3))
    mins = active.min(axis=0)
    maxs = active.max(axis=0) + 1
    return tuple((int(mins[idx]), int(maxs[idx])) for idx in range(3))


def _expand_bounds(
    bounds: tuple[tuple[int, int], tuple[int, int], tuple[int, int]],
    shape: tuple[int, int, int],
    padding: tuple[int, int, int] = (40, 40, 18),
) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    expanded: list[tuple[int, int]] = []
    for idx, (start, end) in enumerate(bounds):
        pad = padding[idx]
        expanded.append((max(start - pad, 0), min(end + pad, shape[idx])))
    return tuple(expanded)


def _square_inplane_bounds(
    bounds: tuple[tuple[int, int], tuple[int, int], tuple[int, int]],
    shape: tuple[int, int, int],
    *,
    min_size: int = 176,
) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    x_bounds, y_bounds, z_bounds = bounds
    x_center = (x_bounds[0] + x_bounds[1]) / 2
    y_center = (y_bounds[0] + y_bounds[1]) / 2
    side = max(x_bounds[1] - x_bounds[0], y_bounds[1] - y_bounds[0], min_size)

    def _axis_window(center: float, axis_size: int) -> tuple[int, int]:
        if side >= axis_size:
            return (0, axis_size)
        start = int(round(center - side / 2))
        end = start + int(side)
        if start < 0:
            end -= start
            start = 0
        if end > axis_size:
            start -= end - axis_size
            end = axis_size
        start = max(start, 0)
        end = min(end, axis_size)
        return (start, end)

    return (
        _axis_window(x_center, shape[0]),
        _axis_window(y_center, shape[1]),
        z_bounds,
    )


def _focus_crop_arrays(
    volume: np.ndarray,
    mask: np.ndarray | None = None,
    padding: tuple[int, int, int] = (40, 40, 18),
) -> tuple[np.ndarray, np.ndarray | None, tuple[tuple[int, int], tuple[int, int], tuple[int, int]]]:
    shape = tuple(int(value) for value in volume.shape[:3])
    base_bounds = _mask_bounds(mask) or _fallback_volume_bounds(volume)
    bounds = _square_inplane_bounds(_expand_bounds(base_bounds, shape, padding=padding), shape)
    slices = tuple(slice(start, end) for start, end in bounds)
    cropped_volume = volume[slices]
    cropped_mask = mask[slices] if mask is not None else None
    return cropped_volume, cropped_mask, bounds


def _crop_nifti_pair(
    image_path: Path,
    mask_path: Path | None,
    output_image_path: Path,
    output_mask_path: Path | None = None,
    extra_modalities: list[tuple[Path, Path]] | None = None,
) -> dict[str, Any]:
    image = nib.load(str(image_path))
    image_data = image.get_fdata(dtype=np.float32)
    if image_data.ndim == 4:
        image_data = image_data[..., 0]

    mask_image = nib.load(str(mask_path)) if mask_path and mask_path.exists() else None
    mask_data = None
    if mask_image is not None:
        mask_data = mask_image.get_fdata(dtype=np.float32)
        if mask_data.ndim == 4:
            mask_data = mask_data[..., 0]

    _, _, bounds = _focus_crop_arrays(image_data, mask_data)
    slices = tuple(slice(start, end) for start, end in bounds)

    output_image_path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(image.slicer[slices], str(output_image_path))

    if mask_image is not None and output_mask_path is not None:
        output_mask_path.parent.mkdir(parents=True, exist_ok=True)
        nib.save(mask_image.slicer[slices], str(output_mask_path))

    written_modalities: dict[str, str] = {}
    for source_path, target_path in extra_modalities or []:
        extra_image = nib.load(str(source_path))
        target_path.parent.mkdir(parents=True, exist_ok=True)
        nib.save(extra_image.slicer[slices], str(target_path))
        written_modalities[target_path.stem] = str(target_path)

    return {
        "bounds": bounds,
        "image_path": str(output_image_path),
        "mask_path": str(output_mask_path) if output_mask_path else None,
        "extra_paths": written_modalities,
        "privacy_mode": "focus_crop_defaced",
    }


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


def _contain_image(
    image: Image.Image,
    size: tuple[int, int] = (320, 320),
    background: tuple[int, int, int, int] = (12, 18, 24, 255),
) -> Image.Image:
    canvas = Image.new("RGBA", size, background)
    contained = image.copy()
    contained.thumbnail(size, Image.Resampling.LANCZOS)
    offset = ((size[0] - contained.width) // 2, (size[1] - contained.height) // 2)
    canvas.alpha_composite(contained, offset)
    return canvas


def _merge_bounds(
    bounds_list: list[tuple[tuple[int, int], tuple[int, int], tuple[int, int]]],
    shape: tuple[int, int, int],
    padding: tuple[int, int, int] = (40, 40, 18),
) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    if not bounds_list:
        return tuple((0, int(shape[idx])) for idx in range(3))
    merged: list[tuple[int, int]] = []
    for axis in range(3):
        axis_min = min(bounds[axis][0] for bounds in bounds_list)
        axis_max = max(bounds[axis][1] for bounds in bounds_list)
        merged.append((axis_min, axis_max))
    return _square_inplane_bounds(_expand_bounds(tuple(merged), shape, padding=padding), shape)


def _save_preview_pair(
    volume_path: Path,
    mask_path: Path | None,
    output_dir: Path,
    stem: str,
    bounds: tuple[tuple[int, int], tuple[int, int], tuple[int, int]] | None = None,
    slice_index_override: int | None = None,
) -> dict[str, Any]:
    volume = _load_volume(volume_path)
    mask = _load_volume(mask_path) if mask_path and mask_path.exists() else None
    if bounds is None:
        cropped_volume, cropped_mask, bounds = _focus_crop_arrays(volume, mask)
    else:
        slices = tuple(slice(start, end) for start, end in bounds)
        cropped_volume = volume[slices]
        cropped_mask = mask[slices] if mask is not None else None
    slice_index = (
        int(np.clip(slice_index_override - bounds[2][0], 0, cropped_volume.shape[2] - 1))
        if slice_index_override is not None
        else _select_axial_index(cropped_volume, cropped_mask)
    )
    base = _slice_to_image(cropped_volume, slice_index)
    base = _contain_image(base)
    slice_path = output_dir / f"{stem}_slice.png"
    base.save(slice_path)

    overlay_path = None
    if cropped_mask is not None:
        overlay = _mask_to_overlay(cropped_mask, slice_index)
        overlay = _contain_image(overlay, background=(0, 0, 0, 0))
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
        "privacy_mode": "focus_crop_defaced",
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
    extracted_assets: list[dict[str, Any]] = []
    shared_bounds_list: list[tuple[tuple[int, int], tuple[int, int], tuple[int, int]]] = []
    shared_centers: list[int] = []
    shared_shape: tuple[int, int, int] | None = None

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

        volume = _load_volume(image_path)
        mask = _load_volume(mask_path) if mask_path and mask_path.exists() else None
        shared_shape = tuple(int(value) for value in volume.shape[:3])
        local_bounds = _mask_bounds(mask) or _fallback_volume_bounds(volume)
        shared_bounds_list.append(local_bounds)
        if mask is not None and np.any(mask > 0):
            coords = np.argwhere(mask > 0)
            shared_centers.append(int(np.round(coords[:, 2].mean())))
        extracted_assets.append(
            {
                "timepoint": timepoint,
                "study_date": study_date,
                "image_path": image_path,
                "mask_path": mask_path,
            }
        )

    shared_bounds = _merge_bounds(shared_bounds_list, shared_shape) if shared_shape and shared_bounds_list else None
    shared_slice_index = int(np.round(np.mean(shared_centers))) if shared_centers else None

    for asset in extracted_assets:
        preview = _save_preview_pair(
            asset["image_path"],
            asset["mask_path"],
            target_dir,
            f"{asset['timepoint']}_{primary_modality}",
            bounds=shared_bounds,
            slice_index_override=shared_slice_index,
        )
        preview_assets.append(
            NeuroSlicePreview(
                timepoint=asset["timepoint"],
                study_date=asset["study_date"],
                modality=primary_modality.upper(),
                image_path=str(asset["image_path"]),
                mask_path=str(asset["mask_path"]) if asset["mask_path"] else None,
                slice_path=str(preview["slice_path"]),
                overlay_path=str(preview["overlay_path"]) if preview["overlay_path"] else None,
                slice_index=int(preview["slice_index"]),
                caption=_figure_caption(asset["timepoint"], primary_modality.upper(), bool(asset["mask_path"])),
            )
        )
        manifest_volumes.append(
            {
                "timepoint": asset["timepoint"],
                "study_date": asset["study_date"],
                "modality": primary_modality.upper(),
                "volume_path": str(asset["image_path"]),
                "mask_path": str(asset["mask_path"]) if asset["mask_path"] else None,
                "display_name": f"{asset['timepoint']} {primary_modality.upper()}",
            }
        )
        if asset["mask_path"]:
            manifest_overlays.append(
                {
                    "timepoint": asset["timepoint"],
                    "study_date": asset["study_date"],
                    "mask_path": str(asset["mask_path"]),
                    "label": "Tumor mask",
                }
            )

    if preview_assets:
        picked = [preview_assets[0]]
        if len(preview_assets) > 2:
            picked.append(preview_assets[len(preview_assets) // 2])
        if len(preview_assets) > 1:
            picked.append(preview_assets[-1])
        seen: set[str] = set()
        ordered_panels: list[NeuroSlicePreview] = []
        for item in picked:
            if item.timepoint in seen:
                continue
            seen.add(item.timepoint)
            ordered_panels.append(item)
        labels = ["Baseline", "Mid follow-up", "Latest"]
        for index, item in enumerate(ordered_panels):
            comparison_panels.append(
                {
                    "label": labels[min(index, len(labels) - 1)],
                    "timepoint": item.timepoint,
                    "image_path": item.image_path,
                    "overlay_path": item.overlay_path,
                    "preview_path": item.overlay_path or item.slice_path,
                    "study_date": item.study_date,
                }
            )

    manifest = {
        "viewer": "niivue",
        "case_id": patient_id,
        "title": title,
        "asset_root": str(target_dir),
        "privacy_mode": "focus_crop_defaced",
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


def materialize_privacy_preserving_viewer_assets(
    *,
    archive_path: str | Path,
    image_member: str,
    output_image_path: str | Path,
    mask_member: str | None = None,
    output_mask_path: str | Path | None = None,
    flair_member: str | None = None,
    output_flair_path: str | Path | None = None,
) -> dict[str, Any]:
    archive = Path(archive_path).expanduser().resolve()
    out_image = Path(output_image_path).expanduser().resolve()
    out_mask = Path(output_mask_path).expanduser().resolve() if output_mask_path else None
    out_flair = Path(output_flair_path).expanduser().resolve() if output_flair_path else None

    with tempfile.TemporaryDirectory(prefix="clinicalclaw-neuro-") as temp_dir:
        temp_root = Path(temp_dir)
        extracted_image = _extract_member(archive, image_member, temp_root)
        extracted_mask = _extract_member(archive, mask_member, temp_root) if mask_member else None
        extra_modalities: list[tuple[Path, Path]] = []
        if flair_member and out_flair is not None:
            extracted_flair = _extract_member(archive, flair_member, temp_root)
            extra_modalities.append((extracted_flair, out_flair))
        result = _crop_nifti_pair(
            extracted_image,
            extracted_mask,
            out_image,
            output_mask_path=out_mask,
            extra_modalities=extra_modalities,
        )
    return result
