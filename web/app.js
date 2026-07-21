const project = document.querySelector("#project");
const form = document.querySelector("#route-form");
const result = document.querySelector("#result");
const observability = document.querySelector("#observability");
const configStudio = document.querySelector("#config-studio");
const scenarioSimulator = document.querySelector("#scenario-simulator");
const integrationContract = document.querySelector("#integration-contract");
const shadowAnalytics = document.querySelector("#shadow-analytics");
const pilotReadiness = document.querySelector("#pilot-readiness");
const tradeoff = document.querySelector("#tradeoff");
const tradeoffValue = document.querySelector("#tradeoff-value");
let currentRouteId = "";
let currentRunContract = null;

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

async function loadIntegrationContract() {
  const [health, version, contract] = await Promise.all([
    getJson("/api/health"),
    getJson("/api/version"),
    getJson("/api/contracts"),
  ]);
  integrationContract.innerHTML = `
    <h2>DevSpace Integration</h2>
    <p>Stable local API contract for DevSpace or another caller.</p>
    <div class="metrics observability-metrics">
      <div><span>Health</span><strong>${health.ok ? "ok" : "bad"}</strong></div>
      <div><span>Contract</span><strong>${escapeHtml(contract.contract_version)}</strong></div>
      <div><span>Local only</span><strong>${health.local_only ? "yes" : "no"}</strong></div>
    </div>
    <dl>
      <dt>App version</dt><dd>${escapeHtml(version.app_version)}</dd>
      <dt>Modes</dt><dd>${escapeHtml(contract.modes.join(", "))}</dd>
      <dt>Endpoints</dt><dd><ul>${listItems(Object.keys(contract.endpoints))}</ul></dd>
    </dl>
    <div class="action-row">
      <button type="button" id="run-v1-advise">Test v1 advise</button>
      <button type="button" id="run-v1-strict">Test v1 strict</button>
    </div>
    <div id="integration-status" class="status"></div>
  `;
  document.querySelector("#run-v1-advise").addEventListener("click", testIntegrationAdvise);
  document.querySelector("#run-v1-strict").addEventListener("click", testIntegrationStrict);
}

async function loadShadowAnalytics() {
  const summary = await getJson("/api/shadow/summary");
  const topProjects = summary.top_mismatch_projects.length
    ? summary.top_mismatch_projects.map((item) => `${item[0]} (${item[1]})`).join(", ")
    : "none";
  shadowAnalytics.innerHTML = `
    <h2>Shadow Analytics</h2>
    <p>Compare actual model usage against router recommendations.</p>
    <div class="warning">Shadow mode is advisory. It does not change DevSpace model selection.</div>
    <div class="metrics">
      <div><span>Shadow runs</span><strong>${escapeHtml(summary.total_shadow_runs)}</strong></div>
      <div><span>Tier agreement</span><strong>${escapeHtml(percent(summary.tier_agreement_rate))}</strong></div>
      <div><span>Overkill</span><strong>${escapeHtml(summary.estimated_overkill_count)}</strong></div>
      <div><span>Too weak</span><strong>${escapeHtml(summary.estimated_too_weak_safety_risk_count)}</strong></div>
      <div><span>Units saved</span><strong>${escapeHtml(summary.estimated_units_saved_lost)}</strong></div>
      <div><span>Would block</span><strong>${escapeHtml(summary.strict_mode_would_block_count)}</strong></div>
    </div>
    <dl>
      <dt>Top mismatch projects</dt><dd>${escapeHtml(topProjects)}</dd>
      <dt>Reports</dt><dd class="export-links">
        <a href="/exports/reports/shadow_mode_report.md" target="_blank">Markdown report</a>
        <a href="/exports/reports/shadow_mode_report.json" target="_blank">JSON report</a>
      </dd>
    </dl>
    <button type="button" id="export-shadow-report">Export report</button>
    <div id="shadow-status" class="status"></div>
  `;
  document.querySelector("#export-shadow-report").addEventListener("click", exportShadowReport);
}

async function loadPilotReadiness() {
  const scorecard = await getJson("/api/pilot/scorecard");
  pilotReadiness.innerHTML = `
    <h2>Pilot Readiness</h2>
    <p>Leadership-friendly demo scorecard and rollout links.</p>
    <div class="metrics">
      <div><span>Status</span><strong>${escapeHtml(scorecard.readiness_status)}</strong></div>
      <div><span>Golden eval</span><strong>${escapeHtml(scorecard.golden_eval_pass_rate)}%</strong></div>
      <div><span>Projects</span><strong>${escapeHtml(scorecard.project_count)}</strong></div>
      <div><span>High risk</span><strong>${escapeHtml(scorecard.high_risk_project_count)}</strong></div>
      <div><span>Modes</span><strong>${escapeHtml(scorecard.integration_modes.length)}</strong></div>
      <div><span>Tests</span><strong>${escapeHtml(scorecard.unit_test_count)}</strong></div>
    </div>
    <dl>
      <dt>Integration modes</dt><dd>${escapeHtml(scorecard.integration_modes.join(", "))}</dd>
      <dt>Links</dt><dd class="export-links">
        <a href="/exports/reports/pilot_readiness_report.md" target="_blank">Pilot readiness report</a>
        <a href="/api/pilot/demo-script" target="_blank">Demo script</a>
        <a href="/api/pilot/rollout-plan" target="_blank">Rollout plan</a>
        <a href="/exports/reports/shadow_mode_report.md" target="_blank">Shadow mode report</a>
        <a href="/exports/gateway/routing_policy.example.yaml" target="_blank">Enterprise exports</a>
      </dd>
    </dl>
    <button type="button" id="export-pilot-report">Export pilot report</button>
    <div id="pilot-status" class="status"></div>
  `;
  document.querySelector("#export-pilot-report").addEventListener("click", exportPilotReport);
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
  const contract = data.run_contract || packet.run_contract || {};
  const normalized = data.normalized_task || {};
  const capabilities = normalized.requested_capabilities || data.requested_capabilities || [];
  const warnings = normalized.ambiguity_warnings || data.task_ambiguity_warnings || [];
  currentRouteId = data.route_id;
  currentRunContract = contract;
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
    <section class="normalized-task">
      <div class="context-head">
        <h3>Normalized Task Brief</h3>
        <span class="${badgeClass(normalized.intrinsic_risk || data.intrinsic_task_risk || "low")}">${escapeHtml(normalized.intrinsic_risk || data.intrinsic_task_risk || "low")}</span>
      </div>
      <dl>
        <dt>User asked for</dt><dd>${escapeHtml(normalized.normalized_summary || "")}</dd>
        <dt>Task type</dt><dd>${escapeHtml(normalized.task_type || "general")}</dd>
        <dt>Operation</dt><dd>${escapeHtml(normalized.operation_type || data.operation_type || "unknown")}</dd>
        <dt>Detected capabilities</dt><dd><ul>${listItems(capabilities)}</ul></dd>
        <dt>Why</dt><dd>${escapeHtml(normalized.risk_reason || "")}</dd>
        <dt>Minimum tier</dt><dd>${escapeHtml(normalized.minimum_recommended_tier || data.minimum_recommended_tier || "cheap")}</dd>
        <dt>Ambiguity warnings</dt><dd><ul>${listItems(warnings)}</ul></dd>
        <dt>False-positive controls</dt><dd><ul>${listItems(normalized.false_positive_controls_triggered || data.false_positive_controls_triggered || [])}</ul></dd>
      </dl>
    </section>
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
    <section class="run-contract">
      <h3>Run Contract</h3>
      <div class="context-grid">
        <div>
          <h4>Allowed files</h4>
          <ul>${listItems(contract.allowed_file_patterns || [])}</ul>
        </div>
        <div>
          <h4>Forbidden files</h4>
          <ul>${listItems(contract.forbidden_file_patterns || [])}</ul>
        </div>
      </div>
      <div class="context-grid">
        <div>
          <h4>Allowed actions</h4>
          <ul>${listItems(contract.allowed_actions || [])}</ul>
        </div>
        <div>
          <h4>Forbidden actions</h4>
          <ul>${listItems(contract.forbidden_actions || [])}</ul>
        </div>
      </div>
      <div class="forbidden">
        <strong>Validation and stop conditions</strong>
        <ul>${listItems([...(contract.required_validation || []), ...(contract.stop_conditions || [])])}</ul>
      </div>
      ${contract.human_review_required ? '<div class="warning">Run contract requires human review.</div>' : ""}
      <p>${escapeHtml(contract.contract_reasoning || "")}</p>
      <div class="scope-guard">
        <h4>Scope Guard Check</h4>
        <label>
          Changed files
          <textarea id="scope-files" rows="4" placeholder="One changed file per line"></textarea>
        </label>
        <label>
          Diff summary
          <textarea id="scope-diff" rows="3" placeholder="Optional sanitized summary"></textarea>
        </label>
        <button type="button" id="check-scope">Check scope</button>
        <div id="scope-result" class="status"></div>
      </div>
    </section>
    <section class="diff-review">
      <h3>Diff Review / Quality Gate</h3>
      <label>
        Changed files
        <textarea id="diff-files" rows="3" placeholder="One changed file per line"></textarea>
      </label>
      <label>
        Git diff or patch
        <textarea id="diff-text" rows="8" placeholder="Paste sanitized diff here"></textarea>
      </label>
      <label>
        Optional contract JSON
        <textarea id="diff-contract" rows="5" placeholder="Defaults to the current run contract"></textarea>
      </label>
      <button type="button" id="review-diff">Review diff</button>
      <div id="diff-review-result" class="status"></div>
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
  document.querySelector("#check-scope").addEventListener("click", checkScopeGuard);
  document.querySelector("#review-diff").addEventListener("click", reviewDiffGate);
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

function percent(value) {
  return `${((Number(value) || 0) * 100).toFixed(1)}%`;
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

async function checkScopeGuard() {
  const status = document.querySelector("#scope-result");
  const payload = {
    contract: currentRunContract,
    changed_files: filesFromInput(document.querySelector("#scope-files").value),
    diff_summary: document.querySelector("#scope-diff").value,
  };
  try {
    const data = await postJson("/api/v1/contract/check", payload);
    const guard = data.scope_guard;
    status.textContent = `${guard.decision.toUpperCase()}: ${guard.explanation} ${guard.violations.join(" ")}`;
    status.className = guard.decision === "pass" ? "status ok" : "status bad";
  } catch (error) {
    status.textContent = error.message;
    status.className = "status bad";
  }
}

async function reviewDiffGate() {
  const status = document.querySelector("#diff-review-result");
  let contract = currentRunContract;
  const contractText = document.querySelector("#diff-contract").value.trim();
  if (contractText) {
    try {
      contract = JSON.parse(contractText);
    } catch (error) {
      status.textContent = "Contract JSON is invalid.";
      status.className = "status bad";
      return;
    }
  }
  const payload = {
    project_name: project.value,
    task_description: document.querySelector("#task").value,
    run_contract: contract,
    changed_files: filesFromInput(document.querySelector("#diff-files").value),
    git_diff: document.querySelector("#diff-text").value,
    live_prod: document.querySelector("#live-prod").checked || null,
  };
  try {
    const data = await postJson("/api/v1/diff-review", payload);
    const review = data.diff_review;
    status.innerHTML = `
      <strong>${escapeHtml(review.decision.toUpperCase())}</strong> ${escapeHtml(review.summary)}
      <br>Detected: ${escapeHtml(review.detected_change_types.join(", ") || "none")}
      <br>Violations: ${escapeHtml(review.violations.join(" ") || "none")}
      <br>Follow-up: ${escapeHtml(review.required_followup_checks.join(" ") || "none")}
    `;
    status.className = review.decision === "pass" ? "status ok" : "status bad";
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

async function testIntegrationAdvise() {
  const payload = {
    project_name: "Diana Test Project",
    task_description: "Make hello world page prettier",
    files_touched: ["index.html"],
  };
  const data = await postJson("/api/v1/route", payload);
  setIntegrationStatus(`v1 advise: ${data.recommended_model} / ${data.model_tier}`, true);
}

async function testIntegrationStrict() {
  const payload = {
    project_name: "Veteran's Intake Application",
    task_description: "Fix auth ping redirect bug",
    files_touched: ["Auth/ping.php"],
  };
  const data = await postJson("/api/v1/strict-check", payload);
  setIntegrationStatus(`v1 strict block=${data.block} (${data.block_reason || "not blocked"})`, data.block);
}

async function exportShadowReport() {
  const data = await getJson("/api/shadow/report");
  const status = document.querySelector("#shadow-status");
  status.textContent = `Report exported: ${data.files.markdown}`;
  status.className = "status ok";
}

async function exportPilotReport() {
  const data = await getJson("/api/pilot/report");
  const status = document.querySelector("#pilot-status");
  status.textContent = `Report exported: ${data.files.markdown}`;
  status.className = "status ok";
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

async function postJson(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed.");
  return data;
}

function setConfigStatus(message, ok) {
  const status = document.querySelector("#config-status");
  status.textContent = message;
  status.className = ok ? "status ok" : "status bad";
}

function setIntegrationStatus(message, ok) {
  const status = document.querySelector("#integration-status");
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
loadIntegrationContract().catch(() => {});
loadShadowAnalytics().catch(() => {});
loadPilotReadiness().catch(() => {});
