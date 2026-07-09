from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from .models import DATA_DIR
from .router import route

RouteFn = Callable[..., dict[str, Any]]
TIER_UNITS = {"cheap": 1, "mid": 3, "advanced": 8}
CONTEXT_UNITS = {"tiny": 1, "small": 2, "medium": 5, "large": 10}


@lru_cache(maxsize=1)
def load_scenarios(path: Path | None = None) -> dict[str, Any]:
    with (path or DATA_DIR / "simulation_scenarios.json").open(encoding="utf-8") as f:
        return json.load(f)["scenarios"]


def list_scenarios(path: Path | None = None) -> list[str]:
    return sorted(load_scenarios(path))


def run_scenario(name: str, path: Path | None = None, route_fn: RouteFn = route) -> dict[str, Any]:
    scenarios = load_scenarios(path)
    if name not in scenarios:
        raise ValueError(f"unknown scenario: {name}")
    scenario = scenarios[name]
    routed = []
    for index, task in enumerate(scenario["tasks"], 1):
        result = route_fn(
            project_name=task["project_name"],
            task_description=task["task_description"],
            files_touched=task.get("files_touched", []),
            previous_failure_count=task.get("previous_failure_count", 0),
            live_prod=task.get("live_prod") if "live_prod" in task else None,
            session_id=task.get("session_id"),
        )
        routed.append(_task_result(index, task, result))

    return {
        "scenario": name,
        "description": scenario.get("description", ""),
        "summary": _summary(routed),
        "tasks": routed,
    }


def format_simulation(result: dict[str, Any]) -> str:
    summary = result["summary"]
    savings = summary["savings"]
    return "\n".join(
        [
            f"Scenario: {result['scenario']}",
            f"Total tasks: {summary['total_tasks']}",
            f"Routes by tier: {json.dumps(summary['routes_by_tier'], sort_keys=True)}",
            f"Routes by model: {json.dumps(summary['routes_by_model'], sort_keys=True)}",
            f"Routes by model alias: {json.dumps(summary['routes_by_model_alias'], sort_keys=True)}",
            f"Routes by risk: {json.dumps(summary['routes_by_risk'], sort_keys=True)}",
            f"Routes by context size: {json.dumps(summary['routes_by_context_size'], sort_keys=True)}",
            f"Human review required count: {summary['human_review_required_count']}",
            f"Live-prod count: {summary['live_prod_count']}",
            f"Sensitive-task count: {summary['sensitive_task_count']}",
            f"Escalation count: {summary['escalation_count']}",
            f"Estimated cost units saved: {savings['estimated_units_saved']} ({savings['estimated_percent_saved']}%)",
            f"Estimated context units saved: {savings['estimated_context_units_saved']} ({savings['estimated_context_percent_saved']}%)",
            f"Top matched rules: {summary['top_matched_rules']}",
            f"Top projects by advanced routes: {summary['top_projects_by_advanced_routes']}",
            f"Top projects by human review required: {summary['top_projects_by_human_review_required']}",
        ]
    )


def _task_result(index: int, task: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    return {
        "index": index,
        "project_name": task["project_name"],
        "task_description": task["task_description"],
        "files_touched": task.get("files_touched", []),
        "live_prod": bool(task.get("live_prod")),
        "previous_failure_count": task.get("previous_failure_count", 0),
        "recommended_model": result["recommended_model"],
        "model_tier": result["model_tier"],
        "selected_model_alias": result["selected_model_alias"],
        "risk_level": result["risk_level"],
        "context_size": result["context_pack"]["context_size"],
        "human_review_required": result["human_review_required"],
        "sticky_route_used": result["sticky_route_used"],
        "matched_rules": result["matched_rules"],
        "route_id": result["route_id"],
    }


def _summary(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(tasks)
    router_cost = sum(TIER_UNITS[item["model_tier"]] for item in tasks)
    naive_cost = total * TIER_UNITS["advanced"]
    router_context = sum(CONTEXT_UNITS[item["context_size"]] for item in tasks)
    naive_context = total * CONTEXT_UNITS["large"]
    advanced = [item for item in tasks if item["model_tier"] == "advanced"]
    human = [item for item in tasks if item["human_review_required"]]
    return {
        "total_tasks": total,
        "routes_by_tier": dict(Counter(item["model_tier"] for item in tasks)),
        "routes_by_model": dict(Counter(item["recommended_model"] for item in tasks)),
        "routes_by_model_alias": dict(Counter(item["selected_model_alias"] for item in tasks)),
        "routes_by_risk": dict(Counter(item["risk_level"] for item in tasks)),
        "routes_by_context_size": dict(Counter(item["context_size"] for item in tasks)),
        "human_review_required_count": len(human),
        "live_prod_count": sum(1 for item in tasks if item["live_prod"] or "live_prod_project" in item["matched_rules"]),
        "sensitive_task_count": sum(1 for item in tasks if any(rule.split(":", 1)[0] in {"sensitive_project", "sensitive_data"} for rule in item["matched_rules"])),
        "sticky_routes_used_count": sum(1 for item in tasks if item["sticky_route_used"]),
        "escalation_count": sum(1 for item in tasks if "previous_failures_escalate" in item["matched_rules"]),
        "top_matched_rules": Counter(rule.split(":", 1)[0] for item in tasks for rule in item["matched_rules"]).most_common(8),
        "top_projects_by_advanced_routes": Counter(item["project_name"] for item in advanced).most_common(5),
        "top_projects_by_human_review_required": Counter(item["project_name"] for item in human).most_common(5),
        "savings": {
            "naive_all_advanced_cost": naive_cost,
            "router_estimated_cost": router_cost,
            "estimated_units_saved": naive_cost - router_cost,
            "estimated_percent_saved": _percent(naive_cost - router_cost, naive_cost),
            "naive_full_repo_context": naive_context,
            "router_estimated_context": router_context,
            "estimated_context_units_saved": naive_context - router_context,
            "estimated_context_percent_saved": _percent(naive_context - router_context, naive_context),
        },
    }


def _percent(saved: int, total: int) -> float:
    return round((saved / total) * 100, 1) if total else 0.0
