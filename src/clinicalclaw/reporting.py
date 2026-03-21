from __future__ import annotations

import json
from html import escape as html_escape
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

try:  # pragma: no cover - exercised in integration tests when available
    from jinja2 import BaseLoader, Environment, select_autoescape
except ImportError:  # pragma: no cover - fallback path
    Environment = None
    BaseLoader = object  # type: ignore[assignment]
    select_autoescape = None  # type: ignore[assignment]


_REPORT_TEMPLATE = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{{ document.title }}</title>
    <style>
      :root {
        color-scheme: light;
        --bg: #f5f7f4;
        --panel: rgba(255, 255, 255, 0.9);
        --panel-strong: rgba(255, 255, 255, 0.98);
        --border: rgba(19, 31, 43, 0.08);
        --text: #13202c;
        --muted: #607282;
        --accent: #0d6ab8;
        --accent-soft: rgba(13, 106, 184, 0.1);
        --good: #2f8f6f;
        --warn: #b26a2d;
        --danger: #c14553;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        background:
          radial-gradient(circle at top right, rgba(13, 106, 184, 0.08), transparent 34%),
          radial-gradient(circle at bottom left, rgba(47, 143, 111, 0.06), transparent 28%),
          var(--bg);
        color: var(--text);
        font-family: "Inter", "Manrope", "Avenir Next", "Segoe UI", sans-serif;
        line-height: 1.5;
      }
      .page {
        max-width: 1100px;
        margin: 0 auto;
        padding: 36px 24px 48px;
      }
      .hero {
        display: grid;
        grid-template-columns: minmax(0, 1.8fr) minmax(260px, 1fr);
        gap: 20px;
        align-items: stretch;
        margin-bottom: 20px;
      }
      .hero-card,
      .panel {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 24px;
        box-shadow: 0 14px 38px rgba(10, 22, 34, 0.06);
        backdrop-filter: blur(10px);
      }
      .hero-card {
        padding: 28px 30px;
      }
      .eyebrow {
        margin: 0 0 10px;
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: var(--accent);
      }
      h1 {
        margin: 0;
        font-size: 2rem;
        line-height: 1.15;
      }
      .subtitle {
        margin: 10px 0 0;
        color: var(--muted);
        max-width: 68ch;
      }
      .summary {
        margin-top: 18px;
        padding-top: 18px;
        border-top: 1px solid var(--border);
        color: var(--text);
      }
      .summary strong { color: var(--accent); }
      .summary-strip {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 12px;
        margin-top: 18px;
      }
      .metric {
        padding: 14px 16px;
        border-radius: 18px;
        background: var(--panel-strong);
        border: 1px solid var(--border);
      }
      .metric span {
        display: block;
      }
      .metric-label {
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--muted);
        margin-bottom: 6px;
      }
      .metric-value {
        font-size: 1.02rem;
        font-weight: 700;
      }
      .status-card {
        padding: 24px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        gap: 16px;
      }
      .status-chip {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        width: fit-content;
        padding: 8px 12px;
        border-radius: 999px;
        background: var(--accent-soft);
        color: var(--accent);
        font-size: 0.88rem;
        font-weight: 700;
      }
      .status-chip.danger { background: rgba(193, 69, 83, 0.1); color: var(--danger); }
      .status-chip.warn { background: rgba(178, 106, 45, 0.12); color: var(--warn); }
      .status-chip.good { background: rgba(47, 143, 111, 0.12); color: var(--good); }
      .panel {
        padding: 20px 22px;
        margin-top: 16px;
      }
      .panel h2 {
        margin: 0 0 12px;
        font-size: 1.05rem;
      }
      .section-list {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 14px;
      }
      .section {
        border: 1px solid var(--border);
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.78);
        padding: 16px 16px 14px;
      }
      .section h3 {
        margin: 0 0 8px;
        font-size: 0.92rem;
      }
      .section p {
        margin: 0;
        color: var(--text);
        font-size: 0.95rem;
      }
      .section ul {
        margin: 10px 0 0;
        padding-left: 18px;
        color: var(--text);
      }
      .section li + li { margin-top: 6px; }
      .figure-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
        gap: 14px;
      }
      .figure {
        border: 1px solid var(--border);
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.84);
        padding: 14px;
      }
      .figure h3 {
        margin: 0 0 10px;
        font-size: 0.92rem;
      }
      .figure img, .figure svg {
        max-width: 100%;
        display: block;
        border-radius: 14px;
      }
      .figure figcaption {
        margin-top: 8px;
        color: var(--muted);
        font-size: 0.86rem;
      }
      .footer {
        margin-top: 18px;
        color: var(--muted);
        font-size: 0.88rem;
      }
      .figure-text {
        margin-top: 10px;
        font-size: 0.84rem;
        color: var(--muted);
      }
      .figure-text code {
        padding: 2px 6px;
        border-radius: 999px;
        background: rgba(13, 106, 184, 0.08);
        color: var(--accent);
      }
    </style>
  </head>
  <body>
    <main class="page">
      <section class="hero">
        <article class="hero-card">
          <p class="eyebrow">{{ document.audience }}</p>
          <h1>{{ document.title }}</h1>
          {% if document.subtitle %}
            <p class="subtitle">{{ document.subtitle }}</p>
          {% endif %}
          {% if document.summary %}
            <p class="summary">{{ document.summary }}</p>
          {% endif %}
          {% if document.metrics %}
            <div class="summary-strip">
              {% for metric in document.metrics %}
                <div class="metric">
                  <span class="metric-label">{{ metric.label }}</span>
                  <span class="metric-value">{{ metric.value }}</span>
                  {% if metric.caption %}
                    <span class="figure-text">{{ metric.caption }}</span>
                  {% endif %}
                </div>
              {% endfor %}
            </div>
          {% endif %}
        </article>

        <aside class="panel status-card">
          <div>
            <span class="status-chip {{ document.badge_tone }}">{{ document.badge_label }}</span>
            {% if document.highlight %}
              <p class="summary" style="margin-top: 14px;">{{ document.highlight }}</p>
            {% endif %}
          </div>
          {% if document.footer %}
            <div class="footer">{{ document.footer }}</div>
          {% endif %}
        </aside>
      </section>

      {% if document.figures %}
        <section class="panel">
          <h2>Visual Summary</h2>
          <div class="figure-grid">
            {% for figure in document.figures %}
              <figure class="figure">
                <h3>{{ figure.title }}</h3>
                {{ figure.rendered_markup | safe }}
                {% if figure.caption %}
                  <figcaption>{{ figure.caption }}</figcaption>
                {% endif %}
                {% if figure.notes %}
                  <div class="figure-text">
                    {% for note in figure.notes %}
                      <div>• {{ note }}</div>
                    {% endfor %}
                  </div>
                {% endif %}
              </figure>
            {% endfor %}
          </div>
        </section>
      {% endif %}

      {% if document.sections %}
        <section class="panel">
          <h2>Report Sections</h2>
          <div class="section-list">
            {% for section in document.sections %}
              <article class="section">
                <h3>{{ section.title }}</h3>
                <p>{{ section.body }}</p>
                {% if section.bullets %}
                  <ul>
                    {% for bullet in section.bullets %}
                      <li>{{ bullet }}</li>
                    {% endfor %}
                  </ul>
                {% endif %}
              </article>
            {% endfor %}
          </div>
        </section>
      {% endif %}
    </main>
  </body>
</html>
"""


class ReportMetric(BaseModel):
    label: str
    value: str
    caption: str | None = None


class ReportSection(BaseModel):
    title: str
    body: str
    bullets: list[str] = Field(default_factory=list)


class ReportFigure(BaseModel):
    title: str
    source: str
    caption: str = ""
    notes: list[str] = Field(default_factory=list)
    kind: str = "image"


class ReportDocument(BaseModel):
    title: str
    subtitle: str = ""
    audience: str = "Clinical report"
    summary: str = ""
    highlight: str = ""
    badge_label: str = "Ready"
    badge_tone: str = "good"
    metrics: list[ReportMetric] = Field(default_factory=list)
    sections: list[ReportSection] = Field(default_factory=list)
    figures: list[ReportFigure] = Field(default_factory=list)
    footer: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReportBundle(BaseModel):
    document: ReportDocument
    html: str
    html_path: str | None = None
    json_path: str | None = None
    pdf_path: str | None = None
    pdf_supported: bool = False


def _coerce_metric(value: Any) -> ReportMetric:
    if isinstance(value, ReportMetric):
        return value
    if isinstance(value, dict):
        return ReportMetric(
            label=str(value.get("label", "Metric")),
            value=str(value.get("value", "")),
            caption=value.get("caption"),
        )
    return ReportMetric(label="Metric", value=str(value))


def _coerce_section(value: Any) -> ReportSection:
    if isinstance(value, ReportSection):
        return value
    if isinstance(value, dict):
        bullets = value.get("bullets") or []
        if isinstance(bullets, str):
            bullets = [bullets]
        return ReportSection(
            title=str(value.get("title", "Section")),
            body=str(value.get("body", "")),
            bullets=[str(item) for item in bullets],
        )
    return ReportSection(title="Section", body=str(value))


def _coerce_figure(value: Any) -> ReportFigure:
    if isinstance(value, ReportFigure):
        return value
    if isinstance(value, dict):
        return ReportFigure(
            title=str(value.get("title", "Figure")),
            source=str(value.get("source", "")),
            caption=str(value.get("caption", "")),
            notes=[str(item) for item in value.get("notes", []) or []],
            kind=str(value.get("kind", "image")),
        )
    return ReportFigure(title="Figure", source=str(value))


def _html_figure_markup(figure: ReportFigure) -> str:
    source = figure.source.strip()
    if not source:
        return ""
    if source.startswith("<svg"):
        return source
    if source.startswith("data:"):
        return f'<img src="{source}" alt="{html_escape(figure.title)}" />'
    path = Path(source)
    if path.exists() and path.suffix.lower() == ".svg":
        return path.read_text(encoding="utf-8")
    if path.exists():
        resolved = path.as_posix()
        return f'<img src="{html_escape(resolved)}" alt="{html_escape(figure.title)}" />'
    if source.endswith(".svg"):
        return f'<img src="{html_escape(source)}" alt="{html_escape(figure.title)}" />'
    return f'<img src="{html_escape(source)}" alt="{html_escape(figure.title)}" />'


def build_report_document(payload: dict[str, Any]) -> ReportDocument:
    metrics = payload.get("metrics") or []
    sections = payload.get("sections") or []
    figures = payload.get("figures") or []
    return ReportDocument(
        title=str(payload.get("title") or "Clinical report"),
        subtitle=str(payload.get("subtitle") or payload.get("sub_title") or ""),
        audience=str(payload.get("audience") or "Clinical report"),
        summary=str(payload.get("summary") or ""),
        highlight=str(payload.get("highlight") or payload.get("badge") or ""),
        badge_label=str(payload.get("badge_label") or payload.get("risk_label") or "Ready"),
        badge_tone=str(payload.get("badge_tone") or payload.get("tone") or "good"),
        metrics=[_coerce_metric(item) for item in metrics],
        sections=[_coerce_section(item) for item in sections],
        figures=[_coerce_figure(item) for item in figures],
        footer=str(payload.get("footer") or ""),
        metadata=dict(payload.get("metadata") or {}),
    )


def build_report_document_from_workspace(workspace: dict[str, Any], *, default_title: str | None = None) -> ReportDocument:
    report = workspace.get("report") or {}
    analysis = workspace.get("analysis") or {}
    workflow = workspace.get("workflow") or {}
    imaging_preview = workspace.get("imaging_preview") or {}
    visualizations = workspace.get("visualizations") or {}
    summary_cards = workspace.get("summary_cards") or []
    risk_reason = (
        report.get("summary")
        or analysis.get("risk_reason")
        or workspace.get("risk_reason")
        or workspace.get("queue_recommendation")
        or workspace.get("gap_recommendation")
        or ""
    )
    highlight = report.get("risk_level") or analysis.get("risk_level") or workspace.get("risk_label") or ""
    footer = report.get("physician_questions", [None])[0] if report.get("physician_questions") else ""

    if report.get("sections"):
        sections = report.get("sections", [])
    else:
        sections = []
        lead_body = risk_reason or workflow.get("objective") or workflow.get("summary") or ""
        if lead_body:
            sections.append({"title": "Signal", "body": lead_body})
        if workspace.get("recommended_actions"):
            sections.append(
                {
                    "title": "Actions",
                    "body": "Recommended next steps are captured as concise operational actions.",
                    "bullets": list(workspace.get("recommended_actions", [])[:3]),
                }
            )
        elif workspace.get("playbook"):
            sections.append(
                {
                    "title": "Actions",
                    "body": "Recommended checks and closure steps for the current case.",
                    "bullets": list(workspace.get("playbook", [])[:3]),
                }
            )
        elif report.get("physician_questions"):
            sections.append(
                {
                    "title": "Recommendations",
                    "body": "Review the case in context and confirm the next action.",
                    "bullets": report.get("physician_questions", [])[:3],
                }
            )
        evidence_items = workspace.get("evidence_grid") or workspace.get("matched_incidents") or []
        if evidence_items:
            bullets: list[str] = []
            for item in evidence_items[:3]:
                if isinstance(item, dict):
                    bullets.append(
                        ", ".join(
                            part
                            for part in [
                                str(item.get("label") or item.get("title") or item.get("category") or ""),
                                str(item.get("value") or item.get("summary") or item.get("score") or ""),
                            ]
                            if part
                        )
                    )
                else:
                    bullets.append(str(item))
            sections.append(
                {
                    "title": "Evidence",
                    "body": "Structured evidence supporting the current disposition.",
                    "bullets": bullets,
                }
            )
        if workspace.get("review"):
            review = workspace.get("review") or {}
            sections.append(
                {
                    "title": "Review",
                    "body": f"Review status: {review.get('status', 'in_review')}.",
                    "bullets": [str(review.get("comment"))] if review.get("comment") else [],
                }
            )

    metrics: list[dict[str, Any]] = []
    if analysis:
        for label, key in [
            ("Baseline", "baseline_total_ml"),
            ("Latest", "latest_total_ml"),
            ("Net change", "cumulative_change_pct"),
            ("Recent interval", "recent_segment_pct"),
        ]:
            value = analysis.get(key)
            if value is None:
                continue
            if isinstance(value, (int, float)):
                text = f"{value:+.1f}%" if "change" in key or "interval" in key else f"{value:.2f} mL"
            else:
                text = str(value)
            metrics.append({"label": label, "value": text})
    if not metrics and summary_cards:
        for item in summary_cards[:4]:
            metrics.append({"label": item.get("label", "Metric"), "value": str(item.get("value", ""))})
    if not metrics and workspace.get("summary_cards"):
        for item in workspace.get("summary_cards", [])[:4]:
            metrics.append({"label": item.get("label", "Metric"), "value": str(item.get("value", ""))})

    figures: list[dict[str, Any]] = []
    if visualizations.get("trend_svg"):
        figures.append(
            {
                "title": "Trend",
                "source": visualizations["trend_svg"],
                "caption": "Longitudinal burden trend.",
                "kind": "svg",
            }
        )
    if visualizations.get("timeline_svg"):
        figures.append(
            {
                "title": "Timeline",
                "source": visualizations["timeline_svg"],
                "caption": "Treatment-aligned event path.",
                "kind": "svg",
            }
        )
    if visualizations.get("comparison_svg"):
        figures.append(
            {
                "title": "Comparison",
                "source": visualizations["comparison_svg"],
                "caption": "Baseline / midpoint / latest comparison.",
                "kind": "svg",
            }
        )
    if imaging_preview.get("image_url"):
        figures.append(
            {
                "title": imaging_preview.get("title", "Preview"),
                "source": imaging_preview["image_url"],
                "caption": imaging_preview.get("caption", ""),
                "kind": "image",
            }
        )

    return build_report_document(
        {
            "title": report.get("title") or default_title or workspace.get("title") or "Clinical report",
            "subtitle": report.get("subtitle") or workspace.get("dataset") or workflow.get("summary") or "",
            "summary": risk_reason,
            "highlight": highlight,
            "badge_label": highlight or "Ready",
            "badge_tone": _badge_tone(highlight or "ready"),
            "metrics": metrics,
            "sections": sections,
            "figures": figures,
            "footer": footer,
            "metadata": {
                "case_id": workspace.get("id"),
                "patient_id": (workspace.get("patient") or {}).get("id"),
                "workflow_id": workflow.get("id"),
                "dataset": workspace.get("dataset"),
            },
        }
    )


def _badge_tone(label: str) -> str:
    normalized = label.lower()
    if "urgent" in normalized or "danger" in normalized:
        return "danger"
    if "alert" in normalized or "watch" in normalized:
        return "warn"
    return "good"


def _render_html_with_jinja(document: ReportDocument) -> str:
    if Environment is None:
        raise RuntimeError("Jinja2 is not available")
    env = Environment(
        loader=BaseLoader(),
        autoescape=select_autoescape(default=True, enabled_extensions=("html", "xml")) if select_autoescape else True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.from_string(_REPORT_TEMPLATE)
    payload = document.model_dump()
    for figure in payload["figures"]:
        figure["rendered_markup"] = _html_figure_markup(ReportFigure.model_validate(figure))
    return template.render(document=payload)


def _render_html_fallback(document: ReportDocument) -> str:
    def render_metric(metric: ReportMetric) -> str:
        caption = f'<span class="figure-text">{html_escape(metric.caption)}</span>' if metric.caption else ""
        return (
            '<div class="metric">'
            f'<span class="metric-label">{html_escape(metric.label)}</span>'
            f'<span class="metric-value">{html_escape(metric.value)}</span>'
            f"{caption}"
            "</div>"
        )

    def render_section(section: ReportSection) -> str:
        bullets = ""
        if section.bullets:
            bullets = "<ul>" + "".join(f"<li>{html_escape(item)}</li>" for item in section.bullets) + "</ul>"
        return (
            '<article class="section">'
            f'<h3>{html_escape(section.title)}</h3>'
            f"<p>{html_escape(section.body)}</p>"
            f"{bullets}"
            "</article>"
        )

    def render_figure(figure: ReportFigure) -> str:
        markup = _html_figure_markup(figure)
        notes = "".join(f"<div>• {html_escape(note)}</div>" for note in figure.notes)
        caption = f"<figcaption>{html_escape(figure.caption)}</figcaption>" if figure.caption else ""
        return (
            '<figure class="figure">'
            f"<h3>{html_escape(figure.title)}</h3>"
            f"{markup}"
            f"{caption}"
            + (f'<div class="figure-text">{notes}</div>' if notes else "")
            + "</figure>"
        )

    hero_metrics = "".join(render_metric(metric) for metric in document.metrics)
    figures = "".join(render_figure(figure) for figure in document.figures)
    sections = "".join(render_section(section) for section in document.sections)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{html_escape(document.title)}</title>
    <style>
      body {{ font-family: Inter, Manrope, Segoe UI, sans-serif; margin: 0; background: #f5f7f4; color: #13202c; }}
      .page {{ max-width: 1100px; margin: 0 auto; padding: 36px 24px 48px; }}
      .hero, .panel {{ background: rgba(255,255,255,0.92); border: 1px solid rgba(19,31,43,0.08); border-radius: 24px; }}
      .hero {{ display: grid; grid-template-columns: minmax(0,1.8fr) minmax(260px,1fr); gap: 20px; padding: 0; margin-bottom: 20px; }}
      .hero-card {{ padding: 28px 30px; }}
      .panel {{ padding: 20px 22px; margin-top: 16px; }}
      .summary-strip, .figure-grid, .section-list {{ display: grid; gap: 14px; }}
      .summary-strip {{ grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); margin-top: 18px; }}
      .figure-grid {{ grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }}
      .section-list {{ grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }}
      .metric, .figure, .section, .status-card {{ border: 1px solid rgba(19,31,43,0.08); border-radius: 18px; background: rgba(255,255,255,0.84); }}
      .metric {{ padding: 14px 16px; }}
      .metric-label {{ display: block; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: #607282; margin-bottom: 6px; }}
      .metric-value {{ font-size: 1.02rem; font-weight: 700; }}
      .status-card {{ padding: 24px; display: flex; flex-direction: column; justify-content: space-between; gap: 16px; }}
      .status-chip {{ display: inline-flex; padding: 8px 12px; border-radius: 999px; background: rgba(47,143,111,0.12); color: #2f8f6f; font-size: 0.88rem; font-weight: 700; }}
      .status-chip.warn {{ background: rgba(178,106,45,0.12); color: #b26a2d; }}
      .status-chip.danger {{ background: rgba(193,69,83,0.12); color: #c14553; }}
      h1 {{ margin: 0; font-size: 2rem; line-height: 1.15; }}
      .eyebrow {{ margin: 0 0 10px; font-size: 0.74rem; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase; color: #0d6ab8; }}
      .subtitle {{ margin: 10px 0 0; color: #607282; }}
      .summary {{ margin-top: 18px; padding-top: 18px; border-top: 1px solid rgba(19,31,43,0.08); }}
      .figure img, .figure svg {{ max-width: 100%; border-radius: 14px; display: block; }}
      .footer {{ margin-top: 18px; color: #607282; font-size: 0.88rem; }}
      .figure-text {{ margin-top: 10px; font-size: 0.84rem; color: #607282; }}
      .figure-text code {{ padding: 2px 6px; border-radius: 999px; background: rgba(13,106,184,0.08); color: #0d6ab8; }}
      .section h3, .figure h3 {{ margin: 0 0 8px; font-size: 0.92rem; }}
      .section p {{ margin: 0; }}
      .section ul {{ margin: 10px 0 0; padding-left: 18px; }}
      figcaption {{ margin-top: 8px; color: #607282; font-size: 0.86rem; }}
    </style>
  </head>
  <body>
    <main class="page">
      <section class="hero">
        <article class="hero-card">
          <p class="eyebrow">{html_escape(document.audience)}</p>
          <h1>{html_escape(document.title)}</h1>
          {f'<p class="subtitle">{html_escape(document.subtitle)}</p>' if document.subtitle else ''}
          {f'<p class="summary">{html_escape(document.summary)}</p>' if document.summary else ''}
          {f'<div class="summary-strip">{hero_metrics}</div>' if document.metrics else ''}
        </article>
        <aside class="panel status-card">
          <div>
            <span class="status-chip {html_escape(document.badge_tone)}">{html_escape(document.badge_label)}</span>
            {f'<p class="summary" style="margin-top: 14px;">{html_escape(document.highlight)}</p>' if document.highlight else ''}
          </div>
          {f'<div class="footer">{html_escape(document.footer)}</div>' if document.footer else ''}
        </aside>
      </section>
      {f'<section class="panel"><h2>Visual Summary</h2><div class="figure-grid">{figures}</div></section>' if document.figures else ''}
      {f'<section class="panel"><h2>Report Sections</h2><div class="section-list">{sections}</div></section>' if document.sections else ''}
    </main>
  </body>
</html>
"""


def render_report_html(document: ReportDocument | dict[str, Any]) -> str:
    report = document if isinstance(document, ReportDocument) else build_report_document(document)
    if Environment is not None:
        return _render_html_with_jinja(report)
    return _render_html_fallback(report)


def render_report_pdf(html: str, output_path: str | Path) -> str | None:
    if find_spec("weasyprint") is None:
        return None
    from weasyprint import HTML  # pragma: no cover - optional dependency path

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html, base_url=str(target.parent)).write_pdf(str(target))
    return str(target)


def export_report_bundle(
    document: ReportDocument | dict[str, Any],
    output_dir: str | Path,
    *,
    stem: str = "report",
    export_pdf: bool = False,
) -> ReportBundle:
    report = document if isinstance(document, ReportDocument) else build_report_document(document)
    target_dir = Path(output_dir).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    html = render_report_html(report)
    html_path = target_dir / f"{stem}.html"
    json_path = target_dir / f"{stem}.json"
    html_path.write_text(html, encoding="utf-8")
    json_path.write_text(json.dumps(report.model_dump(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    pdf_path = target_dir / f"{stem}.pdf"
    pdf_supported = False
    pdf_value: str | None = None
    if export_pdf:
        pdf_value = render_report_pdf(html, pdf_path)
        pdf_supported = pdf_value is not None
    else:
        pdf_supported = find_spec("weasyprint") is not None

    return ReportBundle(
        document=report,
        html=html,
        html_path=str(html_path),
        json_path=str(json_path),
        pdf_path=pdf_value,
        pdf_supported=pdf_supported,
    )
