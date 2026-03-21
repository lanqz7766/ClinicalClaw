from __future__ import annotations

import zipfile
from pathlib import Path

import nibabel as nib
import numpy as np

from clinicalclaw.neuro_visualization import build_neuro_visualization_bundle


def _write_nifti(path: Path, data: np.ndarray) -> None:
    image = nib.Nifti1Image(data.astype(np.float32), affine=np.eye(4))
    path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(image, str(path))


def _build_synthetic_archive(tmp_path: Path) -> Path:
    source_root = tmp_path / "source"
    patient_root = source_root / "PTEST"
    baseline_volume = np.zeros((16, 16, 16), dtype=np.float32)
    baseline_volume[5:11, 5:11, 7:10] = 140.0
    followup_volume = np.zeros((16, 16, 16), dtype=np.float32)
    followup_volume[4:12, 4:12, 6:11] = 190.0

    baseline_mask = np.zeros((16, 16, 16), dtype=np.float32)
    baseline_mask[5:11, 5:11, 7:10] = 1.0
    followup_mask = np.zeros((16, 16, 16), dtype=np.float32)
    followup_mask[4:12, 4:12, 6:11] = 1.0

    _write_nifti(patient_root / "BraTS" / "baseline" / "t1c.nii.gz", baseline_volume)
    _write_nifti(patient_root / "BraTS" / "fu1" / "t1c.nii.gz", followup_volume)
    _write_nifti(patient_root / "tumor_segmentation" / "PTEST_tumor_mask_baseline.nii.gz", baseline_mask)
    _write_nifti(patient_root / "tumor_segmentation" / "PTEST_tumor_mask_fu1.nii.gz", followup_mask)

    archive_path = tmp_path / "PTEST.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(patient_root.rglob("*")):
            if file_path.is_file():
                zf.write(file_path, arcname=file_path.relative_to(source_root))
    return archive_path


def test_build_neuro_visualization_bundle_creates_manifest_and_previews(tmp_path):
    archive_path = _build_synthetic_archive(tmp_path)
    output_dir = tmp_path / "output"

    bundle = build_neuro_visualization_bundle(
        archive_path=archive_path,
        patient_id="PTEST",
        timeline=[
            {"timepoint": "baseline", "study_date": "2024-01-01"},
            {"timepoint": "fu1", "study_date": "2024-02-15"},
        ],
        output_dir=output_dir,
        title="Synthetic neuro review",
    )

    assert bundle.case_id == "PTEST"
    assert bundle.viewer == "niivue"
    assert len(bundle.preview_assets) == 2
    assert bundle.viewer_manifest["selected_timepoints"] == ["baseline", "fu1"]
    assert len(bundle.comparison_panels) == 2
    assert Path(bundle.asset_paths["manifest"]).exists()
    assert Path(bundle.preview_assets[0].slice_path).exists()
    assert Path(bundle.preview_assets[0].overlay_path or bundle.preview_assets[0].slice_path).exists()
    assert "baseline_slice" in bundle.asset_paths
    assert "fu1_overlay" in bundle.asset_paths

