const state = {
  caseId: null,
  cases: [],
  knowledgeBase: [],
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

function formatCompactTimestamp(value) {
  return new Date(value).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
  });
}

function titleCase(value) {
  return (value || "").replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
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
    <div class="queue-pill watch">
      <span>Watch</span>
      <strong>${queue.watch}</strong>
    </div>
    <div class="queue-pill alert">
      <span>Alert</span>
      <strong>${queue.alert}</strong>
    </div>
    <div class="queue-pill urgent">
      <span>Urgent</span>
      <strong>${queue.urgent}</strong>
    </div>
  `;
}

function renderCaseList() {
  const container = document.getElementById("case-list");
  container.innerHTML = state.cases
    .map(
      (item) => `
        <div class="case-item${item.id === state.caseId ? " active" : ""}">
          <button type="button" data-case-id="${item.id}">
            <div class="meta-row">
              <strong>${item.title}</strong>
              <span class="tag-pill">${item.risk_label}</span>
            </div>
            <p class="meta-muted">${item.owner} · ${item.queue}</p>
            <div class="meta-row">
              <span>${titleCase(item.status)}</span>
              <span>${formatCompactTimestamp(item.received_at)}</span>
            </div>
          </button>
        </div>
      `,
    )
    .join("");
}

function renderKnowledgeBase(items) {
  document.getElementById("kb-list").innerHTML = items
    .map(
      (item) => `
        <article class="kb-item">
          <strong>${item.title}</strong>
          <p class="support-copy">${item.category} · ${item.process_step}</p>
          <div class="meta-row">
            <span class="tag-pill">${titleCase(item.severity_hint)}</span>
            <span class="meta-muted">${item.evidence_level}</span>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderHero(workspace) {
  document.getElementById("case-title").textContent = workspace.title;
  document.getElementById("case-subtitle").textContent = workspace.risk_reason;
  document.getElementById("case-meta").innerHTML = `
    <span>${workspace.patient_label}</span>
    <span>${workspace.service_line}</span>
    <span>${workspace.machine}</span>
    <span>${workspace.fields.stage}</span>
  `;
  const riskBadge = document.getElementById("risk-badge");
  riskBadge.textContent = workspace.risk_label;
  riskBadge.className = `risk-badge ${workspace.risk_tier}`;
  document.getElementById("review-badge").textContent = titleCase(workspace.review.status);
}

function renderSummaryCards(workspace) {
  document.getElementById("summary-cards").innerHTML = workspace.summary_cards
    .map(
      (item) => `
        <article class="summary-card ${item.tone}">
          <span>${item.label}</span>
          <strong>${item.label === "Due" ? formatTimestamp(item.value) : item.value}</strong>
        </article>
      `,
    )
    .join("");
}

function renderIntake(workspace) {
  const fields = {
    ...workspace.fields,
    machine: workspace.machine,
    owner: workspace.owner,
    queue: workspace.queue,
    received: formatTimestamp(workspace.received_at),
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
}

function renderChat(workspace) {
  const topMatch = workspace.matched_incidents[0];
  document.getElementById("chat-log").innerHTML = `
    <div class="chat-bubble">
      <strong>Monitor summary</strong>
      <p>${workspace.risk_label} case owned by ${workspace.owner}. Top matched theme: ${
        topMatch ? `${topMatch.category} / ${topMatch.process_step}` : "None"
      }.</p>
    </div>
  `;
}

function renderTimeline(workspace) {
  document.getElementById("timeline-list").innerHTML = workspace.timeline
    .map(
      (item) => `
        <article class="timeline-item">
          <time>${formatTimestamp(item.created_at)}</time>
          <strong>${item.title}</strong>
          <p>${item.detail}</p>
        </article>
      `,
    )
    .join("");
}

function renderMatches(workspace) {
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
        <p class="section-label">Matched signals</p>
        <p>${top.matched_signals.join(", ")}</p>
        <p class="section-label">Leading indicators</p>
        <p>${top.detection_indicators.join(" · ")}</p>
        <p class="link-line"><a href="${top.source.url}" target="_blank" rel="noreferrer">${top.source.label}</a></p>
      `
    : "<p>No strong historical failure overlap was found.</p>";
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
            <a href="${item.source.url}" target="_blank" rel="noreferrer">${item.source.label}</a>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderActions(workspace) {
  document.getElementById("recommended-checks").innerHTML = workspace.playbook
    .map((item) => `<div class="check-item">${item}</div>`)
    .join("");
  document.getElementById("review-questions").innerHTML = workspace.review_questions
    .map((item) => `<div class="question-item">${item}</div>`)
    .join("");
  document.getElementById("email-card").innerHTML = `
    <p class="section-label">To</p>
    <p>${workspace.mock_email.to}</p>
    <p class="section-label">Subject</p>
    <p>${workspace.mock_email.subject}</p>
    <p class="section-label">Delivery</p>
    <p>${workspace.mock_email.sent ? "Prepared and marked sent" : "Prepared only"}</p>
    <p class="section-label">Body</p>
    <p>${workspace.mock_email.body}</p>
  `;
}

function renderReview(workspace) {
  document.getElementById("review-comment").value = workspace.review.comment || "";
  document.getElementById("review-history").innerHTML = `
    <article class="audit-item info">
      <strong>${titleCase(workspace.review.status)}</strong>
      <p>${workspace.review.comment}</p>
      <div class="meta-row">
        <span>Last updated</span>
        <span>${formatTimestamp(workspace.review.updated_at)}</span>
      </div>
    </article>
  `;
  document.getElementById("audit-list").innerHTML = workspace.audit
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

function renderWorkspace(workspace) {
  state.workspace = workspace;
  state.cases = state.cases.map((item) =>
    item.id === workspace.id
      ? {
          ...item,
          risk_tier: workspace.risk_tier,
          risk_label: workspace.risk_label,
          status: workspace.status,
          owner: workspace.owner,
          queue: workspace.queue,
        }
      : item,
  );
  renderQueueSummary();
  renderCaseList();
  renderHero(workspace);
  renderSummaryCards(workspace);
  renderIntake(workspace);
  renderChat(workspace);
  renderTimeline(workspace);
  renderMatches(workspace);
  renderActions(workspace);
  renderReview(workspace);
}

async function loadWorkspace(caseId = null) {
  if (caseId) {
    const workspace = await fetchJson(`/api/safety/cases/${caseId}`);
    state.caseId = caseId;
    renderWorkspace(workspace);
    return;
  }
  const payload = await fetchJson("/api/safety/workspace");
  state.caseId = payload.default_case_id;
  state.cases = payload.cases;
  state.knowledgeBase = payload.knowledge_base;
  state.queueSummary = payload.queue_summary;
  renderQueueSummary();
  renderCaseList();
  renderKnowledgeBase(payload.knowledge_base);
  renderWorkspace(payload.workspace);
}

async function askQuestion(event) {
  event.preventDefault();
  if (!state.caseId) {
    return;
  }
  const input = document.getElementById("question-input");
  const question = input.value.trim();
  if (!question) {
    return;
  }
  input.value = "";
  const payload = await fetchJson("/api/safety/explain", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ case_id: state.caseId, question }),
  });
  document.getElementById("chat-log").innerHTML = `
    <div class="chat-bubble">
      <strong>Monitor explanation</strong>
      <p>${payload.answer}</p>
    </div>
  `;
  renderWorkspace(payload.workspace);
  setActiveView("overview");
}

async function rerunMatcher() {
  if (!state.caseId) {
    return;
  }
  const workspace = await fetchJson("/api/safety/rerun", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ case_id: state.caseId }),
  });
  renderWorkspace(workspace);
  setActiveView("evidence");
}

async function reviewCase(action) {
  if (!state.caseId) {
    return;
  }
  const comment = document.getElementById("review-comment").value.trim();
  const workspace = await fetchJson("/api/safety/review", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ case_id: state.caseId, action, comment }),
  });
  renderWorkspace(workspace);
}

function bindEvents() {
  document.querySelectorAll("[data-view-tab]").forEach((button) => {
    button.addEventListener("click", () => setActiveView(button.dataset.viewTab));
  });
  document.getElementById("case-list").addEventListener("click", async (event) => {
    const button = event.target.closest("[data-case-id]");
    if (!button) {
      return;
    }
    state.caseId = button.dataset.caseId;
    await loadWorkspace(state.caseId);
    setActiveView("overview");
  });
  document.querySelectorAll(".prompt-chip").forEach((button) => {
    button.addEventListener("click", () => {
      document.getElementById("question-input").value = button.dataset.question;
      document.getElementById("question-input").focus();
    });
  });
  document.getElementById("question-form").addEventListener("submit", askQuestion);
  document.getElementById("rerun-button").addEventListener("click", rerunMatcher);
  document.querySelectorAll("[data-review-action]").forEach((button) => {
    button.addEventListener("click", () => reviewCase(button.dataset.reviewAction));
  });
}

window.addEventListener("DOMContentLoaded", async () => {
  bindEvents();
  await loadWorkspace();
  setActiveView("overview");
});
