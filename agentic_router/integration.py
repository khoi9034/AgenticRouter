from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config_validation import contains_sensitive_value
from .models import DATA_DIR
from .observability import sanitize_text
from .packets import packet_from_route
from .router import route
from .shadow import write_shadow_run

CONTRACT_VERSION = "v1"
APP_VERSION = "0.1.0"
EXPORT_DIR = DATA_DIR.parent / "exports" / "devspace"
REQUIRED_RESPONSE_FIELDS = {
    "contract_version",
    "route_id",
    "recommended_model",
    "selected_model_alias",
    "model_tier",
    "effort_level",
    "risk_level",
    "human_review_required",
    "reason",
    "matched_rules",
    "fallback_candidates",
    "normalized_task",
    "intrinsic_task_risk",
    "requested_capabilities",
    "minimum_recommended_tier",
    "task_ambiguity_warnings",
    "task_type",
    "operation_type",
    "false_positive_controls_triggered",
    "context_pack",
    "devspace_run_packet",
    "observability",
    "mode",
    "block",
    "block_reason",
    "warnings",
    "recommended_next_action",
}


def load_contract() -> dict[str, Any]:
    with (DATA_DIR / "api_contracts.json").open(encoding="utf-8") as f:
        return json.load(f)


def health() -> dict[str, Any]:
    return {"ok": True, "service": "AgenticRouter", "local_only": True, "contract_version": CONTRACT_VERSION}


def version() -> dict[str, Any]:
    return {"app_version": APP_VERSION, "contract_version": CONTRACT_VERSION, "api_versions": [CONTRACT_VERSION]}


def handle_request(payload: dict[str, Any], forced_mode: str | None = None) -> dict[str, Any]:
    request = _normalize_request(payload, forced_mode)
    forbidden_context = contains_sensitive_value(payload)
    result = route(
        project_name=request["project_name"],
        task_description=request["task_description"],
        files_touched=request["files_touched"],
        previous_failure_count=request["previous_failure_count"],
        live_prod=request["live_prod"],
        session_id=request.get("session_id"),
        profile_name=request["profile"],
        cost_quality_tradeoff=request.get("cost_quality_tradeoff"),
        allowed_models=request["allowed_models"] or None,
    )
    include_packet = (request["mode"] == "packet" or request["include_packet"]) and not forbidden_context
    packet = (
        packet_from_route(request["project_name"], request["task_description"], request["files_touched"], result)
        if include_packet
        else {}
    )
    router_would_block_in_strict = result["human_review_required"] or forbidden_context
    block = request["mode"] == "strict" and router_would_block_in_strict
    warnings = _warnings(request, forbidden_context)
    shadow = (
        write_shadow_run(
            request["project_name"],
            request["task_description"],
            request["files_touched"],
            result,
            request.get("actual_model_used"),
            router_would_block_in_strict,
        )
        if request["mode"] == "shadow"
        else None
    )
    response = {
        "contract_version": CONTRACT_VERSION,
        "mode": request["mode"],
        "route_id": result["route_id"],
        "recommended_model": result["recommended_model"],
        "selected_model_alias": result["selected_model_alias"],
        "model_tier": result["model_tier"],
        "effort_level": result["effort_level"],
        "risk_level": result["risk_level"],
        "human_review_required": result["human_review_required"],
        "reason": result["reason"],
        "matched_rules": result["matched_rules"],
        "fallback_candidates": result["fallback_candidates"],
        "normalized_task": result["normalized_task"],
        "intrinsic_task_risk": result["intrinsic_task_risk"],
        "requested_capabilities": result["requested_capabilities"],
        "minimum_recommended_tier": result["minimum_recommended_tier"],
        "task_ambiguity_warnings": result["task_ambiguity_warnings"],
        "task_type": result["task_type"],
        "operation_type": result["operation_type"],
        "false_positive_controls_triggered": result["false_positive_controls_triggered"],
        "context_pack": result["context_pack"],
        "devspace_run_packet": packet,
        "observability": {
            "trace_written": True,
            "prompt_body_logged": _prompt_body_logged(result),
            "caller": sanitize_text(request.get("caller", ""), 80) if request.get("caller") else None,
            "task_id": sanitize_text(request.get("task_id", ""), 80) if request.get("task_id") else None,
            "actual_model_used": sanitize_text(request.get("actual_model_used", ""), 80) if request.get("actual_model_used") else None,
        },
        "block": block,
        "block_reason": _block_reason(result, forbidden_context) if block else None,
        "warnings": warnings,
        "recommended_next_action": _next_action(request["mode"], block, result),
    }
    if shadow:
        comparison = shadow["comparison"]
        response.update(
            {
                "shadow_id": shadow["record"]["shadow_id"],
                "comparison_to_actual": comparison,
                "actual_tier": comparison["actual_tier"],
                "recommended_tier": comparison["recommended_tier"],
                "overkill_or_underpowered": comparison["overkill_or_underpowered"],
                "abstract_cost_delta": comparison["abstract_cost_delta"],
                "router_would_block_in_strict": router_would_block_in_strict,
            }
        )
    return response


def export_devspace_contract(output_dir: Path | None = None) -> dict[str, Any]:
    folder = output_dir or EXPORT_DIR
    folder.mkdir(parents=True, exist_ok=True)
    contract_path = folder / "agentic_router_api_contract.json"
    examples_path = folder / "example_requests.json"
    contract_path.write_text(json.dumps(load_contract(), indent=2, sort_keys=True), encoding="utf-8")
    examples_path.write_text(json.dumps(example_requests(), indent=2, sort_keys=True), encoding="utf-8")
    return {"export_folder": str(folder), "files": {"contract": str(contract_path), "examples": str(examples_path)}}


def example_requests() -> dict[str, list[dict[str, Any]]]:
    return {
        "requests": [
            {
                "mode": "advise",
                "project_name": "Diana Test Project",
                "task_description": "Make hello world page prettier",
                "files_touched": ["index.html"],
                "previous_failure_count": 0,
                "profile": "balanced",
            },
            {
                "mode": "packet",
                "project_name": "Gap Bills Forge Conversion",
                "task_description": "Change PDF output naming format",
                "files_touched": ["forge_bot/gap_bills_bot.py"],
                "live_prod": True,
            },
            {
                "mode": "strict",
                "project_name": "Veteran's Intake Application",
                "task_description": "Fix auth ping redirect bug",
                "files_touched": ["Auth/ping.php"],
                "live_prod": True,
            },
            {
                "mode": "shadow",
                "project_name": "Grant Quarter Reporting",
                "task_description": "Create a dashboard report for quarter totals",
                "files_touched": ["reports/quarterly.py"],
                "actual_model_used": "Sonnet 4.6",
            },
        ]
    }


def integration_self_test() -> dict[str, Any]:
    failures = []
    for index, request in enumerate(example_requests()["requests"], 1):
        response = handle_request(request)
        missing = sorted(REQUIRED_RESPONSE_FIELDS - response.keys())
        if missing:
            failures.append({"index": index, "missing": missing})
    return {"ok": not failures, "checked": len(example_requests()["requests"]), "failures": failures}


def format_contract_summary() -> str:
    contract = load_contract()
    return "\n".join(
        [
            f"Contract version: {contract['contract_version']}",
            "Endpoints:",
            *[f"- {endpoint}: {description}" for endpoint, description in contract["endpoints"].items()],
            "Required fields: " + ", ".join(contract["required_fields"]),
            "Optional fields: " + ", ".join(contract["optional_fields"]),
        ]
    )


def _normalize_request(payload: dict[str, Any], forced_mode: str | None) -> dict[str, Any]:
    mode = forced_mode or payload.get("mode", "advise")
    if mode not in {"advise", "packet", "shadow", "strict"}:
        raise ValueError("mode must be advise, packet, shadow, or strict")
    if "project_name" not in payload or "task_description" not in payload:
        raise ValueError("project_name and task_description are required")
    return {
        "mode": mode,
        "project_name": str(payload["project_name"]),
        "task_description": str(payload["task_description"]),
        "files_touched": _files(payload.get("files_touched", [])),
        "previous_failure_count": 0 if payload.get("previous_failure_count") in (None, "") else int(payload.get("previous_failure_count", 0)),
        "live_prod": payload.get("live_prod") if isinstance(payload.get("live_prod"), bool) else None,
        "session_id": _optional_text(payload.get("session_id")),
        "profile": str(payload.get("profile") or payload.get("profile_name") or "balanced"),
        "cost_quality_tradeoff": _optional_int(payload.get("cost_quality_tradeoff")),
        "allowed_models": _files(payload.get("allowed_models", [])),
        "actual_model_used": _optional_text(payload.get("actual_model_used")),
        "caller": _optional_text(payload.get("caller")),
        "task_id": _optional_text(payload.get("task_id")),
        "include_packet": bool(payload.get("include_packet")),
    }


def _files(value: Any) -> list[str]:
    if value in (None, "", []):
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.replace(",", "\n").splitlines() if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    raise ValueError("list field must be a list or string")


def _optional_text(value: Any) -> str | None:
    text = "" if value is None else str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    return None if value in (None, "") else int(value)


def _prompt_body_logged(result: dict[str, Any]) -> bool:
    return result["risk_level"] in {"low", "medium"} and not result["human_review_required"] and result["model_tier"] != "advanced"


def _warnings(request: dict[str, Any], forbidden_context: bool) -> list[str]:
    warnings = []
    if forbidden_context:
        warnings.append("Request appears to contain forbidden context; remove secrets, private paths, or sensitive identifiers.")
        if request["mode"] == "packet" or request["include_packet"]:
            warnings.append("Run packet was suppressed until forbidden context is removed.")
    if request["mode"] == "shadow" and not request.get("actual_model_used"):
        warnings.append("Shadow mode works best when actual_model_used is supplied.")
    return warnings


def _block_reason(result: dict[str, Any], forbidden_context: bool) -> str:
    if forbidden_context:
        return "forbidden_context_detected"
    if result["human_review_required"]:
        return "human_review_required"
    return "not_blocked"


def _next_action(mode: str, block: bool, result: dict[str, Any]) -> str:
    if block:
        return "stop_and_request_human_review"
    if mode == "shadow":
        return "compare_recommendation_with_actual_model"
    if result["human_review_required"]:
        return "route_with_human_review"
    return "use_recommended_model"
