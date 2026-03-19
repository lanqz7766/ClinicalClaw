const state = {
  page: "home",
  neuroView: "command",
  safetyView: "overview",
  console: null,
  findings: {
    caseId: null,
    cases: [],
    queueSummary: null,
    workspace: null,
  },
  queue: {
    caseId: null,
    cases: [],
    queueSummary: null,
    workspace: null,
  },
  diagnosis: {
    caseId: null,
    cases: [],
    queueSummary: null,
    workspace: null,
  },
  screening: {
    caseId: null,
    cases: [],
    queueSummary: null,
    workspace: null,
  },
  neuro: {
    caseId: null,
    cases: [],
    workspace: null,
  },
  safety: {
    caseId: null,
    cases: [],
    queueSummary: null,
    workspace: null,
  },
  homeMessages: [],
};

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ error: response.statusText }));
    throw new Error(payload.error || "Request failed");
  }
  return response.json();
}

async function consumeSSE(url, body, onEvent) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok || !response.body) {
    const payload = await response.json().catch(() => ({ error: response.statusText }));
    throw new Error(payload.error || "Streaming request failed");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";
    for (const chunk of chunks) {
      const lines = chunk.split("\n");
      const eventLine = lines.find((line) => line.startsWith("event: "));
      const dataLine = lines.find((line) => line.startsWith("data: "));
      if (!eventLine || !dataLine) {
        continue;
      }
      const event = eventLine.slice(7).trim();
      const data = JSON.parse(dataLine.slice(6));
      onEvent(event, data);
    }
  }
}

function formatDate(value) {
  return new Date(value).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatTimestamp(value) {
  return new Date(value).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function titleCase(value) {
  return (value || "").replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function reviewLabel(value) {
  return titleCase(value);
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderInlineMarkdown(value) {
  return escapeHtml(value)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`(.+?)`/g, "<code>$1</code>");
}

function renderMarkdownLite(value) {
  const text = String(value || "").replace(/\r\n/g, "\n").trim();
  if (!text) {
    return "";
  }

  const blocks = text.split(/\n{2,}/);
  const html = [];

  for (const rawBlock of blocks) {
    const block = rawBlock.trim();
    if (!block) {
      continue;
    }

    if (/^-{3,}$/.test(block)) {
      html.push("<hr>");
      continue;
    }

    const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
    if (!lines.length) {
      continue;
    }

    const headingMatch = lines[0].match(/^(#{1,4})\s+(.+)$/);
    if (headingMatch && lines.length === 1) {
      const level = Math.min(headingMatch[1].length + 1, 4);
      html.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`);
      continue;
    }

    if (lines.every((line) => /^[-*]\s+/.test(line))) {
      html.push(
        `<ul>${lines
          .map((line) => `<li>${renderInlineMarkdown(line.replace(/^[-*]\s+/, ""))}</li>`)
          .join("")}</ul>`,
      );
      continue;
    }

    if (lines.every((line) => /^\d+\.\s+/.test(line))) {
      html.push(
        `<ol>${lines
          .map((line) => `<li>${renderInlineMarkdown(line.replace(/^\d+\.\s+/, ""))}</li>`)
          .join("")}</ol>`,
      );
      continue;
    }

    if (headingMatch) {
      const level = Math.min(headingMatch[1].length + 1, 4);
      html.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`);
      if (lines.length > 1) {
        html.push(`<p>${lines.slice(1).map(renderInlineMarkdown).join("<br>")}</p>`);
      }
      continue;
    }

    html.push(`<p>${lines.map(renderInlineMarkdown).join("<br>")}</p>`);
  }

  return html.join("");
}

function setPage(page) {
  state.page = page;
  document.querySelectorAll("[data-page-panel]").forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.pagePanel === page);
  });
  document.querySelectorAll(".topbar-flyout").forEach((flyout) => flyout.removeAttribute("open"));
  if (page === "home" && state.console) {
    document.getElementById("page-subtitle").textContent = state.console.tagline;
  }
}

function setSubView(group, view) {
  if (group === "neuro") {
    state.neuroView = view;
  } else {
    state.safetyView = view;
  }
  document.querySelectorAll(`[data-${group}-view]`).forEach((button) => {
    button.classList.toggle("active", button.dataset[`${group}View`] === view);
  });
  document.querySelectorAll(`[data-${group}-panel]`).forEach((panel) => {
    panel.classList.toggle("active", panel.dataset[`${group}Panel`] === view);
  });
}

function renderConsole(consolePayload) {
  document.getElementById("command-prompts").innerHTML = consolePayload.quick_prompts
    .map((item) => `<button class="prompt-chip home-prompt" data-prompt="${item}">${item}</button>`)
    .join("");
  document.getElementById("page-subtitle").textContent = consolePayload.tagline;
  const workflowMenuItems = consolePayload.workflows
    .map(
      (item) => `
        <button class="workflow-menu-item module-open" data-open-module="${item.module}" type="button" role="menuitem">
          <span>${item.title}</span>
          <small>${item.examples[0] || item.summary}</small>
        </button>
      `,
    )
    .join("");
  document.getElementById("workflow-menu-list").innerHTML = workflowMenuItems;
  const workflowCards = consolePayload.workflows
    .filter((item) => item.module !== "home")
    .map(
      (item) => `
        <article class="workflow-card">
          <p class="section-label">${titleCase(item.module)}</p>
          <h3>${item.title}</h3>
          <p class="support-copy">${item.summary}</p>
          <div class="workflow-example">${item.examples[0] || item.summary}</div>
          <div class="actions-row">
            <button class="ghost-button module-open" data-open-module="${item.module}" type="button">Open</button>
          </div>
        </article>
      `,
    )
    .join("");
  document.getElementById("landing-workflow-cards").innerHTML = workflowCards;
  document.getElementById("workflow-grid").innerHTML = workflowCards;
}

function renderHomeChat() {
  const container = document.getElementById("home-chat-log");
  container.innerHTML = state.homeMessages
    .map(
      (message) => `
        <div class="chat-bubble ${message.role}">
          <div class="chat-rich">${renderMarkdownLite(message.content)}</div>
        </div>
      `,
    )
    .join("");
  container.scrollTop = container.scrollHeight;
}

function homeSystemMessage(content) {
  return { role: "system", content };
}

function summarizeToolCall(name = "", route = {}) {
  const toolName = name.toLowerCase();
  const workflowId = route.workflow_id || "";
  const targetModule = route.target_module || route.suggested_module || "";

  if (toolName.includes("catalog") || toolName.includes("workflow")) {
    return "Reviewing the available workflows.";
  }
  if (toolName.includes("finding")) {
    return "Reviewing the relevant findings-closure context.";
  }
  if (toolName.includes("queue")) {
    return "Reviewing the relevant queue triage context.";
  }
  if (toolName.includes("diagnosis")) {
    return "Reviewing the relevant missed-diagnosis context.";
  }
  if (toolName.includes("screening")) {
    return "Reviewing the relevant screening-gap context.";
  }
  if (toolName.includes("knowledge") || toolName.includes("search")) {
    return "Checking prior safety patterns and reference signals.";
  }
  if (toolName.includes("safety")) {
    return "Reviewing the relevant safety case context.";
  }
  if (toolName.includes("neuro") || toolName.includes("workspace")) {
    return "Reviewing the longitudinal imaging context.";
  }
  if (workflowId === "radiation_safety_monitor" || targetModule === "safety") {
    return "Reviewing the relevant safety case context.";
  }
  if (workflowId === "findings_closure" || targetModule === "findings") {
    return "Reviewing the relevant findings-closure context.";
  }
  if (workflowId === "queue_triage" || targetModule === "queue") {
    return "Reviewing the relevant queue triage context.";
  }
  if (workflowId === "missed_diagnosis_detection" || targetModule === "diagnosis") {
    return "Reviewing the relevant missed-diagnosis context.";
  }
  if (workflowId === "screening_gap_closure" || targetModule === "screening") {
    return "Reviewing the relevant screening-gap context.";
  }
  if (workflowId === "neuro_longitudinal" || targetModule === "neuro") {
    return "Reviewing the longitudinal imaging context.";
  }
  return "Working through the requested clinical context.";
}

function summarizeAgentEvent(eventName, data, route = {}) {
  if (eventName === "queued") {
    return "Preparing the selected workflow.";
  }
  if (eventName === "started") {
    return "Reviewing the relevant context.";
  }
  if (eventName === "agent" && data.kind === "tool_call") {
    return summarizeToolCall(data.data?.name, route);
  }
  if (eventName === "agent" && data.kind === "tool_result") {
    return "Pulling the findings into a concise response.";
  }
  return "";
}

function renderRouterCard(payload = null) {
  const container = document.getElementById("router-card");
  if (!payload) {
    container.innerHTML = `
      <p class="router-note">Ready to route requests across the available clinical workflows.</p>
    `;
    return;
  }
  const alternatives = (payload.alternatives || [])
    .map(
      (item) =>
        `<button class="shortcut-button module-open" data-open-module="${item.module}" type="button">${item.title}</button>`,
    )
    .join("");
  const primaryModule = payload.target_module === "home" ? payload.suggested_module : payload.target_module;
  const header =
    payload.target_module === "home" ? "Suggested workflow" : "Workflow selected";
  const title = payload.workflow?.title || "General Clinical Command";
  const summary =
    payload.target_module === "home" && payload.suggested_module
      ? `${payload.reason}`
      : `${title}. ${payload.reason}`;
  container.innerHTML = `
    <div class="router-header">
      <span class="section-label">${header}</span>
      ${typeof payload.confidence === "number" && payload.confidence > 0 ? `<span class="meta-muted">${Math.round(payload.confidence * 100)}%</span>` : ""}
    </div>
    <strong>${title}</strong>
    <p class="router-note">${summary}</p>
    ${
      primaryModule && primaryModule !== "home"
        ? `<div class="actions-row compact-actions"><button class="ghost-button module-open" data-open-module="${primaryModule}" type="button">Open ${titleCase(primaryModule)}</button></div>`
        : ""
    }
    ${alternatives ? `<div class="actions-row compact-actions">${alternatives}</div>` : ""}
  `;
}

function renderNeuroCaseList() {
  const container = document.getElementById("neuro-case-list");
  container.innerHTML = state.neuro.cases
    .map(
      (item) => `
        <div class="case-item${item.id === state.neuro.caseId ? " active" : ""}">
          <button type="button" data-neuro-case-id="${item.id}">
            <div class="meta-row">
              <strong>${item.patient.display_name}</strong>
              <span>${reviewLabel(item.review.status)}</span>
            </div>
            <p>${item.patient.diagnosis}</p>
            <div class="meta-row">
              <span>${item.dataset}</span>
              <span>${item.risk_level}</span>
            </div>
          </button>
        </div>
      `,
    )
    .join("");
}

function renderFindingsCaseList() {
  const container = document.getElementById("findings-case-list");
  container.innerHTML = state.findings.cases
    .map(
      (item) => `
        <div class="case-item${item.id === state.findings.caseId ? " active" : ""}">
          <button type="button" data-findings-case-id="${item.id}">
            <div class="meta-row">
              <strong>${item.title}</strong>
              <span>${item.risk_label}</span>
            </div>
            <p>${item.workflow_title}</p>
            <div class="meta-row">
              <span>${item.queue}</span>
              <span>${formatDate(item.due_at)}</span>
            </div>
          </button>
        </div>
      `,
    )
    .join("");
}

function renderFindingsWorkspace(workspace) {
  state.findings.workspace = workspace;
  renderFindingsCaseList();
  document.getElementById("findings-title").textContent = workspace.title;
  document.getElementById("findings-summary").textContent = workspace.risk_reason;
  document.getElementById("findings-meta").innerHTML = `
    <span>${workspace.patient_label}</span>
    <span>${workspace.service_line}</span>
    <span>${workspace.queue}</span>
  `;
  document.getElementById("findings-risk-badge").textContent = workspace.risk_label;
  document.getElementById("findings-risk-badge").className = `risk-badge ${workspace.risk_tier}`;
  document.getElementById("findings-summary-cards").innerHTML = workspace.summary_cards
    .map(
      (item) => `
        <article class="summary-card">
          <span>${item.label}</span>
          <strong>${item.label === "Due" ? formatTimestamp(item.value) : item.value}</strong>
        </article>
      `,
    )
    .join("");
  document.getElementById("findings-focus").textContent = `${workspace.focus_metric.label}: ${workspace.focus_metric.value} ${workspace.focus_metric.unit} · ${workspace.focus_metric.delta}`;
  document.getElementById("findings-actions").innerHTML = workspace.recommended_actions
    .map(
      (item) => `
        <article class="report-block">
          <h4>${item}</h4>
          <p>${workspace.workflow_title}</p>
        </article>
      `,
    )
    .join("");
  document.getElementById("findings-rationale").textContent = workspace.rationale[0];
  document.getElementById("findings-evidence").innerHTML = workspace.evidence_grid
    .map(
      (item) => `
        <div class="field-chip">
          <span>${item.label}</span>
          <strong>${item.value}</strong>
        </div>
      `,
    )
    .join("");
}

function renderQueueCaseList() {
  const container = document.getElementById("queue-case-list");
  container.innerHTML = state.queue.cases
    .map(
      (item) => `
        <div class="case-item${item.id === state.queue.caseId ? " active" : ""}">
          <button type="button" data-queue-case-id="${item.id}">
            <div class="meta-row">
              <strong>${item.title}</strong>
              <span>${item.risk_label}</span>
            </div>
            <p>${item.workflow_title}</p>
            <div class="meta-row">
              <span>${item.queue}</span>
              <span>${formatDate(item.due_at)}</span>
            </div>
          </button>
        </div>
      `,
    )
    .join("");
}

function renderQueueWorkspace(workspace) {
  state.queue.workspace = workspace;
  renderQueueCaseList();
  document.getElementById("queue-title").textContent = workspace.title;
  document.getElementById("queue-subtitle").textContent = workspace.risk_reason;
  document.getElementById("queue-meta").innerHTML = `
    <span>${workspace.patient_label}</span>
    <span>${workspace.service_line}</span>
    <span>${workspace.queue}</span>
  `;
  document.getElementById("queue-risk-badge").textContent = workspace.risk_label;
  document.getElementById("queue-risk-badge").className = `risk-badge ${workspace.risk_tier}`;
  document.getElementById("queue-summary-cards").innerHTML = workspace.summary_cards
    .map(
      (item) => `
        <article class="summary-card">
          <span>${item.label}</span>
          <strong>${item.label === "Due" ? formatTimestamp(item.value) : item.value}</strong>
        </article>
      `,
    )
    .join("");
  document.getElementById("queue-focus").textContent =
    `${workspace.focus_metric.label}: ${workspace.focus_metric.value} ${workspace.focus_metric.unit} · ${workspace.focus_metric.delta}`;
  document.getElementById("queue-actions").innerHTML = workspace.recommended_actions
    .map(
      (item) => `
        <article class="report-block">
          <h4>${item}</h4>
          <p>${workspace.workflow_title}</p>
        </article>
      `,
    )
    .join("");
  document.getElementById("queue-rationale").textContent = workspace.queue_recommendation || workspace.rationale[0];
  document.getElementById("queue-evidence").innerHTML = workspace.evidence_grid
    .map(
      (item) => `
        <div class="field-chip">
          <span>${item.label}</span>
          <strong>${item.value}</strong>
        </div>
      `,
    )
    .join("");
}

function renderDiagnosisCaseList() {
  const container = document.getElementById("diagnosis-case-list");
  container.innerHTML = state.diagnosis.cases
    .map(
      (item) => `
        <div class="case-item${item.id === state.diagnosis.caseId ? " active" : ""}">
          <button type="button" data-diagnosis-case-id="${item.id}">
            <div class="meta-row">
              <strong>${item.title}</strong>
              <span>${item.risk_label}</span>
            </div>
            <p>${item.workflow_title}</p>
            <div class="meta-row">
              <span>${item.queue}</span>
              <span>${formatDate(item.due_at)}</span>
            </div>
          </button>
        </div>
      `,
    )
    .join("");
}

function renderDiagnosisWorkspace(workspace) {
  state.diagnosis.workspace = workspace;
  renderDiagnosisCaseList();
  document.getElementById("diagnosis-title").textContent = workspace.title;
  document.getElementById("diagnosis-subtitle").textContent = workspace.risk_reason;
  document.getElementById("diagnosis-meta").innerHTML = `
    <span>${workspace.patient_label}</span>
    <span>${workspace.service_line}</span>
    <span>${workspace.queue}</span>
  `;
  document.getElementById("diagnosis-risk-badge").textContent = workspace.risk_label;
  document.getElementById("diagnosis-risk-badge").className = `risk-badge ${workspace.risk_tier}`;
  document.getElementById("diagnosis-summary-cards").innerHTML = workspace.summary_cards
    .map(
      (item) => `
        <article class="summary-card">
          <span>${item.label}</span>
          <strong>${item.label === "Due" ? formatTimestamp(item.value) : item.value}</strong>
        </article>
      `,
    )
    .join("");
  document.getElementById("diagnosis-focus").textContent =
    `${workspace.focus_metric.label}: ${workspace.focus_metric.value} ${workspace.focus_metric.unit} · ${workspace.focus_metric.delta}`;
  document.getElementById("diagnosis-actions").innerHTML = workspace.recommended_actions
    .map(
      (item) => `
        <article class="report-block">
          <h4>${item}</h4>
          <p>${workspace.workflow_title}</p>
        </article>
      `,
    )
    .join("");
  document.getElementById("diagnosis-rationale").textContent = workspace.gap_recommendation || workspace.rationale[0];
  document.getElementById("diagnosis-evidence").innerHTML = workspace.evidence_grid
    .map(
      (item) => `
        <div class="field-chip">
          <span>${item.label}</span>
          <strong>${item.value}</strong>
        </div>
      `,
    )
    .join("");
}

function renderScreeningCaseList() {
  const container = document.getElementById("screening-case-list");
  container.innerHTML = state.screening.cases
    .map(
      (item) => `
        <div class="case-item${item.id === state.screening.caseId ? " active" : ""}">
          <button type="button" data-screening-case-id="${item.id}">
            <div class="meta-row">
              <strong>${item.title}</strong>
              <span>${item.risk_label}</span>
            </div>
            <p>${item.workflow_title}</p>
            <div class="meta-row">
              <span>${item.queue}</span>
              <span>${formatDate(item.due_at)}</span>
            </div>
          </button>
        </div>
      `,
    )
    .join("");
}

function renderScreeningWorkspace(workspace) {
  state.screening.workspace = workspace;
  renderScreeningCaseList();
  document.getElementById("screening-title").textContent = workspace.title;
  document.getElementById("screening-subtitle").textContent = workspace.risk_reason;
  document.getElementById("screening-meta").innerHTML = `
    <span>${workspace.patient_label}</span>
    <span>${workspace.service_line}</span>
    <span>${workspace.queue}</span>
  `;
  document.getElementById("screening-risk-badge").textContent = workspace.risk_label;
  document.getElementById("screening-risk-badge").className = `risk-badge ${workspace.risk_tier}`;
  document.getElementById("screening-summary-cards").innerHTML = workspace.summary_cards
    .map(
      (item) => `
        <article class="summary-card">
          <span>${item.label}</span>
          <strong>${item.label === "Due" ? formatTimestamp(item.value) : item.value}</strong>
        </article>
      `,
    )
    .join("");
  document.getElementById("screening-focus").textContent =
    `${workspace.focus_metric.label}: ${workspace.focus_metric.value} ${workspace.focus_metric.unit} · ${workspace.focus_metric.delta}`;
  document.getElementById("screening-actions").innerHTML = workspace.recommended_actions
    .map(
      (item) => `
        <article class="report-block">
          <h4>${item}</h4>
          <p>${workspace.workflow_title}</p>
        </article>
      `,
    )
    .join("");
  document.getElementById("screening-rationale").textContent = workspace.gap_recommendation || workspace.rationale[0];
  document.getElementById("screening-evidence").innerHTML = workspace.evidence_grid
    .map(
      (item) => `
        <div class="field-chip">
          <span>${item.label}</span>
          <strong>${item.value}</strong>
        </div>
      `,
    )
    .join("");
}

function renderUploads(uploads) {
  const container = document.getElementById("upload-list");
  container.innerHTML = uploads.length
    ? uploads
        .map(
          (item) => `
            <div class="upload-chip">
              <span>${item.filename}</span>
              <span>${formatTimestamp(item.added_at)}</span>
            </div>
          `,
        )
        .join("")
    : '<p class="support-copy">No local notes attached.</p>';
}

function renderNeuroHero(workspace) {
  const patient = workspace.patient;
  document.getElementById("patient-name").textContent = patient.display_name;
  document.getElementById("patient-summary").textContent = patient.summary;
  document.getElementById("patient-meta").innerHTML = `
    <span>ID ${patient.id}</span>
    <span>${patient.sex}</span>
    <span>Age ${patient.age}</span>
    <span>${patient.diagnosis}</span>
  `;
  document.getElementById("review-badge").textContent = reviewLabel(workspace.review.status);
  document.getElementById("risk-pill").textContent = workspace.analysis.risk_level;
}

function renderMetrics(analysis) {
  const metrics = [
    { label: "Baseline", value: `${analysis.baseline_total_ml.toFixed(2)} mL` },
    { label: "Latest", value: `${analysis.latest_total_ml.toFixed(2)} mL` },
    { label: "Annualized", value: `${analysis.annual_change_pct}% / year` },
    { label: "Recent segment", value: `${analysis.recent_segment_pct}% / year` },
  ];
  document.getElementById("metric-grid").innerHTML = metrics
    .map(
      (metric) => `
        <div class="metric">
          <span class="metric-label">${metric.label}</span>
          <span class="metric-value">${metric.value}</span>
        </div>
      `,
    )
    .join("");
}

function renderNeuroChat(messages) {
  const log = document.getElementById("chat-log");
  log.innerHTML = messages
    .slice(-6)
    .map(
      (message) => `
        <div class="chat-bubble ${message.role}">
          <div class="chat-rich">${renderMarkdownLite(message.content)}</div>
        </div>
      `,
    )
    .join("");
  log.scrollTop = log.scrollHeight;
}

function renderWorkflow(workflow) {
  document.getElementById("workflow-title").textContent = workflow.title;
  document.getElementById("workflow-objective").textContent = workflow.objective;
  document.getElementById("workflow-status").textContent = reviewLabel(workflow.status);
  document.getElementById("workflow-steps").innerHTML = workflow.steps
    .map(
      (step) => `
        <article class="workflow-step">
          <header>
            <div>
              <strong>${step.name}</strong>
              <div class="support-copy">${step.tool}</div>
            </div>
            <span class="step-badge">${step.status}</span>
          </header>
          <p>${step.detail}</p>
        </article>
      `,
    )
    .join("");
}

function renderTimeline(points) {
  document.getElementById("timeline").innerHTML = points
    .map(
      (point) => `
        <article class="timeline-card">
          <div class="meta-row">
            <strong>${formatDate(point.study_date)}</strong>
            <span>${point.sequence}</span>
          </div>
          <p>${point.diagnosis}</p>
          <div class="meta-row">
            <span>L ${point.left_hippocampus_ml.toFixed(2)} mL</span>
            <span>R ${point.right_hippocampus_ml.toFixed(2)} mL</span>
            <span>Total ${point.total_hippocampus_ml.toFixed(2)} mL</span>
          </div>
        </article>
      `,
    )
    .join("");
}

function buildChartPath(points, key, width, height, padding, min, max) {
  return points
    .map((point, index) => {
      const x = padding + (index / Math.max(points.length - 1, 1)) * (width - padding * 2);
      const ratio = (point[key] - min) / Math.max(max - min, 0.001);
      const y = height - padding - ratio * (height - padding * 2);
      return `${index === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
}

function renderChart(points) {
  const svg = document.getElementById("trend-chart");
  const width = 560;
  const height = 240;
  const padding = 28;
  const totalSeries = points.map((point) => ({
    ...point,
    total_hippocampus_ml: point.left_hippocampus_ml + point.right_hippocampus_ml,
  }));
  const allValues = [
    ...points.map((point) => point.left_hippocampus_ml),
    ...points.map((point) => point.right_hippocampus_ml),
    ...totalSeries.map((point) => point.total_hippocampus_ml),
  ];
  const min = Math.min(...allValues) - 0.08;
  const max = Math.max(...allValues) + 0.08;
  const leftPath = buildChartPath(points, "left_hippocampus_ml", width, height, padding, min, max);
  const rightPath = buildChartPath(points, "right_hippocampus_ml", width, height, padding, min, max);
  const totalPath = buildChartPath(totalSeries, "total_hippocampus_ml", width, height, padding, min, max);

  svg.innerHTML = `
    <rect x="0" y="0" width="${width}" height="${height}" rx="22" fill="white"></rect>
    <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" stroke="rgba(15,39,59,0.1)"></line>
    <line x1="${padding}" y1="${padding}" x2="${padding}" y2="${height - padding}" stroke="rgba(15,39,59,0.1)"></line>
    <path d="${leftPath}" fill="none" stroke="#0d6ab8" stroke-width="4" stroke-linecap="round"></path>
    <path d="${rightPath}" fill="none" stroke="#157d76" stroke-width="4" stroke-linecap="round"></path>
    <path d="${totalPath}" fill="none" stroke="#6e7f91" stroke-width="3" stroke-dasharray="8 7" stroke-linecap="round"></path>
  `;
}

function renderNeuroAnalysis(analysis) {
  document.getElementById("attention-banner").innerHTML = `
    <strong>High-attention longitudinal change</strong>
    <div>${analysis.risk_reason}</div>
  `;
}

function renderReport(report, preview) {
  document.getElementById("preview-image").src = preview.image_url;
  document.getElementById("preview-caption").textContent = preview.caption;
  document.getElementById("report-title").textContent = report.title;
  document.getElementById("report-summary").textContent = report.summary;
  document.getElementById("report-sections").innerHTML = report.sections
    .map(
      (section) => `
        <article class="report-block">
          <h4>${section.title}</h4>
          <p>${section.body}</p>
        </article>
      `,
    )
    .join("");
  document.getElementById("physician-questions").innerHTML = report.physician_questions
    .map((item) => `<li>${item}</li>`)
    .join("");
}

function renderNeuroReview(review, audit) {
  document.getElementById("review-comment").value = review.comment || "";
  document.getElementById("review-history").innerHTML = `
    <div class="audit-item info">
      <strong>${reviewLabel(review.status)}</strong>
      <p>${review.comment || "No reviewer comment yet."}</p>
      <div class="meta-row">
        <span>${review.reviewer}</span>
        <span>${formatTimestamp(review.updated_at)}</span>
      </div>
    </div>
  `;
  document.getElementById("audit-list").innerHTML = audit
    .slice(0, 6)
    .map(
      (item) => `
        <article class="audit-item ${item.severity}">
          <strong>${item.title}</strong>
          <p>${item.detail}</p>
          <div class="meta-row">
            <span>${item.severity}</span>
            <span>${formatTimestamp(item.created_at)}</span>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderNeuroWorkspace(workspace) {
  state.neuro.workspace = workspace;
  renderNeuroCaseList();
  renderNeuroHero(workspace);
  renderMetrics(workspace.analysis);
  renderNeuroChat(workspace.messages);
  renderWorkflow(workspace.workflow);
  renderTimeline(workspace.timeline);
  renderChart(workspace.timeline);
  renderNeuroAnalysis(workspace.analysis);
  renderReport(workspace.report, workspace.imaging_preview);
  renderNeuroReview(workspace.review, workspace.audit);
  renderUploads(workspace.uploads);
}

function renderSafetyCaseList() {
  document.getElementById("queue-summary").innerHTML = `
    <div class="queue-pill watch"><span>Watch</span><strong>${state.safety.queueSummary.watch}</strong></div>
    <div class="queue-pill alert"><span>Alert</span><strong>${state.safety.queueSummary.alert}</strong></div>
    <div class="queue-pill urgent"><span>Urgent</span><strong>${state.safety.queueSummary.urgent}</strong></div>
  `;
  document.getElementById("safety-case-list").innerHTML = state.safety.cases
    .map(
      (item) => `
        <div class="case-item${item.id === state.safety.caseId ? " active" : ""}">
          <button type="button" data-safety-case-id="${item.id}">
            <div class="meta-row">
              <strong>${item.title}</strong>
              <span class="tag-pill">${item.risk_label}</span>
            </div>
            <p>${item.owner}</p>
            <div class="meta-row">
              <span>${item.queue}</span>
              <span>${formatDate(item.received_at)}</span>
            </div>
          </button>
        </div>
      `,
    )
    .join("");
}

function renderSafetyHero(workspace) {
  document.getElementById("safety-case-title").textContent = workspace.title;
  document.getElementById("safety-case-subtitle").textContent = workspace.risk_reason;
  document.getElementById("safety-case-meta").innerHTML = `
    <span>${workspace.patient_label}</span>
    <span>${workspace.service_line}</span>
    <span>${workspace.machine}</span>
    <span>${workspace.queue}</span>
  `;
  document.getElementById("safety-risk-badge").textContent = workspace.risk_label;
  document.getElementById("safety-risk-badge").className = `risk-badge ${workspace.risk_tier}`;
  document.getElementById("safety-review-badge").textContent = titleCase(workspace.review.status);
}

function renderSafetySummaryCards(workspace) {
  document.getElementById("safety-summary-cards").innerHTML = workspace.summary_cards
    .map(
      (item) => `
        <article class="summary-card">
          <span>${item.label}</span>
          <strong>${item.label === "Due" ? formatTimestamp(item.value) : item.value}</strong>
        </article>
      `,
    )
    .join("");
}

function renderSafetyOverview(workspace) {
  const fields = {
    ...workspace.fields,
    machine: workspace.machine,
    owner: workspace.owner,
    due: formatTimestamp(workspace.due_at),
  };
  document.getElementById("intake-fields").innerHTML = Object.entries(fields)
    .map(
      ([label, value]) => `
        <div class="field-chip">
          <span>${titleCase(label)}</span>
          <strong>${value}</strong>
        </div>
      `,
    )
    .join("");
  document.getElementById("case-text").textContent = workspace.free_text;
  document.getElementById("timeline-list").innerHTML = workspace.timeline
    .map(
      (item) => `
        <article class="timeline-item">
          <strong>${item.title}</strong>
          <p>${item.detail}</p>
          <span class="meta-muted">${formatTimestamp(item.created_at)}</span>
        </article>
      `,
    )
    .join("");

  const top = workspace.matched_incidents[0];
  document.getElementById("top-match-title").textContent = top ? top.title : "No strong pattern found";
  document.getElementById("risk-summary").innerHTML = `
    <strong>${workspace.risk_label}</strong>
    <p>${workspace.risk_reason}</p>
  `;
  document.getElementById("top-match-details").innerHTML = top
    ? `
        <p class="section-label">Match rationale</p>
        <p>${top.summary}</p>
        <div class="meta-row">
          <span class="tag-pill">${top.category}</span>
          <span class="tag-pill">${top.process_step}</span>
          <span class="tag-pill">${top.evidence_level}</span>
        </div>
        <p>${top.matched_signals.join(", ")}</p>
        <p><a href="${top.source.url}" target="_blank" rel="noreferrer">${top.source.label}</a></p>
      `
    : "<p>No strong historical failure overlap was found.</p>";
}

function renderSafetyEvidence(workspace) {
  document.getElementById("match-list").innerHTML = workspace.matched_incidents
    .map(
      (item) => `
        <article class="match-card">
          <div class="meta-row">
            <h4>${item.title}</h4>
            <span class="match-score">Score ${item.score}</span>
          </div>
          <p>${item.summary}</p>
          <div class="meta-row">
            <span class="tag-pill">${item.category}</span>
            <span class="tag-pill">${item.process_step}</span>
          </div>
        </article>
      `,
    )
    .join("");
  document.getElementById("recommended-checks").innerHTML = workspace.playbook
    .map((item) => `<div class="check-item">${item}</div>`)
    .join("");
  document.getElementById("review-questions").innerHTML = workspace.review_questions
    .map((item) => `<div class="question-item">${item}</div>`)
    .join("");
  document.getElementById("email-card").innerHTML = `
    <p class="section-label">Escalation email</p>
    <p><strong>${workspace.mock_email.subject}</strong></p>
    <p>${workspace.mock_email.body}</p>
    <p class="meta-muted">${workspace.mock_email.sent ? "Prepared and marked sent" : "Prepared only"}</p>
  `;
}

function renderSafetyReview(workspace) {
  document.getElementById("safety-review-comment").value = workspace.review.comment || "";
  document.getElementById("review-history-safety").innerHTML = `
    <article class="audit-item info">
      <strong>${titleCase(workspace.review.status)}</strong>
      <p>${workspace.review.comment}</p>
      <div class="meta-row">
        <span>Last updated</span>
        <span>${formatTimestamp(workspace.review.updated_at)}</span>
      </div>
    </article>
  `;
  document.getElementById("audit-list-safety").innerHTML = workspace.audit
    .slice(0, 6)
    .map(
      (item) => `
        <article class="audit-item ${item.severity}">
          <strong>${item.title}</strong>
          <p>${item.detail}</p>
          <div class="meta-row">
            <span>${item.severity}</span>
            <span>${formatTimestamp(item.created_at)}</span>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderSafetyWorkspace(workspace) {
  state.safety.workspace = workspace;
  renderSafetyCaseList();
  renderSafetyHero(workspace);
  renderSafetySummaryCards(workspace);
  renderSafetyOverview(workspace);
  renderSafetyEvidence(workspace);
  renderSafetyReview(workspace);
}

async function loadConsole() {
  const payload = await fetchJson("/api/demo/console");
  state.console = payload;
  renderConsole(payload);
}

async function loadNeuroWorkspace(caseId = null) {
  if (caseId) {
    const workspace = await fetchJson(`/api/demo/cases/${caseId}`);
    state.neuro.caseId = caseId;
    renderNeuroWorkspace(workspace);
    return;
  }
  const payload = await fetchJson("/api/demo/workspace");
  state.neuro.caseId = payload.default_case_id;
  state.neuro.cases = payload.cases;
  renderNeuroWorkspace(payload.workspace);
}

async function loadFindingsWorkspace(caseId = null) {
  if (caseId) {
    const workspace = await fetchJson(`/api/findings/cases/${caseId}`);
    state.findings.caseId = caseId;
    renderFindingsWorkspace(workspace);
    return;
  }
  const payload = await fetchJson("/api/findings/workspace");
  state.findings.caseId = payload.default_case_id;
  state.findings.cases = payload.cases;
  state.findings.queueSummary = payload.queue_summary;
  renderFindingsWorkspace(payload.workspace);
}

async function loadQueueWorkspace(caseId = null) {
  if (caseId) {
    const workspace = await fetchJson(`/api/queue/cases/${caseId}`);
    state.queue.caseId = caseId;
    renderQueueWorkspace(workspace);
    return;
  }
  const payload = await fetchJson("/api/queue/workspace");
  state.queue.caseId = payload.default_case_id;
  state.queue.cases = payload.cases;
  state.queue.queueSummary = payload.queue_summary;
  renderQueueWorkspace(payload.workspace);
}

async function loadDiagnosisWorkspace(caseId = null) {
  if (caseId) {
    const workspace = await fetchJson(`/api/diagnosis/cases/${caseId}`);
    state.diagnosis.caseId = caseId;
    renderDiagnosisWorkspace(workspace);
    return;
  }
  const payload = await fetchJson("/api/diagnosis/workspace");
  state.diagnosis.caseId = payload.default_case_id;
  state.diagnosis.cases = payload.cases;
  state.diagnosis.queueSummary = payload.queue_summary;
  renderDiagnosisWorkspace(payload.workspace);
}

async function loadScreeningWorkspace(caseId = null) {
  if (caseId) {
    const workspace = await fetchJson(`/api/screening/cases/${caseId}`);
    state.screening.caseId = caseId;
    renderScreeningWorkspace(workspace);
    return;
  }
  const payload = await fetchJson("/api/screening/workspace");
  state.screening.caseId = payload.default_case_id;
  state.screening.cases = payload.cases;
  state.screening.queueSummary = payload.queue_summary;
  renderScreeningWorkspace(payload.workspace);
}

async function loadSafetyWorkspace(caseId = null) {
  if (caseId) {
    const workspace = await fetchJson(`/api/safety/cases/${caseId}`);
    state.safety.caseId = caseId;
    renderSafetyWorkspace(workspace);
    return;
  }
  const payload = await fetchJson("/api/safety/workspace");
  state.safety.caseId = payload.default_case_id;
  state.safety.cases = payload.cases;
  state.safety.queueSummary = payload.queue_summary;
  renderSafetyWorkspace(payload.workspace);
}

async function handleGeneralCommand(event) {
  event.preventDefault();
  const input = document.getElementById("command-input");
  const message = input.value.trim();
  if (!message) {
    return;
  }
  input.value = "";
  state.homeMessages.push({ role: "user", content: message });
  state.homeMessages.push(homeSystemMessage("Routing your request."));
  renderHomeChat();
  const pendingIndex = state.homeMessages.length - 1;
  let latestRoute = null;
  const routeCardPayload = {
    workflow: { title: "Routing..." },
    reason: "Choosing the most relevant workflow for this request.",
    suggested_steps: [],
    target_module: "home",
  };
  renderRouterCard(routeCardPayload);

  await consumeSSE("/api/demo/execute-stream", { message }, (eventName, data) => {
    if (eventName === "routed") {
      const workflow = state.console.workflows.find((item) =>
        item.id === data.workflow_id || item.module === data.target_module,
      ) || { title: titleCase(data.target_module), tools: [] };
      latestRoute = data;
      renderRouterCard({
        workflow,
        reason: data.reason,
        suggested_steps: workflow.tools || [],
        target_module: data.target_module,
        suggested_module: data.suggested_module,
        confidence: data.confidence,
        alternatives: data.alternatives || [],
      });
      state.homeMessages[pendingIndex] = {
        role: "system",
        content:
          data.target_module === "home" && data.suggested_module
            ? `${data.reason} Suggested workflow: ${workflow.title}.`
            : `${workflow.title} selected. ${data.reason}`,
      };
      renderHomeChat();
      return;
    }

    if (eventName === "queued" || eventName === "started" || eventName === "agent") {
      const summary = summarizeAgentEvent(eventName, data, latestRoute || {});
      if (!summary) {
        return;
      }
      state.homeMessages[pendingIndex] = {
        role: "system",
        content: summary,
      };
      renderHomeChat();
      return;
    }

    if (eventName === "done") {
      state.homeMessages[pendingIndex] = {
        role: "assistant",
        content: data.result || "Execution completed.",
      };
      renderHomeChat();
      return;
    }

    if (eventName === "error") {
      state.homeMessages[pendingIndex] = {
        role: "assistant",
        content: `I ran into a problem while working on that request: ${data.error}`,
      };
      renderHomeChat();
    }
  });
}

async function handleNeuroChat(event) {
  event.preventDefault();
  const input = document.getElementById("chat-input");
  const message = input.value.trim();
  if (!message || !state.neuro.caseId) {
    return;
  }
  input.value = "";
  const payload = await fetchJson("/api/demo/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ case_id: state.neuro.caseId, message }),
  });
  renderNeuroWorkspace(payload.workspace);
  setSubView("neuro", "command");
}

async function handleNeuroReview(action) {
  const comment = document.getElementById("review-comment").value.trim();
  const workspace = await fetchJson("/api/demo/review", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ case_id: state.neuro.caseId, action, comment }),
  });
  renderNeuroWorkspace(workspace);
}

async function handleUpload(files) {
  if (!state.neuro.caseId || !files.length) {
    return;
  }
  for (const file of files) {
    const workspace = await fetchJson("/api/demo/upload", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ case_id: state.neuro.caseId, filename: file.name }),
    });
    renderNeuroWorkspace(workspace);
  }
}

async function handleSafetyReview(action) {
  const comment = document.getElementById("safety-review-comment").value.trim();
  const workspace = await fetchJson("/api/safety/review", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ case_id: state.safety.caseId, action, comment }),
  });
  renderSafetyWorkspace(workspace);
}

async function rerunSafetyMatcher() {
  const workspace = await fetchJson("/api/safety/rerun", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ case_id: state.safety.caseId }),
  });
  renderSafetyWorkspace(workspace);
  setSubView("safety", "evidence");
}

function bindEvents() {
  document.querySelectorAll("[data-page]").forEach((button) => {
    button.addEventListener("click", () => setPage(button.dataset.page));
  });
  document.addEventListener("click", async (event) => {
    const moduleButton = event.target.closest("[data-open-module]");
    if (moduleButton) {
      setPage(moduleButton.dataset.openModule);
      return;
    }
    const neuroCaseButton = event.target.closest("[data-neuro-case-id]");
    if (neuroCaseButton) {
      await loadNeuroWorkspace(neuroCaseButton.dataset.neuroCaseId);
      setPage("neuro");
      return;
    }
    const safetyCaseButton = event.target.closest("[data-safety-case-id]");
    if (safetyCaseButton) {
      await loadSafetyWorkspace(safetyCaseButton.dataset.safetyCaseId);
      setPage("safety");
      return;
    }
    const findingsCaseButton = event.target.closest("[data-findings-case-id]");
    if (findingsCaseButton) {
      await loadFindingsWorkspace(findingsCaseButton.dataset.findingsCaseId);
      setPage("findings");
      return;
    }
    const queueCaseButton = event.target.closest("[data-queue-case-id]");
    if (queueCaseButton) {
      await loadQueueWorkspace(queueCaseButton.dataset.queueCaseId);
      setPage("queue");
      return;
    }
    const diagnosisCaseButton = event.target.closest("[data-diagnosis-case-id]");
    if (diagnosisCaseButton) {
      await loadDiagnosisWorkspace(diagnosisCaseButton.dataset.diagnosisCaseId);
      setPage("diagnosis");
      return;
    }
    const screeningCaseButton = event.target.closest("[data-screening-case-id]");
    if (screeningCaseButton) {
      await loadScreeningWorkspace(screeningCaseButton.dataset.screeningCaseId);
      setPage("screening");
      return;
    }
    const homePrompt = event.target.closest(".home-prompt");
    if (homePrompt) {
      document.getElementById("command-input").value = homePrompt.dataset.prompt;
      document.getElementById("command-input").focus();
      return;
    }
    const neuroPrompt = event.target.closest(".neuro-prompt");
    if (neuroPrompt) {
      document.getElementById("chat-input").value = neuroPrompt.dataset.prompt;
      document.getElementById("chat-input").focus();
      return;
    }
  });

  document.getElementById("command-form").addEventListener("submit", handleGeneralCommand);
  document.getElementById("chat-form").addEventListener("submit", handleNeuroChat);
  document.getElementById("file-input").addEventListener("change", async (event) => {
    await handleUpload(event.target.files);
    event.target.value = "";
  });
  document.querySelectorAll("[data-review-action]").forEach((button) => {
    button.addEventListener("click", () => handleNeuroReview(button.dataset.reviewAction));
  });
  document.querySelectorAll("[data-safety-review-action]").forEach((button) => {
    button.addEventListener("click", () => handleSafetyReview(button.dataset.safetyReviewAction));
  });
  document.getElementById("rerun-button").addEventListener("click", rerunSafetyMatcher);
  document.querySelectorAll("[data-neuro-view]").forEach((button) => {
    button.addEventListener("click", () => setSubView("neuro", button.dataset.neuroView));
  });
  document.querySelectorAll("[data-safety-view]").forEach((button) => {
    button.addEventListener("click", () => setSubView("safety", button.dataset.safetyView));
  });
}

window.addEventListener("DOMContentLoaded", async () => {
  bindEvents();
  state.homeMessages = [
    {
      role: "system",
      content:
        "Start with a clinical request. ClinicalClaw will route it, review the relevant context, and open the right workspace when needed.",
    },
  ];
  renderHomeChat();
  renderRouterCard();
  await Promise.all([
    loadConsole(),
    loadNeuroWorkspace(),
    loadSafetyWorkspace(),
    loadQueueWorkspace(),
    loadDiagnosisWorkspace(),
    loadScreeningWorkspace(),
  ]);
  await loadFindingsWorkspace();
  setPage("home");
  setSubView("neuro", "command");
  setSubView("safety", "overview");
});
