from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from .models import DATA_DIR
from .contracts import contract_from_route
from .observability import sanitize_text
from .projects import find_project
from .router import route


@lru_cache(maxsize=1)
def load_validation_playbooks() -> dict[str, list[str]]:
    with (DATA_DIR / "validation_playbooks.json").open(encoding="utf-8") as f:
        return json.load(f)


def generate_packet(
    project_name: str,
    task_description: str,
    files_touched: list[str] | None = None,
    previous_failure_count: int = 0,
    live_prod: bool | None = None,
    session_id: str | None = None,
    profile_name: str = "balanced",
    cost_quality_tradeoff: int | None = None,
    allowed_models: list[str] | None = None,
) -> dict[str, Any]:
    result = route(
        project_name=project_name,
        task_description=task_description,
        files_touched=files_touched or [],
        previous_failure_count=previous_failure_count,
        live_prod=live_prod,
        session_id=session_id,
        profile_name=profile_name,
        cost_quality_tradeoff=cost_quality_tradeoff,
        allowed_models=allowed_models,
    )
    return packet_from_route(project_name, task_description, files_touched or [], result)


def packet_from_route(
    project_name: str,
    task_description: str,
    files_touched: list[str],
    route_result: dict[str, Any],
) -> dict[str, Any]:
    project = find_project(project_name)
    playbook_name = _playbook(project_name, task_description, files_touched, route_result)
    validation = load_validation_playbooks()[playbook_name]
    context_pack = route_result["context_pack"]
    run_contract = contract_from_route(project_name, task_description, files_touched, route_result)
    safety = _safety_checklist(route_result, context_pack, project)
    stop_conditions = _stop_conditions(route_result, context_pack, playbook_name)
    escalation = _escalation_plan(route_result, playbook_name)
    packet = {
        "route_id": route_result["route_id"],
        "recommended_model": route_result["recommended_model"],
        "effort_level": route_result["effort_level"],
        "risk_level": route_result["risk_level"],
        "human_review_required": route_result["human_review_required"],
        "normalized_task": route_result.get("normalized_task", {}),
        "operation_type": route_result.get("operation_type"),
        "false_positive_controls_triggered": route_result.get("false_positive_controls_triggered", []),
        "context_pack": context_pack,
        "run_contract": run_contract,
        "execution_prompt": "",
        "context_checklist": _context_checklist(context_pack),
        "safety_checklist": safety,
        "validation_checklist": validation,
        "stop_conditions": stop_conditions,
        "escalation_plan": escalation,
        "validation_playbook": playbook_name,
    }
    packet["execution_prompt"] = _execution_prompt(
        project_name,
        task_description,
        files_touched,
        route_result,
        project,
        packet,
    )
    return packet


def format_packet(packet: dict[str, Any]) -> str:
    sections = [
        f"Route ID: {packet['route_id']}",
        f"Recommended model: {packet['recommended_model']}",
        f"Effort: {packet['effort_level']}",
        f"Risk: {packet['risk_level']}",
        f"Human review required: {'yes' if packet['human_review_required'] else 'no'}",
        "\nExecution prompt:\n" + packet["execution_prompt"],
        "\nContext checklist:\n" + _bullets(packet["context_checklist"]),
        "\nSafety checklist:\n" + _bullets(packet["safety_checklist"]),
        "\nValidation checklist:\n" + _bullets(packet["validation_checklist"]),
        "\nStop conditions:\n" + _bullets(packet["stop_conditions"]),
        "\nEscalation plan:\n" + _bullets(packet["escalation_plan"]),
    ]
    return "\n".join(sections)


def _playbook(project_name: str, task: str, files: list[str], result: dict[str, Any]) -> str:
    text = " ".join([project_name, task, *files, *result["matched_rules"]]).casefold()
    if project_name in {"Local Budget Book", "Transparency Portal"} or "official public" in text:
        return "public_official_budget_content"
    if any(term in text for term in ["graph", "intune", "advanced hunting", "usb", "cybersecurity"]):
        return "microsoft_graph_cybersecurity"
    if any(term in text for term in ["network", "switch", "iap", "infrastructure", "active directory", "syslog"]):
        return "infrastructure_network_security"
    if ("forge" in text or "bot" in text) and "live_prod_project" in result["matched_rules"]:
        return "live_prod_forge_bot"
    if "teamdynamix" in text or "tdx" in text:
        return "teamdynamix_integration"
    if "laserfiche" in text:
        return "laserfiche_integration"
    if "forge" in text or "bot" in text:
        return "forge_bot"
    if any(term in text for term in ["veteran", "workers comp", "claim", "payroll", "hr", "intake"]):
        return "sensitive_intake_or_claims"
    if result["model_tier"] == "cheap":
        return "static_ui_docs"
    return "normal_web_app"


def _context_checklist(context_pack: dict[str, Any]) -> list[str]:
    return [
        "Inspect: " + ", ".join(context_pack["include_patterns"]),
        "Use file types: " + ", ".join(context_pack["include_file_types"]),
        "Exclude: " + ", ".join(context_pack["exclude_patterns"]),
        "Forbidden: " + ", ".join(context_pack["forbidden_context"]),
        context_pack["redaction_warning"],
    ]


def _safety_checklist(result: dict[str, Any], context_pack: dict[str, Any], project: dict[str, Any]) -> list[str]:
    items = [
        "Use sanitized context only; never include secrets, PII, records, tokens, passwords, emails, tenant IDs, USB serials, or production log content.",
        "Keep the change scoped to the requested task and touched files.",
    ]
    if result["human_review_required"] or project.get("sensitive"):
        items.append("Require human review before sensitive-data or security-control changes.")
    if result.get("intrinsic_task_risk") == "high":
        items.append("Intrinsic task risk is high; keep context sanitized and avoid broad changes.")
    if "live_prod_project" in result["matched_rules"]:
        items.append("Live-prod project: do not make broad refactors; require human review before deployment.")
    if "naming" in " ".join(context_pack["redaction_warning"].split()).casefold():
        items.append("Check downstream filename dependencies before changing naming conventions.")
    return items


def _stop_conditions(result: dict[str, Any], context_pack: dict[str, Any], playbook: str) -> list[str]:
    items = [
        "Stop if required context is missing or ambiguous.",
        "Stop if validation cannot be run or interpreted.",
        "Stop if the task requires secrets, real records, production logs, or unsanitized sensitive data.",
    ]
    if result["human_review_required"]:
        items.append("Stop before deployment or risky writes until human review is complete.")
    if playbook == "public_official_budget_content":
        items.append("Stop if source figures cannot be verified.")
    if playbook == "live_prod_forge_bot":
        items.append("Stop if rollback impact is unclear.")
    return items


def _escalation_plan(result: dict[str, Any], playbook: str) -> list[str]:
    items = ["Escalate to a human reviewer if scope expands beyond the listed task."]
    if result["model_tier"] != "advanced":
        items.append("Escalate to an advanced model after two failed attempts or if security/data risk appears.")
    if result["human_review_required"] or playbook in {"live_prod_forge_bot", "infrastructure_network_security"}:
        items.append("Human approval is required before production, sensitive-data, security, infrastructure, or deployment changes.")
    return items


def _execution_prompt(
    project_name: str,
    task_description: str,
    files_touched: list[str],
    result: dict[str, Any],
    project: dict[str, Any],
    packet: dict[str, Any],
) -> str:
    context = result["context_pack"]
    files = ", ".join(files_touched) if files_touched else "No exact files were listed; use the context patterns below"
    safe_task = result.get("normalized_task", {}).get("normalized_summary") or sanitize_text(task_description, 180)
    return "\n".join(
        [
            f"Project: {project_name}",
            f"Task: {safe_task}",
            f"Normalized task brief: {safe_task}",
            f"Detected capabilities: {', '.join(result.get('requested_capabilities', [])) or 'none'}. Operation: {result.get('operation_type', 'unknown')}. Minimum tier: {result.get('minimum_recommended_tier', result['model_tier'])}.",
            f"Normalizer reason: {result.get('normalized_task', {}).get('risk_reason', 'No extra normalizer reason.')}",
            f"Use model/effort: {result['recommended_model']} / {result['effort_level']}.",
            f"Risk notes: project risk={project.get('risk_level', result['risk_level'])}; route risk={result['risk_level']}; human review required={result['human_review_required']}.",
            f"Inspect these files/context: {files}. Also use: {', '.join(context['include_patterns'])}.",
            f"Do not inspect or include: {', '.join(context['exclude_patterns'])}. Forbidden context: {', '.join(context['forbidden_context'])}.",
            f"Run contract allowed files: {', '.join(packet['run_contract']['allowed_file_patterns'])}.",
            f"Run contract forbidden files/actions: {', '.join(packet['run_contract']['forbidden_file_patterns'])}; {', '.join(packet['run_contract']['forbidden_actions'])}.",
            "Use sanitized context only. Do not include secrets, PII, real records, tokens, passwords, emails, tenant IDs, USB serials, or production log content.",
            ("Live-prod constraint: do not make broad refactors; require human review before deployment." if "live_prod_project" in result["matched_rules"] else "Keep the change narrow and avoid unrelated refactors."),
            "Validate with: " + "; ".join(packet["validation_checklist"]),
            "Report back with changed files, validation run, residual risks, and any human-review needs.",
            "Stop and ask for human review if context is missing, validation is blocked, secrets/records are needed, source figures cannot be verified, or production impact is unclear.",
        ]
    )


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)
