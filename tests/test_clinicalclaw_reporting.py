from importlib.util import find_spec

from clinicalclaw.reporting import (
    build_report_document,
    build_report_document_from_workspace,
    export_report_bundle,
)


def test_report_document_from_workspace_extracts_compact_sections_and_metrics(tmp_path):
    trend_svg = tmp_path / "trend.svg"
    trend_svg.write_text("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 10'><rect width='10' height='10' fill='#0d6ab8'/></svg>", encoding="utf-8")

    workspace = {
        "id": "demo-case-001",
        "title": "Demo case",
        "dataset": "Synthetic clinical workflow",
        "workflow": {"id": "neuro_longitudinal", "summary": "Longitudinal review"},
        "analysis": {
            "baseline_total_ml": 6.78,
            "latest_total_ml": 5.66,
            "cumulative_change_pct": -16.5,
            "recent_segment_pct": -6.5,
            "risk_label": "High attention",
            "risk_reason": "Progressive decline with a recently steeper slope.",
        },
        "visualizations": {"trend_svg": str(trend_svg)},
        "recommended_actions": [
            "Correlate with recent cognitive testing.",
            "Confirm follow-up interval with the treating physician.",
        ],
        "evidence_grid": [
            {"label": "Baseline", "value": "6.78 ml"},
            {"label": "Latest", "value": "5.66 ml"},
        ],
        "review": {"status": "in_review", "comment": "Awaiting sign-off."},
    }

    document = build_report_document_from_workspace(workspace, default_title="Neuro longitudinal review")
    bundle = export_report_bundle(document, tmp_path / "report", stem="neuro_review", export_pdf=True)

    assert document.title == "Neuro longitudinal review"
    assert document.metrics[0].label == "Baseline"
    assert document.sections[0].title == "Signal"
    assert any(section.title == "Actions" for section in document.sections)
    assert any(section.title == "Evidence" for section in document.sections)
    assert "Longitudinal burden trend." in bundle.html
    assert bundle.html_path and (tmp_path / "report" / "neuro_review.html").exists()
    assert bundle.json_path and (tmp_path / "report" / "neuro_review.json").exists()

    weasy_available = find_spec("weasyprint") is not None
    assert bundle.pdf_supported == weasy_available
    if weasy_available:
        assert bundle.pdf_path and (tmp_path / "report" / "neuro_review.pdf").exists()
    else:
        assert bundle.pdf_path is None


def test_report_document_builds_from_generic_payload():
    document = build_report_document(
        {
            "title": "Clinical report",
            "subtitle": "Compact summary",
            "summary": "Summary text",
            "highlight": "Watch",
            "badge_label": "Watch",
            "badge_tone": "warn",
            "metrics": [{"label": "A", "value": "1"}],
            "sections": [{"title": "Signal", "body": "Body"}],
            "figures": [{"title": "Trend", "source": "<svg xmlns='http://www.w3.org/2000/svg'></svg>"}],
        }
    )

    assert document.title == "Clinical report"
    assert document.badge_tone == "warn"
    assert document.metrics[0].label == "A"
    assert document.sections[0].title == "Signal"
    assert document.figures[0].title == "Trend"
