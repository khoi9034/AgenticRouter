const project = document.querySelector("#project");
const form = document.querySelector("#route-form");
const result = document.querySelector("#result");
const tradeoff = document.querySelector("#tradeoff");
const tradeoffValue = document.querySelector("#tradeoff-value");
let currentRouteId = "";

async function loadProjects() {
  const response = await fetch("/api/projects");
  const data = await response.json();
  project.innerHTML = data.projects
    .map((item) => `<option value="${escapeHtml(item.name)}">${escapeHtml(item.name)}</option>`)
    .join("");
}

function filesFromInput(value) {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function badgeClass(risk) {
  if (risk === "low") return "badge low";
  if (risk === "medium" || risk === "medium-high") return "badge medium";
  return "badge high";
}

function showResult(data) {
  const rules = data.matched_rules.map((rule) => `<li>${escapeHtml(rule)}</li>`).join("");
  const pack = data.context_pack;
  const packet = data.run_packet;
  currentRouteId = data.route_id;
  result.className = "panel result";
  result.innerHTML = `
    <div class="result-head">
      <div>
        <span class="label">Recommended model</span>
        <h2>${escapeHtml(data.recommended_model)}</h2>
      </div>
      <span class="${badgeClass(data.risk_level)}">${escapeHtml(data.risk_level)}</span>
    </div>
    <div class="metrics">
      <div><span>Tier</span><strong>${escapeHtml(data.model_tier)}</strong></div>
      <div><span>Effort</span><strong>${escapeHtml(data.effort_level)}</strong></div>
      <div><span>Review</span><strong>${data.human_review_required ? "Required" : "Not required"}</strong></div>
    </div>
    ${data.human_review_required ? '<div class="warning">Human review required before sensitive or production changes.</div>' : ""}
    <dl>
      <dt>Route ID</dt><dd class="route-id">${escapeHtml(data.route_id)}</dd>
      <dt>Selected model alias</dt><dd>${escapeHtml(data.selected_model_alias)}</dd>
      <dt>Selected model</dt><dd>${escapeHtml(data.selected_model)}</dd>
      <dt>Routing profile</dt><dd>${escapeHtml(data.profile_name)} (${escapeHtml(data.cost_quality_tradeoff)})</dd>
      <dt>Sticky route used</dt><dd>${data.sticky_route_used ? "yes" : "no"}</dd>
      <dt>Fallback candidates</dt><dd><ul>${listItems(data.fallback_candidates)}</ul></dd>
      <dt>Reason</dt><dd>${escapeHtml(data.reason)}</dd>
      <dt>Context policy</dt><dd>${escapeHtml(data.context_policy)}</dd>
      <dt>Escalation policy</dt><dd>${escapeHtml(data.escalation_policy)}</dd>
      <dt>Matched rules</dt><dd><ul>${rules}</ul></dd>
    </dl>
    <section class="context-pack">
      <div class="context-head">
        <h3>Recommended Context Pack</h3>
        <span class="size-badge">${escapeHtml(pack.context_size)}</span>
      </div>
      <div class="context-grid">
        <div>
          <h4>Include</h4>
          <ul>${listItems(pack.include_patterns)}</ul>
        </div>
        <div>
          <h4>Exclude</h4>
          <ul>${listItems(pack.exclude_patterns)}</ul>
        </div>
      </div>
      <div class="forbidden">
        <strong>Forbidden context</strong>
        <ul>${listItems(pack.forbidden_context)}</ul>
      </div>
      <p class="context-warning">${escapeHtml(pack.redaction_warning)}</p>
      <p>${escapeHtml(pack.context_reason)}</p>
    </section>
    <section class="run-packet">
      <h3>DevSpace Run Packet</h3>
      <label>
        Execution prompt
        <textarea class="packet-text" rows="14" readonly>${escapeHtml(packet.execution_prompt)}</textarea>
      </label>
      <div class="context-grid">
        <div>
          <h4>Validation checklist</h4>
          <ul>${listItems(packet.validation_checklist)}</ul>
        </div>
        <div>
          <h4>Stop conditions</h4>
          <ul>${listItems(packet.stop_conditions)}</ul>
        </div>
      </div>
      <div class="forbidden">
        <strong>Escalation plan</strong>
        <ul>${listItems(packet.escalation_plan)}</ul>
      </div>
    </section>
    <form id="feedback-form" class="feedback">
      <h3>Feedback</h3>
      <p>Notes should be sanitized. Do not include secrets, PII, records, emails, tokens, or serial numbers.</p>
      <div class="split">
        <label>
          Accepted recommendation?
          <select id="accepted" required>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </label>
        <label>
          Task succeeded?
          <select id="task-succeeded" required>
            <option value="unknown">Unknown</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </label>
      </div>
      <div class="split">
        <label>
          Actual model used
          <input id="actual-model" required placeholder="${escapeHtml(data.recommended_model)}">
        </label>
        <label>
          Recommendation fit
          <select id="recommendation-fit" required>
            <option value="right">Right</option>
            <option value="too_cheap">Too cheap</option>
            <option value="overkill">Overkill</option>
          </select>
        </label>
      </div>
      <label>
        Notes
        <textarea id="feedback-notes" rows="3" placeholder="Sanitized feedback only"></textarea>
      </label>
      <button type="submit">Save feedback</button>
      <div id="feedback-status" class="status"></div>
    </form>
  `;
  document.querySelector("#feedback-form").addEventListener("submit", saveFeedback);
}

function showError(message) {
  result.className = "panel result";
  result.innerHTML = `<div class="warning">${escapeHtml(message)}</div>`;
}

function listItems(items) {
  return items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    project_name: project.value,
    task_description: document.querySelector("#task").value,
    files_touched: filesFromInput(document.querySelector("#files").value),
    previous_failure_count: Number(document.querySelector("#failures").value || 0),
    live_prod: document.querySelector("#live-prod").checked || null,
    session_id: document.querySelector("#session-id").value.trim() || null,
    profile_name: document.querySelector("#profile").value,
    cost_quality_tradeoff: Number(tradeoff.value),
    allowed_models: filesFromInput(document.querySelector("#allowed-models").value),
  };

  try {
    const response = await fetch("/api/route", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    response.ok ? showResult(data) : showError(data.error || "Routing failed.");
  } catch (error) {
    showError(error.message);
  }
});

async function saveFeedback(event) {
  event.preventDefault();
  const status = document.querySelector("#feedback-status");
  const succeeded = document.querySelector("#task-succeeded").value;
  const payload = {
    route_id: currentRouteId,
    accepted: document.querySelector("#accepted").value === "true",
    task_succeeded: succeeded === "unknown" ? null : succeeded === "true",
    actual_model: document.querySelector("#actual-model").value,
    recommendation_fit: document.querySelector("#recommendation-fit").value,
    notes: document.querySelector("#feedback-notes").value,
  };

  try {
    const response = await fetch("/api/feedback", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    status.textContent = response.ok ? "Feedback saved." : data.error || "Feedback failed.";
    status.className = response.ok ? "status ok" : "status bad";
  } catch (error) {
    status.textContent = error.message;
    status.className = "status bad";
  }
}

tradeoff.addEventListener("input", () => {
  tradeoffValue.textContent = tradeoff.value;
});

loadProjects().catch((error) => showError(error.message));
