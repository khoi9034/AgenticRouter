from __future__ import annotations

from typing import Any

from .context import build_context_pack
from .normalizer import normalize_task
from .observability import write_trace
from .outcomes import make_route_id
from .profiles import safety_locked, select_model
from .projects import find_project
from .rules import escalate_tier, hits, load_routing_rules, max_risk, max_tier, touches_code
from .sessions import can_reuse_session, latest_session, save_session_route

EFFORT_BY_TIER = {"cheap": "low", "mid": "medium", "advanced": "high"}


def route(
    project_name: str,
    task_description: str,
    files_touched: list[str] | None = None,
    previous_failure_count: int = 0,
    live_prod: bool | None = None,
    sensitive: bool | None = None,
    output_format: str = "text",
    session_id: str | None = None,
    profile_name: str = "balanced",
    cost_quality_tradeoff: int | None = None,
    allowed_models: list[str] | None = None,
) -> dict[str, Any]:
    if output_format not in {"text", "json"}:
        raise ValueError("output_format must be text or json")
    if previous_failure_count < 0:
        raise ValueError("previous_failure_count cannot be negative")

    files = files_touched or []
    project = find_project(project_name)
    rules = load_routing_rules()
    is_live_prod = project.get("live_prod", False) if live_prod is None else live_prod
    project_sensitive = project.get("sensitive", False) if sensitive is None else sensitive
    text = " ".join([project_name, task_description, *files, *project.get("keywords", [])])
    normalized = normalize_task(task_description, files, previous_failure_count=previous_failure_count)

    tier = project.get("default_tier", "cheap")
    risk = project.get("risk_level", "low")
    matched_rules = [f"project_default:{tier}", f"project_risk:{risk}"]
    if normalized["matched_task_signals"]:
        matched_rules.append("task_signals:" + ", ".join(normalized["matched_task_signals"][:4]))
    if normalized["false_positive_controls_triggered"]:
        matched_rules.append("task_false_positive_controls:" + ", ".join(normalized["false_positive_controls_triggered"][:4]))
    matched_rules.append(f"task_operation:{normalized['operation_type']}")
    tier = max_tier(tier, normalized["minimum_recommended_tier"])
    risk = max_risk(risk, normalized["intrinsic_risk"])
    if normalized["minimum_recommended_tier"] != "cheap":
        matched_rules.append(f"task_minimum_tier:{normalized['minimum_recommended_tier']}")
    if normalized["intrinsic_risk"] != "low":
        matched_rules.append(f"intrinsic_task_risk:{normalized['intrinsic_risk']}")

    cheap_hits = hits(text, rules["cheap_keywords"])
    mid_hits = hits(text, rules["mid_keywords"])
    advanced_hits = hits(text, rules["advanced_keywords"])
    if normalized["intrinsic_risk"] != "high" and normalized["false_positive_controls_triggered"]:
        advanced_hits = []
        if normalized["intrinsic_risk"] == "low":
            mid_hits = []
    sensitive_hits = hits(text, rules["sensitive_keywords"])
    security_hits = hits(text, rules["security_keywords"])

    if cheap_hits and tier == "cheap":
        matched_rules.append("cheap_content:" + ", ".join(cheap_hits[:4]))
    if mid_hits:
        tier = max_tier(tier, "mid")
        risk = max_risk(risk, "medium")
        matched_rules.append("mid_complexity:" + ", ".join(mid_hits[:4]))
    if advanced_hits:
        tier = "advanced"
        risk = max_risk(risk, "high")
        matched_rules.append("advanced_risk:" + ", ".join(advanced_hits[:4]))
    if is_live_prod:
        matched_rules.append("live_prod_project")
    if is_live_prod and touches_code(files) and tier == "cheap":
        tier = "mid"
        risk = max_risk(risk, "medium")
        matched_rules.append("live_prod_code_never_cheap")
    if previous_failure_count >= 2:
        tier = escalate_tier(tier)
        risk = max_risk(risk, "medium")
        matched_rules.append("previous_failures_escalate")

    needs_human = bool(project_sensitive or sensitive_hits or security_hits or normalized["human_review_recommended"])
    if project_sensitive:
        matched_rules.append("sensitive_project")
    if sensitive_hits:
        matched_rules.append("sensitive_data:" + ", ".join(sensitive_hits[:4]))
    if security_hits:
        matched_rules.append("security_controls:" + ", ".join(security_hits[:4]))
    if normalized["security_sensitive"]:
        matched_rules.append("task_security_sensitive")
    if normalized["data_sensitive"]:
        matched_rules.append("task_data_sensitive")
    if normalized["production_sensitive"]:
        matched_rules.append("task_production_sensitive")

    locked = safety_locked(project_name, task_description, files, tier, risk, matched_rules, is_live_prod)
    previous = latest_session(session_id) if session_id else None
    sticky = can_reuse_session(previous, project_name, risk, locked, previous_failure_count) if session_id else False
    model_choice = select_model(
        project_name=project_name,
        task_description=task_description,
        files_touched=files,
        model_tier=tier,
        risk_level=risk,
        matched_rules=matched_rules,
        live_prod=is_live_prod,
        profile_name=profile_name,
        cost_quality_tradeoff=cost_quality_tradeoff,
        allowed_models=allowed_models,
        sticky_alias=previous.get("selected_model_alias") if sticky and previous else None,
        sticky_model=previous.get("selected_model") if sticky and previous else None,
    )
    needs_human = needs_human or model_choice["human_review_default"]
    result = {
        "recommended_model": model_choice["selected_model"],
        "model_tier": tier,
        "effort_level": EFFORT_BY_TIER[tier],
        "risk_level": risk,
        "human_review_required": needs_human,
        "reason": _reason(tier, matched_rules),
        "context_policy": _context_policy(files, needs_human),
        "escalation_policy": _escalation_policy(tier, previous_failure_count, needs_human),
        "matched_rules": matched_rules,
        "session_id": session_id,
        "sticky_route_used": sticky,
        "previous_model": previous.get("selected_model") if previous else None,
        "selected_model_alias": model_choice["selected_model_alias"],
        "selected_model": model_choice["selected_model"],
        "fallback_candidates": model_choice["fallback_candidates"],
        "profile_name": model_choice["profile_name"],
        "cost_quality_tradeoff": model_choice["cost_quality_tradeoff"],
        "normalized_task": normalized,
        "intrinsic_task_risk": normalized["intrinsic_risk"],
        "requested_capabilities": normalized["requested_capabilities"],
        "minimum_recommended_tier": normalized["minimum_recommended_tier"],
        "task_ambiguity_warnings": normalized["ambiguity_warnings"],
        "task_type": normalized["task_type"],
        "operation_type": normalized["operation_type"],
        "false_positive_controls_triggered": normalized["false_positive_controls_triggered"],
    }
    result["context_pack"] = build_context_pack(project_name, task_description, files, risk, tier, matched_rules)
    result["route_id"] = make_route_id(project_name, task_description, files, result)
    write_trace(project_name, task_description, files, result)
    if session_id:
        save_session_route(session_id, project_name, task_description, files, result, model_choice["safety_locked"])
    return result


def _reason(tier: str, matched_rules: list[str]) -> str:
    return f"Routed {tier} from rule matches: " + "; ".join(matched_rules)


def _context_policy(files: list[str], sensitive: bool) -> str:
    scope = (
        "Include only the listed files plus their direct callers, tests, and config."
        if files
        else "Include the project entry, task text, and the smallest directly relevant files."
    )
    exclude = " Exclude secrets, tokens, credentials, bearer tokens, PII, PHI, and real case records."
    return scope + " Do not send whole-repo context." + (exclude if sensitive else "")


def _escalation_policy(tier: str, failures: int, human_review: bool) -> str:
    parts = ["Escalate one tier after 2 failed attempts."]
    if tier == "advanced":
        parts.append("Use a senior model and keep a human approval gate before risky writes.")
    if failures >= 2:
        parts.append("Already escalated because repeated attempts failed.")
    if human_review:
        parts.append("Human review is required before production or sensitive-data changes.")
    return " ".join(parts)
