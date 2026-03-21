from __future__ import annotations

from pathlib import Path

import pytest

from clinicalclaw.neuro_longitudinal_proteas import build_neuro_longitudinal_workspace


P28_ZIP = Path("/Users/qlan/Documents/Agent/Data/17253793/P28.zip")


def test_neuro_report_contract_and_export_paths(tmp_path: Path):
    if not P28_ZIP.exists():
        pytest.skip("P28.zip is not available in the expected local data directory.")

    workspace = build_neuro_longitudinal_workspace(
        data_root=P28_ZIP.parent,
        patient_id="P28",
        output_root=tmp_path,
        materialize_assets=True,
    )

    report = workspace.report

    assert report["title"]
    assert report["rendered_html"].startswith("<section")
    assert "Trend" in report["rendered_html"]
    assert "Interpretation" in report["rendered_html"]
    assert report["rendered_document_html"].lstrip().startswith("<!doctype html>")
    assert Path(report["html_path"]).exists()
    if report.get("pdf_path"):
        assert Path(report["pdf_path"]).exists()
