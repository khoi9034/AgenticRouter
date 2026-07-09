const project = document.querySelector("#project");
const form = document.querySelector("#route-form");
const result = document.querySelector("#result");

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
      <dt>Reason</dt><dd>${escapeHtml(data.reason)}</dd>
      <dt>Context policy</dt><dd>${escapeHtml(data.context_policy)}</dd>
      <dt>Escalation policy</dt><dd>${escapeHtml(data.escalation_policy)}</dd>
      <dt>Matched rules</dt><dd><ul>${rules}</ul></dd>
    </dl>
  `;
}

function showError(message) {
  result.className = "panel result";
  result.innerHTML = `<div class="warning">${escapeHtml(message)}</div>`;
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

loadProjects().catch((error) => showError(error.message));

