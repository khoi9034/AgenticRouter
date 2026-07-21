from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from .models import DATA_DIR
from .observability import sanitize_text
from .rules import max_tier

COMPLEXITY_ORDER = ["low", "medium", "high"]
INTRINSIC_RISK_ORDER = ["low", "medium", "high"]
RISK_SCORE = {"low": 0, "medium": 2, "high": 4}
TIER_BY_RISK = {"low": "cheap", "medium": "mid", "high": "advanced"}

DOC_TERMS = ["docs", "documentation", "readme", "copy", "wording", "comments", "comment", "explaining", "guide"]
VISUAL_TERMS = ["css", "color", "spacing", "layout", "visual", "prettier", "style", "label", "button", "typo"]
STATIC_MOCK_TERMS = ["static", "mock", "placeholder", "demo", "no backend", "without backend"]
READ_ONLY_TERMS = ["read only", "read-only", "lookup", "view", "display", "status"]
NON_PROD_TERMS = ["non production", "non-production", "non prod", "non-prod", "prototype", "sandbox"]
IMPLEMENT_ACTIONS = ["build", "create", "implement", "wire", "connect", "integrate", "modify", "add", "save", "persist"]
WRITE_ACTIONS = ["post", "put", "delete endpoint", "write", "send", "upload", "download", "ticket", "notify"]
DESTRUCTIVE_ACTIONS = ["delete", "overwrite", "purge", "bulk update", "sync", "migrate", "archive"]
BROAD_TERMS = ["fix it", "make it work", "connect everything", "build full system", "whole system", "full stack"]
BROAD_OBJECT_TERMS = ["users", "data", "records", "system", "backend", "frontend"]
SURFACE_TERMS = ["page", "button", "label", "copy", "text", "screen", "css", "color", "spacing", "layout"]
RISKY_SURFACE_TERMS = ["login", "sign in", "signin", "auth", "admin", "database", "sql", "api", "payment"]
BACKEND_CAPABILITIES = {"backend_api", "database_sql", "destructive_bulk_write"}
AUTH_CAPABILITIES = {"authentication_admin", "security_infrastructure", "secrets_credentials"}
EXTERNAL_CAPABILITIES = {"microsoft_graph_intune", "enterprise_system_write", "email_file_transfer"}
SENSITIVE_CAPABILITIES = {"sensitive_records", "finance_compliance_audit", "public_official_content"}


@lru_cache(maxsize=1)
def load_task_taxonomy() -> dict[str, Any]:
    with (DATA_DIR / "task_taxonomy.json").open(encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_task_risk_signals() -> dict[str, Any]:
    with (DATA_DIR / "task_risk_signals.json").open(encoding="utf-8") as f:
        return json.load(f)


def normalize_task(
    task_description: str,
    files_touched: list[str] | None = None,
    previous_failure_count: int = 0,
) -> dict[str, Any]:
    files = files_touched or []
    signal_config = load_task_risk_signals()
    task_text = _fold(task_description)
    text = _fold(" ".join([task_description, *files]))
    raw_matches = _matched_signals(text, signal_config["signals"])
    controls = _false_positive_controls(task_text, raw_matches)
    matches = _apply_false_positive_controls(raw_matches, controls)
    if _has(text, BROAD_TERMS):
        matches.append(_synthetic_signal("broad_ambiguous_scope", "medium", "implementation", "broad_scope", ["broad task"]))

    capabilities = _unique(item["capability"] for item in matches)
    operation_type = _operation_type(text, capabilities, controls)
    intrinsic_risk = _intrinsic_risk(text, matches, controls, operation_type)
    complexity = _complexity(intrinsic_risk, capabilities, operation_type, previous_failure_count)
    minimum_tier = TIER_BY_RISK[intrinsic_risk]
    for item in matches:
        minimum_tier = max_tier(minimum_tier, item["minimum_tier"])
    if (
        "public_official_content" not in capabilities
        and ("mock_ui_no_backend" in controls or "visual_surface_only" in controls or "docs_mentions_risky_terms" in controls or "placeholder_demo_only" in controls)
    ):
        minimum_tier = TIER_BY_RISK[intrinsic_risk]

    security_sensitive = any(item.get("security_sensitive") for item in matches) and "visual_surface_only" not in controls
    data_sensitive = any(item.get("data_sensitive") for item in matches) and "docs_mentions_risky_terms" not in controls
    production_sensitive = any(item.get("production_sensitive") for item in matches) and "non_production_context" not in controls
    risk_reason = _risk_reason(intrinsic_risk, operation_type, capabilities, controls)

    return {
        "normalized_summary": sanitize_text(task_description, 180),
        "task_type": _task_type(matches, intrinsic_risk),
        "requested_capabilities": capabilities,
        "operation_type": operation_type,
        "complexity": complexity,
        "intrinsic_risk": intrinsic_risk,
        "security_sensitive": security_sensitive,
        "data_sensitive": data_sensitive,
        "production_sensitive": production_sensitive,
        "minimum_recommended_tier": minimum_tier,
        "human_review_recommended": security_sensitive or data_sensitive or operation_type == "destructive",
        "ambiguity_warnings": _ambiguity_warnings(task_description, files, matches, signal_config["ambiguous_terms"]),
        "extracted_constraints": _constraints(task_description),
        "forbidden_context_hints": _forbidden_hints(security_sensitive, data_sensitive, production_sensitive, signal_config),
        "matched_task_signals": [f"{item['risk']}:{item['name']}:{', '.join(item['hits'][:3])}" for item in matches],
        "false_positive_controls_triggered": controls,
        "risk_reason": risk_reason,
    }


def _matched_signals(text: str, signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches = []
    for signal in signals:
        hits = [term for term in signal["terms"] if _term_hit(text, term)]
        if hits:
            item = dict(signal)
            item["hits"] = hits
            matches.append(item)
    return matches


def _false_positive_controls(text: str, matches: list[dict[str, Any]]) -> list[str]:
    controls = []
    risky = any(item["risk"] == "high" for item in matches) or _has(text, RISKY_SURFACE_TERMS)
    if risky and _has(text, DOC_TERMS) and not _implementation_intent(text):
        controls.append("docs_mentions_risky_terms")
    if risky and _has(text, VISUAL_TERMS) and _has(text, SURFACE_TERMS) and not _backend_intent(text):
        controls.append("visual_surface_only")
    if risky and _has(text, STATIC_MOCK_TERMS) and not _implementation_intent(text):
        controls.append("placeholder_demo_only")
    if _has(text, STATIC_MOCK_TERMS) and _has(text, ["no backend", "without backend", "mock", "static"]):
        controls.append("mock_ui_no_backend")
    if _has(text, READ_ONLY_TERMS) and _has(text, ["api", "endpoint", "backend"]):
        controls.append("read_only_api")
    if _has(text, ["existing api contract", "existing backend contract", "existing endpoint"]):
        controls.append("existing_contract_only")
    if _has(text, NON_PROD_TERMS):
        controls.append("non_production_context")
    return controls


def _apply_false_positive_controls(matches: list[dict[str, Any]], controls: list[str]) -> list[dict[str, Any]]:
    filtered = []
    for item in matches:
        if "docs_mentions_risky_terms" in controls and item["risk"] == "high" and item["capability"] != "public_official_content":
            continue
        if "visual_surface_only" in controls and item["capability"] in AUTH_CAPABILITIES | {"database_sql", "backend_api", "finance_compliance_audit"}:
            continue
        if "mock_ui_no_backend" in controls and item["capability"] in AUTH_CAPABILITIES | BACKEND_CAPABILITIES | {"forms_workflow"}:
            continue
        if "placeholder_demo_only" in controls and item["risk"] == "high" and item["capability"] != "public_official_content":
            continue
        if "read_only_api" in controls and item["capability"] == "backend_api":
            continue
        if "existing_contract_only" in controls and item["capability"] == "backend_api":
            continue
        if "non_production_context" in controls and item["capability"] == "production_deployment":
            continue
        filtered.append(item)

    if "read_only_api" in controls and not any(item["capability"] == "readonly_analysis" for item in filtered):
        filtered.append(_synthetic_signal("read_only_api", "medium", "read_only", "readonly_analysis", ["read-only API"]))
    return filtered


def _operation_type(text: str, capabilities: list[str], controls: list[str]) -> str:
    if "docs_mentions_risky_terms" in controls:
        return "documentation"
    if "visual_surface_only" in controls or "mock_ui_no_backend" in controls or "placeholder_demo_only" in controls:
        return "visual_polish"
    if _has(text, DESTRUCTIVE_ACTIONS):
        return "destructive"
    if "production_deployment" in capabilities or _has(text, ["deploy", "rollback", "iis", "environment"]):
        return "deployment"
    if _has(text, WRITE_ACTIONS) or any(capability in EXTERNAL_CAPABILITIES for capability in capabilities):
        return "write_operation"
    if _has(text, IMPLEMENT_ACTIONS):
        return "implementation"
    if "readonly_analysis" in capabilities or "read_only_api" in controls:
        return "read_only"
    if any(capability in {"forms_workflow", "dashboard_reporting", "client_side_logic"} for capability in capabilities):
        return "ui_behavior"
    if "docs_static" in capabilities:
        return "documentation"
    return "unknown"


def _intrinsic_risk(text: str, matches: list[dict[str, Any]], controls: list[str], operation_type: str) -> str:
    score = max([RISK_SCORE[item["risk"]] for item in matches] or [0])
    capabilities = {item["capability"] for item in matches}
    if _has(text, BROAD_TERMS) and _has(text, BROAD_OBJECT_TERMS):
        score = max(score, 4)
    elif _has(text, BROAD_TERMS):
        score = max(score, 2)
    if operation_type in {"destructive", "deployment"}:
        score = max(score, 4)
    if operation_type in {"implementation", "write_operation"} and capabilities & (AUTH_CAPABILITIES | BACKEND_CAPABILITIES | EXTERNAL_CAPABILITIES | SENSITIVE_CAPABILITIES):
        score = max(score, 4)
    if operation_type == "read_only":
        score = min(max(score, 2), 2)
    if "public_official_content" not in capabilities and (
        "docs_mentions_risky_terms" in controls or "visual_surface_only" in controls or "mock_ui_no_backend" in controls or "placeholder_demo_only" in controls
    ):
        score = min(score, 2 if "dashboard_reporting" in capabilities or "forms_workflow" in capabilities else 0)
    return "high" if score >= 4 else "medium" if score >= 2 else "low"


def _complexity(intrinsic_risk: str, capabilities: list[str], operation_type: str, previous_failure_count: int) -> str:
    score = RISK_SCORE[intrinsic_risk]
    score += max(0, len(capabilities) - 1)
    if set(capabilities) & BACKEND_CAPABILITIES:
        score += 1
    if set(capabilities) & (AUTH_CAPABILITIES | EXTERNAL_CAPABILITIES | SENSITIVE_CAPABILITIES):
        score += 1
    if operation_type in {"destructive", "deployment", "write_operation"}:
        score += 1
    if previous_failure_count >= 2:
        score += 1
    return "high" if score >= 5 else "medium" if score >= 2 else "low"


def _task_type(matches: list[dict[str, Any]], intrinsic_risk: str) -> str:
    if not matches:
        return "general"
    same_risk = [item for item in matches if item["risk"] == intrinsic_risk]
    return (same_risk or matches)[0]["task_type"]


def _ambiguity_warnings(task: str, files: list[str], matches: list[dict[str, Any]], ambiguous_terms: list[str]) -> list[str]:
    text = _fold(task)
    warnings = []
    if len(task.split()) < 4:
        warnings.append("Task description is very short; include the exact desired change and acceptance criteria.")
    if _has(text, ambiguous_terms) or _has(text, BROAD_TERMS):
        warnings.append("Task wording is broad or ambiguous; clarify scope before routing or execution.")
    if matches and not files and max((item["risk"] for item in matches), key=INTRINSIC_RISK_ORDER.index) == "high":
        warnings.append("High-risk task has no files listed; include only directly relevant files or patterns.")
    return warnings


def _constraints(task: str) -> list[str]:
    constraints = []
    for sentence in re.split(r"(?<=[.!?])\s+|;", task):
        folded = sentence.casefold()
        if any(marker in folded for marker in ["must", "only", "without", "do not", "don't", "keep", "avoid"]):
            constraints.append(sanitize_text(sentence.strip(), 160))
    return constraints


def _forbidden_hints(security: bool, data: bool, production: bool, signal_config: dict[str, Any]) -> list[str]:
    hints = []
    groups = signal_config["forbidden_context_hints"]
    if security:
        hints.extend(groups["security"])
    if data:
        hints.extend(groups["data"])
    if production:
        hints.extend(groups["production"])
    return _unique(hints)


def _risk_reason(intrinsic_risk: str, operation_type: str, capabilities: list[str], controls: list[str]) -> str:
    if controls and intrinsic_risk in {"low", "medium"}:
        return "Harmless context controls limited risky-word escalation: " + ", ".join(controls)
    if intrinsic_risk == "high":
        return f"High intrinsic risk from {operation_type} with capabilities: {', '.join(capabilities) or 'broad system impact'}."
    if intrinsic_risk == "medium":
        return f"Medium intrinsic risk from {operation_type} with capabilities: {', '.join(capabilities) or 'moderate task scope'}."
    return "Low intrinsic risk: documentation, static UI, copy, or visual-only work."


def _synthetic_signal(name: str, risk: str, operation: str, capability: str, hits: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "risk": risk,
        "complexity": "medium" if risk == "medium" else risk,
        "task_type": operation,
        "minimum_tier": TIER_BY_RISK[risk],
        "capability": capability,
        "security_sensitive": False,
        "data_sensitive": False,
        "production_sensitive": False,
        "hits": hits,
    }


def _implementation_intent(text: str) -> bool:
    return _has(text, IMPLEMENT_ACTIONS + WRITE_ACTIONS + DESTRUCTIVE_ACTIONS) and not _has(text, DOC_TERMS + STATIC_MOCK_TERMS)


def _backend_intent(text: str) -> bool:
    return _has(text, ["session", "redirect", "endpoint", "backend", "save", "persist", "token", "permission"])


def _term_hit(text: str, term: str) -> bool:
    folded = _fold(term)
    if folded in {"production", "prod"} and _has(text, NON_PROD_TERMS):
        return False
    if " " in folded or "." in folded or "-" in folded:
        return folded in text
    return re.search(rf"\b{re.escape(folded)}\b", text) is not None


def _has(text: str, terms: list[str]) -> bool:
    return any(_term_hit(text, term) for term in terms)


def _fold(value: str) -> str:
    return " ".join(str(value).casefold().replace("_", " ").split())


def _unique(items) -> list[str]:
    seen = set()
    return [item for item in items if not (item in seen or seen.add(item))]
