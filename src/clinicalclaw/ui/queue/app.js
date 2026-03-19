const state = {
  caseId: null,
  cases: [],
  queueSummary: null,
  workspace: null,
  activeView: "overview",
};

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ error: response.statusText }));
    throw new Error(payload.error || "Request failed");
  }
  return response.json();
}

function formatTimestamp(value) {
  return new Date(value).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function setActiveView(view) {
  state.activeView = view;
  document.querySelectorAll("[data-view-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.viewTab === view);
  });
  document.querySelectorAll("[data-view-panel]").forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.viewPanel === view);
  });
}

function renderQueueSummary() {
  const queue = state.queueSummary || { watch: 0, alert: 0, urgent: 0 };
  document.getElementById("queue-summary").innerHTML = `
    <div class="summary-pill-grid">
      <div class="summary-pill watch">
        <span>Watch</span>
        <strong>${queue.watch}</strong>
      </div>
      <div class="summary-pill alert">
        <span>Alert</span>
        <strong>${queue.alert}</strong>
      </div>
      <div class="summary-pill urgent">
        <span>Urgent</span>
        <strong>${queue.urgent}</strong>
      </div>
    </div>
  `;
}

function renderCaseSelector() {
  const select = document.getElementById("case-select");
  select.innerHTML = state.cases
    .map(
      (item) => `
        <option value="${item.id}" ${item.id === state.caseId ? "selected" : ""}>
          ${item.workflow_title} · ${item.risk_label}
        </option>
      `,
    )
    .join("");
}

function renderRail(workspace) {
  document.getElementById("rail-case-title").textContent = workspace.workflow_title;
  document.getElementById("rail-case-subtitle").textContent = workspace.title;
  const badge = document.getElementById("rail-risk-badge");
  badge.textContent = workspace.risk_label;
  badge.className = `risk-badge ${workspace.risk_tier}`;
  document.getElementById("rail-meta").innerHTML = `
    <div class="rail-meta-item">
      <span class="small-label">Owner</span>
      <strong>${workspace.owner}</strong>
    </div>
    <div class="rail-meta-item">
      <span class="small-label">Due</span>
      <strong>${formatTimestamp(workspace.due_at)}</strong>
    </div>
    <div class="rail-meta-item">
      <span class="small-label">Queue</span>
      <strong>${workspace.queue}</strong>
    </div>
  `;
  document.getElementById("rail-explain").textContent = workspace.rationale[0];
}

function renderHero(workspace) {
  document.getElementById("case-title").textContent = workspace.title;
  document.getElementById("case-subtitle").textContent = workspace.risk_reason;
  document.getElementById("case-meta").innerHTML = `
    <span class="meta-chip">${workspace.patient_label}</span>
    <span class="meta-chip">${workspace.service_line}</span>
    <span class="meta-chip">${workspace.queue}</span>
  `;
  const riskBadge = document.getElementById("risk-badge");
  riskBadge.textContent = workspace.risk_label;
  riskBadge.className = `risk-badge ${workspace.risk_tier}`;
  document.getElementById("workflow-chip").textContent = workspace.workflow_title;
  const scoreMap = { watch: 40, alert: 76, urgent: 95 };
  document.getElementById("signal-score").textContent = scoreMap[workspace.risk_tier] ?? 60;
}

function renderFocusMetric(workspace) {
  document.getElementById("focus-label").textContent = workspace.focus_metric.label;
  document.getElementById("focus-value").textContent = workspace.focus_metric.value;
  document.getElementById("focus-unit").textContent = workspace.focus_metric.unit;
  document.getElementById("focus-delta").textContent = workspace.focus_metric.delta;
  const tone = document.getElementById("signal-tone");
  tone.textContent = workspace.risk_label;
  tone.className = `signal-tone ${workspace.focus_metric.tone}`;
}

function renderSummaryCards(workspace) {
  document.getElementById("summary-cards").innerHTML = workspace.summary_cards
    .map(
      (item) => `
        <div class="summary-card ${item.tone}">
          <span>${item.label}</span>
          <strong>${item.label === "Due" ? formatTimestamp(item.value) : item.value}</strong>
        </div>
      `,
    )
    .join("");
}

function renderTrend(workspace) {
  const points = workspace.trend_points || [];
  const svg = document.getElementById("trend-chart");
  if (!points.length) {
    svg.innerHTML = "";
    document.getElementById("trend-legend").innerHTML = "";
    return;
  }
  const width = 360;
  const height = 160;
  const paddingX = 24;
  const paddingY = 18;
  const values = points.map((item) => item.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, 1);
  const stepX = (width - paddingX * 2) / Math.max(points.length - 1, 1);
  const toX = (index) => paddingX + index * stepX;
  const toY = (value) => height - paddingY - ((value - min) / span) * (height - paddingY * 2);
  const path = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${toX(index)} ${toY(point.value)}`)
    .join(" ");
  const area = `${path} L ${toX(points.length - 1)} ${height - paddingY} L ${toX(0)} ${height - paddingY} Z`;
  const circles = points
    .map(
      (point, index) =>
        `<circle cx="${toX(index)}" cy="${toY(point.value)}" r="4.5" fill="#127064"></circle>`,
    )
    .join("");
  svg.innerHTML = `
    <defs>
      <linearGradient id="queueTrendFill" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="rgba(18, 112, 100, 0.26)" />
        <stop offset="100%" stop-color="rgba(18, 112, 100, 0.02)" />
      </linearGradient>
    </defs>
    <path d="${area}" fill="url(#queueTrendFill)"></path>
    <path d="${path}" fill="none" stroke="#127064" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>
    ${circles}
  `;
  document.getElementById("trend-legend").innerHTML = points
    .map((point) => `<span>${point.label} · ${point.value}</span>`)
    .join("");
}

function renderSteps(workspace) {
  document.getElementById("status-steps").innerHTML = workspace.status_steps
    .map(
      (item) => `
        <div class="step ${item.state}">
          <strong>${item.title}</strong>
          <span>${item.state === "done" ? "Done" : item.state === "current" ? "Current" : "Upcoming"}</span>
        </div>
      `,
    )
    .join("");
  document.getElementById("reason-card").innerHTML = `
    <strong>Why this moved up</strong>
    <p>${workspace.rationale[0]}</p>
  `;
}

function renderEvidence(workspace) {
  document.getElementById("evidence-grid").innerHTML = workspace.evidence_grid
    .map(
      (item) => `
        <div class="evidence-item">
          <strong>${item.label}</strong>
          <p>${item.value}</p>
        </div>
      `,
    )
    .join("");
}

function renderTimeline(workspace) {
  document.getElementById("timeline-list").innerHTML = workspace.timeline
    .map(
      (item) => `
        <article class="timeline-item">
          <strong>${item.title}</strong>
          <p>${item.detail}</p>
          <div class="meta-row"><span>${formatTimestamp(item.created_at)}</span></div>
        </article>
      `,
    )
    .join("");
}

function renderActions(workspace) {
  document.getElementById("action-list").innerHTML = workspace.recommended_actions
    .map(
      (item) => `
        <div class="action-item">
          <strong>${item}</strong>
          <p>${workspace.queue_recommendation || workspace.workflow_title}</p>
        </div>
      `,
    )
    .join("");
  document.getElementById("email-card").innerHTML = `
    <strong>${workspace.mock_email.subject}</strong>
    <p>${workspace.mock_email.body}</p>
    <div class="meta-row">
      <span>${workspace.mock_email.to}</span>
      <span>${workspace.mock_email.sent ? "Prepared + sent" : "Draft only"}</span>
    </div>
  `;
  document.getElementById("chat-log").innerHTML = `
    <div class="chat-bubble">
      <strong>Workflow summary</strong>
      <p>${workspace.risk_label} queue item for ${workspace.workflow_title}. Current disposition: ${workspace.disposition.replace(/_/g, " ")}.</p>
    </div>
  `;
}

function renderReview(workspace) {
  document.getElementById("review-comment").value = workspace.review.comment || "";
  document.getElementById("review-history").innerHTML = `
    <strong>${workspace.review.status.replace(/_/g, " ")}</strong>
    <p>${workspace.review.comment}</p>
    <div class="meta-row"><span>${formatTimestamp(workspace.review.updated_at)}</span></div>
  `;
  document.getElementById("audit-list").innerHTML = workspace.audit
    .slice(0, 6)
    .map(
      (item) => `
        <article class="audit-item ${item.severity}">
          <strong>${item.title}</strong>
          <p>${item.detail}</p>
          <div class="meta-row"><span>${formatTimestamp(item.created_at)}</span></div>
        </article>
      `,
    )
    .join("");
}

function renderWorkspace(workspace) {
  state.workspace = workspace;
  state.cases = state.cases.map((item) =>
    item.id === workspace.id
      ? {
          ...item,
          risk_tier: workspace.risk_tier,
          risk_label: workspace.risk_label,
          owner: workspace.owner,
          queue: workspace.queue,
          due_at: workspace.due_at,
        }
      : item,
  );
  renderQueueSummary();
  renderCaseSelector();
  renderRail(workspace);
  renderHero(workspace);
  renderFocusMetric(workspace);
  renderSummaryCards(workspace);
  renderTrend(workspace);
  renderSteps(workspace);
  renderEvidence(workspace);
  renderTimeline(workspace);
  renderActions(workspace);
  renderReview(workspace);
}

async function loadWorkspace(caseId = null) {
  if (caseId) {
    const workspace = await fetchJson(`/api/queue/cases/${caseId}`);
    state.caseId = caseId;
    renderWorkspace(workspace);
    return;
  }
  const payload = await fetchJson("/api/queue/workspace");
  state.caseId = payload.default_case_id;
  state.cases = payload.cases;
  state.queueSummary = payload.queue_summary;
  renderWorkspace(payload.workspace);
}

async function rerunCase() {
  if (!state.caseId) return;
  const workspace = await fetchJson("/api/queue/rerun", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ case_id: state.caseId }),
  });
  renderWorkspace(workspace);
}

async function askQuestion(event) {
  event.preventDefault();
  const input = document.getElementById("question-input");
  const question = input.value.trim();
  if (!question || !state.caseId) return;
  const response = await fetchJson("/api/queue/explain", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ case_id: state.caseId, question }),
  });
  input.value = "";
  renderWorkspace(response.workspace);
  document.getElementById("chat-log").innerHTML += `
    <div class="chat-bubble">
      <strong>Workflow answer</strong>
      <p>${response.answer}</p>
    </div>
  `;
}

async function reviewCase(action) {
  if (!state.caseId) return;
  const comment = document.getElementById("review-comment").value.trim();
  const workspace = await fetchJson("/api/queue/review", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ case_id: state.caseId, action, comment }),
  });
  renderWorkspace(workspace);
}

function bindEvents() {
  document.getElementById("case-select").addEventListener("change", (event) => {
    loadWorkspace(event.target.value);
  });
  document.getElementById("rerun-button").addEventListener("click", rerunCase);
  document.getElementById("question-form").addEventListener("submit", askQuestion);
  document.querySelectorAll("[data-review-action]").forEach((button) => {
    button.addEventListener("click", () => reviewCase(button.dataset.reviewAction));
  });
  document.querySelectorAll("[data-view-tab]").forEach((button) => {
    button.addEventListener("click", () => setActiveView(button.dataset.viewTab));
  });
  document.querySelectorAll(".prompt-chip").forEach((button) => {
    button.addEventListener("click", () => {
      document.getElementById("question-input").value = button.dataset.question;
      document.getElementById("question-form").requestSubmit();
    });
  });
}

async function init() {
  bindEvents();
  await loadWorkspace();
}

window.addEventListener("DOMContentLoaded", init);
