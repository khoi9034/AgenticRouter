const project = document.querySelector("#project");
const form = document.querySelector("#route-form");
const result = document.querySelector("#result");
const observability = document.querySelector("#observability");
const configStudio = document.querySelector("#config-studio");
const scenarioSimulator = document.querySelector("#scenario-simulator");
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

async function loadObservability() {
  const response = await fetch("/api/observability");
  const data = await response.json();
  const summary = data.summary;
  const files = data.export_files.length
    ? data.export_files.map((file) => `<a href="/${escapeHtml(file.relative_path)}" target="_blank">${escapeHtml(file.name)}</a>`).join("")
    : '<span class="muted">Run export-langsmith-files to create export files.</span>';
  observability.innerHTML = `
    <h2>Local Observability</h2>
    <p>All observability is local. No LangSmith API key or remote tracing is used.</p>
    <div class="metrics observability-metrics">
      <div><span>Traces</span><strong>${escapeHtml(summary.total_traces)}</strong></div>
      <div><span>Human review</span><strong>${escapeHtml(summary.human_review_count)}</strong></div>
      <div><span>Sticky routes</span><strong>${escapeHtml(summary.sticky_route_count)}</strong></div>
    </div>
    <dl>
      <dt>Last route ID</dt><dd class="route-id">${escapeHtml(summary.last_route_id || "none")}</dd>
      <dt>Traces by risk</dt><dd>${escapeHtml(JSON.stringify(summary.traces_by_risk))}</dd>
      <dt>Export files</dt><dd class="export-links">${files}</dd>
    </dl>
  `;
}

async function loadConfigStudio() {
  const response = await fetch("/api/config/summary");
  const summary = await response.json();
  configStudio.innerHTML = `
    <h2>Config Studio</h2>
    <p>Local policy validation, read-only summary, safe bundle export, and one guarded add-project form.</p>
    <div class="metrics observability-metrics">
      <div><span>Projects</span><strong>${escapeHtml(summary.total_projects)}</strong></div>
      <div><span>Golden tasks</span><strong>${escapeHtml(summary.golden_task_count)}</strong></div>
      <div><span>Status</span><strong>${escapeHtml(summary.validation_status)}</strong></div>
    </div>
    <dl>
      <dt>Projects by risk</dt><dd>${escapeHtml(JSON.stringify(summary.projects_by_risk))}</dd>
      <dt>Model aliases</dt><dd>${escapeHtml(summary.aliases.join(", "))}</dd>
      <dt>Routing profiles</dt><dd>${escapeHtml(summary.profiles.join(", "))}</dd>
    </dl>
    <div class="action-row">
      <button type="button" id="validate-config">Validate config</button>
      <button type="button" id="export-config">Download config bundle</button>
      <button type="button" id="refresh-config">View config summary</button>
      <button type="button" id="config-eval">Run golden eval</button>
    </div>
    <div id="config-status" class="status"></div>
    <form id="add-project-form" class="inline-form">
      <h3>Add Project</h3>
      <label>Project name<input id="new-project-name" required></label>
      <div class="split">
        <label>Department<input id="new-project-department"></label>
        <label>Status<input id="new-project-status" placeholder="planning"></label>
      </div>
      <div class="split">
        <label>Risk level<select id="new-project-risk"><option>low</option><option>medium</option><option>high</option></select></label>
        <label class="check"><input id="new-project-live" type="checkbox"> Live/prod</label>
      </div>
      <label>Sensitive domains<textarea id="new-project-domains" rows="2" placeholder="comma-separated"></textarea></label>
      <label>Routing notes<textarea id="new-project-notes" rows="2"></textarea></label>
      <button type="submit">Save project locally</button>
    </form>
  `;
  document.querySelector("#validate-config").addEventListener("click", validateConfig);
  document.querySelector("#export-config").addEventListener("click", exportConfig);
  document.querySelector("#refresh-config").addEventListener("click", loadConfigStudio);
  document.querySelector("#config-eval").addEventListener("click", runConfigEval);
  document.querySelector("#add-project-form").addEventListener("submit", addProject);
}

async function loadScenarioSimulator() {
  const data = await getJson("/api/scenarios");
  scenarioSimulator.innerHTML = `
    <h2>Scenario Simulator</h2>
    <p>Run hypothetical DevSpace task batches through the local router.</p>
    <div class="split">
      <label>Scenario<select id="scenario-select">${data.scenarios.map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("")}</select></label>
      <button type="button" id="run-simulation">Run simulation</button>
    </div>
    <div id="simulation-result" class="simulation-result"></div>
  `;
  document.querySelector("#run-simulation").addEventListener("click", runSimulation);
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

function tierBadgeClass(tier) {
  if (tier === "cheap") return "badge low";
  if (tier === "mid") return "badge medium";
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
    if (response.ok) {
      showResult(data);
      loadObservability();
    } else {
      showError(data.error || "Routing failed.");
    }
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

async function validateConfig() {
  const data = await getJson("/api/config/validate");
  setConfigStatus(data.ok ? "Config validation passed." : `Config validation failed: ${data.errors.join("; ")}`, data.ok);
}

async function exportConfig() {
  const data = await getJson("/api/config/export");
  setConfigStatus(`Config bundle ready: ${data.output}`, true);
}

async function runConfigEval() {
  const data = await getJson("/api/config/eval");
  setConfigStatus(`Golden eval: ${data.passed}/${data.total} passed`, data.failed === 0);
}

async function addProject(event) {
  event.preventDefault();
  const payload = {
    project_name: document.querySelector("#new-project-name").value,
    department: document.querySelector("#new-project-department").value,
    status: document.querySelector("#new-project-status").value,
    risk_level: document.querySelector("#new-project-risk").value,
    live_prod: document.querySelector("#new-project-live").checked,
    sensitive_domains: document.querySelector("#new-project-domains").value,
    routing_notes: document.querySelector("#new-project-notes").value,
  };
  const response = await fetch("/api/config/add-project", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  setConfigStatus(response.ok ? `Saved ${data.project.name}.` : data.error || "Save failed.", response.ok);
  if (response.ok) {
    event.target.reset();
    await loadProjects();
    await loadConfigStudio();
    setConfigStatus(`Saved ${data.project.name}.`, true);
  }
}

async function runSimulation() {
  const response = await fetch("/api/simulate", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({scenario: document.querySelector("#scenario-select").value}),
  });
  const data = await response.json();
  if (!response.ok) {
    document.querySelector("#simulation-result").innerHTML = `<div class="warning">${escapeHtml(data.error || "Simulation failed.")}</div>`;
    return;
  }
  showSimulation(data);
  loadObservability();
}

function showSimulation(data) {
  const summary = data.summary;
  const savings = summary.savings;
  const tierCounts = summary.routes_by_tier;
  const rows = data.tasks.map((task) => `
    <tr>
      <td>${escapeHtml(task.project_name)}</td>
      <td>${escapeHtml(task.task_description)}</td>
      <td><span class="${tierBadgeClass(task.model_tier)}">${escapeHtml(task.model_tier)}</span></td>
      <td><span class="${badgeClass(task.risk_level)}">${escapeHtml(task.risk_level)}</span></td>
      <td><span class="size-badge">${escapeHtml(task.context_size)}</span></td>
      <td>${task.human_review_required ? "yes" : "no"}</td>
    </tr>
  `).join("");
  document.querySelector("#simulation-result").innerHTML = `
    <div class="metrics">
      <div><span>Total tasks</span><strong>${escapeHtml(summary.total_tasks)}</strong></div>
      <div><span>Cheap / Mid / Advanced</span><strong>${escapeHtml(tierCounts.cheap || 0)} / ${escapeHtml(tierCounts.mid || 0)} / ${escapeHtml(tierCounts.advanced || 0)}</strong></div>
      <div><span>Human review</span><strong>${escapeHtml(summary.human_review_required_count)}</strong></div>
      <div><span>Cost units saved</span><strong>${escapeHtml(savings.estimated_units_saved)}</strong></div>
      <div><span>Context units saved</span><strong>${escapeHtml(savings.estimated_context_units_saved)}</strong></div>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Project</th><th>Task</th><th>Tier</th><th>Risk</th><th>Context</th><th>Review</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

async function getJson(path) {
  const response = await fetch(path);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed.");
  return data;
}

function setConfigStatus(message, ok) {
  const status = document.querySelector("#config-status");
  status.textContent = message;
  status.className = ok ? "status ok" : "status bad";
}

tradeoff.addEventListener("input", () => {
  tradeoffValue.textContent = tradeoff.value;
});

loadProjects().catch((error) => showError(error.message));
loadObservability().catch(() => {});
loadConfigStudio().catch(() => {});
loadScenarioSimulator().catch(() => {});
