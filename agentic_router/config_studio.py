from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .config_validation import CONFIG_FILES, contains_sensitive_value, load_config, validate_config
from .models import DATA_DIR

EXPORT_CONFIG_DEFAULT = DATA_DIR.parent / "exports" / "config" / "agentic_router_config_bundle.json"


def export_config(output: Path | str = EXPORT_CONFIG_DEFAULT, data_dir: Path | None = None) -> dict[str, Any]:
    validation = validate_config(data_dir=data_dir)
    if not validation["ok"]:
        raise ValueError("cannot export invalid config")
    cfg = load_config(data_dir)
    bundle = {
        "bundle_version": 1,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        **cfg,
        "enterprise_template_metadata": _enterprise_metadata(data_dir or DATA_DIR),
    }
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
    return {"output": str(target), "validation": validation}


def import_config(input_path: Path | str, dry_run: bool = True, apply: bool = False, data_dir: Path | None = None) -> dict[str, Any]:
    bundle = json.loads(Path(input_path).read_text(encoding="utf-8"))
    cfg = {key: bundle[key] for key in CONFIG_FILES}
    validation = validate_config(cfg)
    if not validation["ok"]:
        raise ValueError("import bundle failed validation")
    if contains_sensitive_value(bundle):
        raise ValueError("import bundle contains a secret-looking value or private path")
    if dry_run or not apply:
        return {"applied": False, "dry_run": True, "validation": validation}

    root = data_dir or DATA_DIR
    backup = root / "config_backups" / f"config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text(json.dumps(load_config(root), indent=2, sort_keys=True), encoding="utf-8")
    for key, filename in CONFIG_FILES.items():
        (root / filename).write_text(json.dumps(cfg[key], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _clear_project_cache()
    return {"applied": True, "dry_run": False, "backup": str(backup), "validation": validation}


def add_project(project: dict[str, Any], data_dir: Path | None = None) -> dict[str, Any]:
    root = data_dir or DATA_DIR
    entry = _project_entry(project)
    if contains_sensitive_value(entry):
        raise ValueError("project entry contains a secret-looking value or private path")
    cfg = load_config(root)
    projects = cfg["projects"]["projects"]
    if any(item["name"].casefold() == entry["name"].casefold() for item in projects):
        raise ValueError("project already exists")
    projects.append(entry)
    validation = validate_config(cfg)
    if not validation["ok"]:
        raise ValueError("; ".join(validation["errors"]))
    (root / "projects.json").write_text(json.dumps(cfg["projects"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _clear_project_cache()
    return {"saved": True, "project": entry, "validation": validation}


def _project_entry(project: dict[str, Any]) -> dict[str, Any]:
    risk = str(project.get("risk_level", "")).strip().lower()
    if risk not in {"low", "medium", "high"}:
        raise ValueError("risk_level must be low, medium, or high")
    name = str(project.get("project_name") or project.get("name") or "").strip()
    if not name:
        raise ValueError("project_name is required")
    sensitive_domains = _items(project.get("sensitive_domains", []))
    department = str(project.get("department", "")).strip()
    status = str(project.get("status", "")).strip()
    routing_notes = str(project.get("routing_notes", "")).strip()
    return {
        "name": name,
        "department": department,
        "status": status,
        "risk_level": risk,
        "default_tier": {"low": "cheap", "medium": "mid", "high": "advanced"}[risk],
        "live_prod": bool(project.get("live_prod")),
        "sensitive": bool(sensitive_domains),
        "sensitive_domains": sensitive_domains,
        "routing_notes": routing_notes,
        "keywords": [item for item in [department, status, *sensitive_domains, routing_notes] if item],
    }


def _items(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _enterprise_metadata(data_dir: Path) -> dict[str, Any]:
    path = data_dir / "enterprise_gateway_templates.json"
    if not path.exists():
        return {"available": False}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "available": True,
        "routing_policy_count": len(data.get("routing_policies", [])),
        "budget_group_count": len(data.get("team_budget_groups", {})),
        "guardrail_count": len(data.get("guardrails", [])),
    }


def _clear_project_cache() -> None:
    from .projects import load_projects

    load_projects.cache_clear()
