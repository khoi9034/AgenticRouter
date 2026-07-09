from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .models import DATA_DIR
from .rules import RISK_ORDER, TIER_ORDER

CONFIG_FILES = {
    "projects": "projects.json",
    "models": "models.json",
    "routing_rules": "routing_rules.json",
    "context_policies": "context_policies.json",
    "model_aliases": "model_aliases.json",
    "routing_profiles": "routing_profiles.json",
    "fallback_policies": "fallback_policies.json",
    "golden_tasks": "golden_tasks.json",
}
SECRET_PATTERNS = [
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    re.compile(r"\b[A-Za-z]:\\[^\s,;\"']+"),
    re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
    re.compile(r"\bbearer\s+token\s+(?=[A-Za-z0-9._-]*\d)[A-Za-z0-9._-]{4,}\b", re.I),
    re.compile(r"\b(api[-_ ]?key|token|password|secret|credential)\s*[:=]\s*[^\s,;\"']+", re.I),
    re.compile(r"\b(usb\s*)?serial\s*(number|#|:|=)\s*[A-Za-z0-9._-]{4,}\b", re.I),
]


def load_config(data_dir: Path | None = None) -> dict[str, Any]:
    root = data_dir or DATA_DIR
    return {key: _read_json(root / filename) for key, filename in CONFIG_FILES.items()}


def validate_config(config: dict[str, Any] | None = None, data_dir: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        cfg = load_config(data_dir) if config is None else config
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}

    _scan_for_secrets(cfg, errors)
    projects = cfg.get("projects", {}).get("projects", [])
    models = cfg.get("models", {}).get("models", [])
    aliases = cfg.get("model_aliases", {}).get("aliases", {})
    profiles = cfg.get("routing_profiles", {}).get("profiles", {})
    fallback_policies = cfg.get("fallback_policies", {})
    golden_tasks = cfg.get("golden_tasks", {}).get("tasks", [])
    model_names = {item.get("name") for item in models}
    alias_names = set(aliases)
    project_names = {item.get("name") for item in projects}
    project_lookup = project_names | {alias for item in projects for alias in item.get("aliases", [])}

    _validate_projects(projects, errors)
    _validate_models(cfg.get("models", {}), model_names, errors)
    _validate_rules(cfg.get("routing_rules", {}), errors)
    _validate_context_policies(cfg.get("context_policies", {}), errors)
    _validate_aliases(aliases, model_names, errors)
    _validate_profiles(profiles, alias_names, errors)
    _validate_fallbacks(fallback_policies, model_names | alias_names, errors)
    _validate_golden(golden_tasks, project_lookup, warnings, errors)
    if len(project_names) != len(projects):
        errors.append("projects.json contains duplicate project names")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def config_summary(data_dir: Path | None = None) -> dict[str, Any]:
    cfg = load_config(data_dir)
    validation = validate_config(cfg)
    projects = cfg["projects"]["projects"]
    return {
        "total_projects": len(projects),
        "projects_by_risk": dict(Counter(item["risk_level"] for item in projects)),
        "total_models": len(cfg["models"]["models"]),
        "aliases": sorted(cfg["model_aliases"]["aliases"]),
        "profiles": sorted(cfg["routing_profiles"]["profiles"]),
        "fallback_policies": sorted(cfg["fallback_policies"]),
        "golden_task_count": len(cfg["golden_tasks"]["tasks"]),
        "high_risk_project_count": sum(1 for item in projects if item["risk_level"] in {"high", "critical"}),
        "live_prod_project_count": sum(1 for item in projects if item["live_prod"]),
        "validation_status": "pass" if validation["ok"] else "fail",
        "validation_errors": validation["errors"],
        "validation_warnings": validation["warnings"],
    }


def format_validation(result: dict[str, Any]) -> str:
    lines = [f"Config validation: {'pass' if result['ok'] else 'fail'}"]
    lines += [f"ERROR: {item}" for item in result["errors"]]
    lines += [f"WARNING: {item}" for item in result["warnings"]]
    return "\n".join(lines)


def format_config_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Total projects: {summary['total_projects']}",
            f"Projects by risk: {json.dumps(summary['projects_by_risk'], sort_keys=True)}",
            f"Total models: {summary['total_models']}",
            f"Aliases: {', '.join(summary['aliases'])}",
            f"Profiles: {', '.join(summary['profiles'])}",
            f"Fallback policies: {', '.join(summary['fallback_policies'])}",
            f"Golden task count: {summary['golden_task_count']}",
            f"High-risk project count: {summary['high_risk_project_count']}",
            f"Live-prod project count: {summary['live_prod_project_count']}",
            f"Validation status: {summary['validation_status']}",
        ]
    )


def contains_sensitive_value(value: Any) -> bool:
    return any(pattern.search(text) for text in _walk_strings(value) for pattern in SECRET_PATTERNS)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _validate_projects(projects: Any, errors: list[str]) -> None:
    if not isinstance(projects, list):
        errors.append("projects.json projects must be a list")
        return
    required = {"name", "risk_level", "default_tier", "live_prod", "sensitive", "keywords"}
    for project in projects:
        missing = required - project.keys()
        if missing:
            errors.append(f"project {project.get('name', '<unknown>')} missing fields: {sorted(missing)}")
        if project.get("risk_level") not in RISK_ORDER:
            errors.append(f"project {project.get('name', '<unknown>')} has invalid risk_level")
        if project.get("default_tier") not in TIER_ORDER:
            errors.append(f"project {project.get('name', '<unknown>')} has invalid default_tier")
        if not isinstance(project.get("live_prod"), bool) or not isinstance(project.get("sensitive"), bool):
            errors.append(f"project {project.get('name', '<unknown>')} live_prod/sensitive must be booleans")
        if project.get("risk_level") in {"high", "critical"} and project.get("sensitive") and project.get("default_tier") != "advanced":
            errors.append(f"high-risk sensitive project {project.get('name')} must default to advanced")


def _validate_models(models_config: dict[str, Any], model_names: set[str], errors: list[str]) -> None:
    if not model_names:
        errors.append("models.json must define at least one model")
    for model in models_config.get("models", []):
        if {"vendor", "name", "tier"} - model.keys():
            errors.append(f"model entry missing fields: {model}")
        if model.get("tier") not in TIER_ORDER:
            errors.append(f"model {model.get('name')} has invalid tier")
    for tier, model_name in models_config.get("default_by_tier", {}).items():
        if tier not in TIER_ORDER or model_name not in model_names:
            errors.append(f"default model for {tier} points to unknown model {model_name}")


def _validate_rules(rules: dict[str, Any], errors: list[str]) -> None:
    for key in ["cheap_keywords", "mid_keywords", "advanced_keywords", "sensitive_keywords", "security_keywords"]:
        if not isinstance(rules.get(key), list):
            errors.append(f"routing_rules.json {key} must be a list")


def _validate_context_policies(policies: dict[str, Any], errors: list[str]) -> None:
    if not isinstance(policies.get("base_forbidden_context"), list):
        errors.append("context_policies.json base_forbidden_context must be a list")
    if not isinstance(policies.get("categories"), dict):
        errors.append("context_policies.json categories must be an object")


def _validate_aliases(aliases: dict[str, Any], model_names: set[str], errors: list[str]) -> None:
    for name, spec in aliases.items():
        for field in ["tier", "primary", "fallback"]:
            if field not in spec:
                errors.append(f"model alias {name} missing {field}")
        for field in ["primary", "fallback"]:
            if spec.get(field) not in model_names:
                errors.append(f"model alias {name} {field} points to unknown model {spec.get(field)}")


def _validate_profiles(profiles: dict[str, Any], alias_names: set[str], errors: list[str]) -> None:
    required = {"cost_quality_tradeoff", "allowed_model_aliases", "minimum_tier_for_sensitive_tasks", "minimum_tier_for_live_prod", "human_review_default"}
    for name, profile in profiles.items():
        missing = required - profile.keys()
        if missing:
            errors.append(f"profile {name} missing fields: {sorted(missing)}")
        if not isinstance(profile.get("cost_quality_tradeoff"), int) or not 0 <= profile.get("cost_quality_tradeoff", -1) <= 10:
            errors.append(f"profile {name} has invalid cost_quality_tradeoff")
        for alias in profile.get("allowed_model_aliases", []):
            if alias not in alias_names:
                errors.append(f"profile {name} points to unknown alias {alias}")


def _validate_fallbacks(fallbacks: dict[str, Any], known: set[str], errors: list[str]) -> None:
    for name, candidates in fallbacks.items():
        if not isinstance(candidates, list):
            errors.append(f"fallback policy {name} must be a list")
            continue
        for candidate in candidates:
            if candidate not in known:
                errors.append(f"fallback policy {name} points to unknown alias/model {candidate}")


def _validate_golden(tasks: Any, project_lookup: set[str], warnings: list[str], errors: list[str]) -> None:
    if not isinstance(tasks, list):
        errors.append("golden_tasks.json tasks must be a list")
        return
    required = {"project_name", "task_description", "expected_tier", "expected_risk", "expected_human_review_required"}
    for index, task in enumerate(tasks, 1):
        missing = required - task.keys()
        if missing:
            errors.append(f"golden task {index} missing fields: {sorted(missing)}")
        if task.get("project_name") not in project_lookup:
            warnings.append(f"golden task {index} references unknown project {task.get('project_name')}")


def _scan_for_secrets(value: Any, errors: list[str]) -> None:
    for text in _walk_strings(value):
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append("config contains a secret-looking value or private path")
                return


def _walk_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)
