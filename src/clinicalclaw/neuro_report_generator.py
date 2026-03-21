from __future__ import annotations

from typing import Any

from jinja2 import Environment, BaseLoader, select_autoescape


_ENV = Environment(
    loader=BaseLoader(),
    autoescape=select_autoescape(("html", "xml")),
    trim_blocks=True,
    lstrip_blocks=True,
)

_TEMPLATE = _ENV.from_string(
    """
<section class="neuro-report-surface" data-risk-tier="{{ risk_level|lower|replace(' ', '-') }}">
  <header class="neuro-report-header">
    <div>
      <p class="section-label">Physician Brief</p>
      <h4>{{ title }}</h4>
      <p class="support-copy">{{ subtitle }}</p>
    </div>
    <span class="report-risk-pill">{{ risk_level }}</span>
  </header>

  <div class="neuro-report-facts">
    <div class="report-fact"><span>Subject</span><strong>{{ patient_label }}</strong></div>
    <div class="report-fact"><span>Timepoints</span><strong>{{ point_count }}</strong></div>
    <div class="report-fact"><span>Baseline</span><strong>{{ baseline }}</strong></div>
    <div class="report-fact"><span>Latest</span><strong>{{ latest }}</strong></div>
  </div>

  <div class="neuro-report-grid">
    <article class="report-block mini">
      <h5>Overview</h5>
      <p>{{ overview }}</p>
    </article>
    <article class="report-block mini">
      <h5>Trend</h5>
      <p>{{ trend }}</p>
    </article>
    <article class="report-block mini">
      <h5>Interpretation</h5>
      <p>{{ interpretation }}</p>
    </article>
    <article class="report-block mini">
      <h5>Recommended next review focus</h5>
      <p>{{ next_check }}</p>
    </article>
  </div>

  <footer class="neuro-report-footer">
    <span>{{ footer }}</span>
  </footer>
</section>
"""
)


def _safe_text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text if text else fallback


def _fmt_float(value: Any, digits: int = 2, suffix: str = "") -> str:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{num:.{digits}f}{suffix}"


def _fmt_signed_percent(value: Any, digits: int = 1) -> str:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return "—"
    prefix = "+" if num > 0 else ""
    return f"{prefix}{num:.{digits}f}%"


def build_neuro_report_bundle(workspace: dict[str, Any] | Any) -> dict[str, Any]:
    payload = workspace.model_dump() if hasattr(workspace, "model_dump") else dict(workspace)
    patient = payload.get("patient", {})
    analysis = payload.get("analysis", {})
    report = payload.get("report", {})
    timeline = payload.get("timeline", [])
    first = timeline[0] if timeline else {}
    latest = timeline[-1] if timeline else {}
    midpoint = timeline[len(timeline) // 2] if timeline else {}
    point_count = len(timeline)

    title = _safe_text(report.get("title"), "Longitudinal neuro-oncology review")
    subtitle = _safe_text(report.get("subtitle"), "Concise physician-facing longitudinal summary")
    patient_label = _safe_text(patient.get("display_name"), _safe_text(payload.get("id"), "Case"))
    baseline = _fmt_float(analysis.get("baseline_volume_ml", first.get("lesion_volume_ml")), 2, " mL")
    latest_value = _fmt_float(analysis.get("latest_volume_ml", latest.get("lesion_volume_ml")), 2, " mL")
    overview = (
        f"{patient_label} has {point_count} longitudinal MRI timepoints "
        f"with baseline {baseline} and latest {latest_value} available for review."
    )
    trend = (
        f"{_fmt_signed_percent(analysis.get('cumulative_change_pct'))} from baseline across "
        f"{point_count} timepoints; recent interval {_fmt_signed_percent(analysis.get('recent_interval_change_pct'))}."
    )
    interpretation = _safe_text(
        analysis.get("risk_reason"),
        (
            f"Primary sequence is T1C with overlay support. "
            f"{_safe_text(midpoint.get('clinical_label'), 'Midpoint')} is available for comparison."
        ),
    )
    next_check = _safe_text(
        (report.get("physician_questions") or ["Correlate imaging trend with clinical status."])[0],
        "Correlate imaging trend with clinical status.",
    )
    footer = _safe_text(
        report.get("summary"),
        "Template-driven report bundle prepared from the longitudinal workspace.",
    )

    html = _TEMPLATE.render(
        title=title,
        subtitle=subtitle,
        patient_label=patient_label,
        point_count=point_count or 0,
        baseline=baseline,
        latest=latest_value,
        risk_level=_safe_text(analysis.get("risk_level"), "Unknown"),
        overview=overview,
        trend=trend,
        interpretation=interpretation,
        next_check=next_check,
        footer=footer,
    )

    markdown = "\n".join(
        [
            f"### {title}",
            subtitle,
            "",
            f"- Subject: **{patient_label}**",
            f"- Timepoints: **{point_count}**",
            f"- Baseline: **{baseline}**",
            f"- Latest: **{latest_value}**",
            f"- Overview: {overview}",
            f"- Trend: {trend}",
            f"- Interpretation: {interpretation}",
            f"- Next check: {next_check}",
            f"- Risk tier: **{_safe_text(analysis.get('risk_level'), 'Unknown')}**",
        ]
    )

    return {
        "title": title,
        "subtitle": subtitle,
        "patient_label": patient_label,
        "risk_level": _safe_text(analysis.get("risk_level"), "Unknown"),
        "html": html,
        "markdown": markdown,
        "summary": footer,
        "highlights": {
            "point_count": point_count,
            "baseline": baseline,
            "latest": latest_value,
            "overview": overview,
            "trend": trend,
            "interpretation": interpretation,
            "next_check": next_check,
        },
    }
