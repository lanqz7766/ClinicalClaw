from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
import nibabel as nib

from clinicalclaw.neuro_longitudinal_proteas import build_neuro_longitudinal_workspace


P28_ZIP = Path("/Users/qlan/Documents/Agent/Data/17253793/P28.zip")


def _extract_p28_series(tmp_path: Path, series_names: list[str]) -> Path:
    if not P28_ZIP.exists():
        pytest.skip("P28.zip is not available in the expected local data directory.")

    pydicom = pytest.importorskip("pydicom")
    del pydicom

    target_root = tmp_path / "p28_sample"
    with zipfile.ZipFile(P28_ZIP) as archive:
        members = archive.namelist()
        for series_name in series_names:
            prefix = f"P28/DICOM/{series_name}/"
            matched = [member for member in members if member.startswith(prefix) and member.endswith(".dcm")]
            assert matched, f"No DICOM files found for series {series_name}"
            for member in matched:
                archive.extract(member, target_root)

    return target_root / "P28" / "DICOM"


@pytest.mark.asyncio
async def test_p28_subset_ranks_t1c_ahead_of_flar_and_supports_inventory(tmp_path: Path):
    neuro_tools = pytest.importorskip("clawagents.tools.neuro")

    raw_root = _extract_p28_series(tmp_path, ["T1C_2022-06-27", "T1C_2022-08-04", "FLR_2022-06-27"])

    tools = {tool.name: tool for tool in neuro_tools.create_neuro_tools()}

    inventory = await tools["dicom_series_inventory"].execute({"path": str(raw_root)})
    assert inventory.success is True
    inv_payload = json.loads(inventory.output)
    assert len(inv_payload["series"]) == 3
    assert inv_payload["files_scanned"] > 0
    assert inv_payload["dicom_files"] > 0
    assert inv_payload["series"][0]["sample_file"].endswith(".dcm")

    candidates = await tools["dicom_t1_candidates"].execute({"path": str(raw_root), "top_k": 2})
    assert candidates.success is True
    cand_payload = json.loads(candidates.output)
    assert cand_payload["candidates"]
    assert len(cand_payload["candidates"]) >= 1
    assert cand_payload["candidates"][0]["score"] >= cand_payload["candidates"][-1]["score"]
    assert cand_payload["candidates"][0]["sample_file"].endswith(".dcm")


def test_p28_subset_builds_a_stable_t1_raw_ingest_manifest(tmp_path: Path):
    neuro_pipeline = pytest.importorskip("clinicalclaw.neuro_pipeline")
    raw_root = _extract_p28_series(tmp_path, ["T1C_2022-06-27", "T1C_2022-08-04", "FLR_2022-06-27"])

    manifest = neuro_pipeline.build_t1_raw_ingest_manifest(
        raw_dicom_root=str(raw_root),
        subject_id="P28",
        output_root=str(tmp_path / "derived"),
        work_root=str(tmp_path / "work"),
        max_files=200,
        top_k=3,
    )

    manifest_path = neuro_pipeline.save_t1_raw_ingest_manifest(manifest, str(tmp_path / "manifest.json"))
    reloaded = neuro_pipeline.load_pipeline_manifest(manifest_path)

    assert manifest.scenario_id == "t1_raw_ingest"
    assert manifest.scheduler.queue == "neuro.t1_raw_ingest"
    assert manifest.candidate_count >= 2
    assert manifest.selected_series_instance_uid
    assert manifest.selected_candidate["sample_file"].endswith(".dcm")
    assert manifest.metadata["inventory"]["series_count"] == 3
    assert reloaded.run_id == manifest.run_id
    assert reloaded.selected_series_instance_uid == manifest.selected_series_instance_uid


def test_p28_workspace_builds_real_longitudinal_review():
    if not P28_ZIP.exists():
        pytest.skip("P28.zip is not available in the expected local data directory.")

    workspace = build_neuro_longitudinal_workspace(
        data_root=P28_ZIP.parent,
        patient_id="P28",
        materialize_assets=False,
    )

    assert workspace.id.startswith("proteas-p28")
    assert len(workspace.timeline) == 6
    assert workspace.timeline[0].timepoint == "baseline"
    assert workspace.timeline[-1].timepoint == "fu5"
    assert workspace.timeline[0].source_type == "radiomics_t1c_mesh_volume"
    assert workspace.visualizations is not None
    assert workspace.visualizations.trend_svg.startswith("<svg")
    assert workspace.visualizations.timeline_svg.startswith("<svg")
    assert workspace.visualizations.comparison_svg.startswith("<svg")
    assert len(workspace.visualizations.comparison_panels) == 3
    assert workspace.visualizations.comparison_panels[0]["label"] == "Baseline"
    assert workspace.visualizations.comparison_panels[-1]["label"] == "Latest"
    assert workspace.viewer["available"] is True
    assert workspace.viewer["enabled"] is False
    assert workspace.viewer["privacy_mode"] == "focus_crop_defaced"
    assert "neuro-report-surface" in workspace.report["rendered_html"]
    assert workspace.workflow["events"][0]["date"] == "2022-06-30"
    assert workspace.analysis.risk_level


def test_p28_materialized_viewer_assets_are_privacy_preserving(tmp_path: Path):
    if not P28_ZIP.exists():
        pytest.skip("P28.zip is not available in the expected local data directory.")

    workspace = build_neuro_longitudinal_workspace(
        data_root=P28_ZIP.parent,
        patient_id="P28",
        materialize_assets=True,
        output_root=tmp_path / "derived",
    )

    viewer = workspace.viewer
    assert viewer["available"] is True
    assert viewer["privacy_mode"] == "focus_crop_defaced"
    assert len(workspace.visualizations.comparison_panels) == 3
    assert all(panel.get("preview_path") for panel in workspace.visualizations.comparison_panels)
    first = viewer["timepoints"][0]
    image_path = tmp_path / "derived" / "P28" / "viewer" / first["timepoint"] / "t1c.nii.gz"
    assert image_path.exists()

    cropped = nib.load(str(image_path))
    with zipfile.ZipFile(P28_ZIP) as archive:
        with archive.open(f"P28/BraTS/{first['timepoint']}/t1c.nii.gz") as src:
            original_bytes = src.read()
    original_tmp = tmp_path / "original.nii.gz"
    original_tmp.write_bytes(original_bytes)
    original = nib.load(str(original_tmp))

    assert cropped.shape[0] < original.shape[0]
    assert cropped.shape[1] < original.shape[1]
