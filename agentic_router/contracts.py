from __future__ import annotations

import fnmatch
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .models import DATA_DIR
from .observability import sanitize_text
from .projects import find_project

COMMON_FORBIDDEN = [
    ".env",
    "*.env",
    "*.ini",
    "config*",
    "config/*",
    "secrets/*",
    "credentials/*",
]
RISKY_CODE = ["Auth/*", "auth/*", "api/*", "database/*", "migrations/*", "*.sql"]
DEPLOYMENT_PATTERNS = ["deployment/*", "deploy/*", ".github/workflows/*", "Dockerfile", "docker-compose*.yml"]
DEPENDENCY_FILES = ["requirements.txt", "pyproject.toml", "package.json", "package-lock.json", "Pipfile", "poetry.lock"]
FORBIDDEN_DIFF_TERMS = ["secret", "password", "bearer token", "api key", "private key", "tenant id", "usb serial"]
ROLLBACK_TERMS = ["rollback", "backup", "restore"]


@lru_cache(maxsize=1)
def load_contract_policies() -> dict[str, Any]:
    with (DATA_DIR / "contract_policies.json").open(encoding="utf-8") as f:
        return json.load(f)


def generate_contract(
    project_name: str,
    task_description: str,
    files_touched: list[str] | None = None,
    previous_failure_count: int = 0,
    live_prod: bool | None = None,
    profile_name: str = "balanced",
) -> dict[str, Any]:
    from .router import route

    result = route(
        project_name=project_name,
        task_description=task_description,
        files_touched=files_touched or [],
        previous_failure_count=previous_failure_count,
        live_prod=live_prod,
        profile_name=profile_name,
    )
    return contract_from_route(project_name, task_description, files_touched or [], result)


def contract_from_route(
    project_name: str,
    task_description: str,
    files_touched: list[str],
    route_result: dict[str, Any],
) -> dict[str, Any]:
    project = find_project(project_name)
    normalized = route_result.get("normalized_task", {})
    policy_name = _policy_name(route_result)
    policy = load_contract_policies()["policies"][policy_name]
    allowed = _allowed_patterns(policy_name, files_touched, route_result)
    forbidden = _unique([*policy["forbidden_file_patterns"], *COMMON_FORBIDDEN])
    if policy_name in {"docs", "static_ui"}:
        forbidden = _unique([*forbidden, *RISKY_CODE, *DEPENDENCY_FILES])
    if policy_name != "production":
        forbidden = _unique([*forbidden, *DEPLOYMENT_PATTERNS])

    human_review = bool(
        route_result["human_review_required"]
        or route_result["risk_level"] == "high"
        or policy_name in {"backend", "production", "external_write", "destructive", "sensitive_file"}
    )
    production_cautions = _production_cautions(route_result, policy_name)
    sensitive_cautions = _sensitive_cautions(route_result, policy_name)
    extra_validation = []
    summary = (normalized.get("normalized_summary") or task_description).casefold()
    if policy_name in {"production", "destructive"}:
        extra_validation.append("Confirm rollback or backup plan is documented.")
    if "email" in summary or "send" in summary:
        extra_validation.append("Use dry-run or test mode if available and validate outgoing payloads.")
    if "upload" in summary or "download" in summary:
        extra_validation.append("Check upload/download authorization and sanitized file handling.")
    required_validation = _unique([*policy["required_validation"], *extra_validation])

    return {
        "contract_id": _contract_id(route_result["route_id"], project_name, task_description, files_touched),
        "project_name": project_name,
        "task_summary": normalized.get("normalized_summary") or sanitize_text(task_description, 180),
        "task_type": route_result.get("task_type") or normalized.get("task_type", "general"),
        "risk_level": route_result["risk_level"],
        "model_tier": route_result["model_tier"],
        "allowed_file_patterns": allowed,
        "forbidden_file_patterns": forbidden,
        "allowed_actions": policy["allowed_actions"],
        "forbidden_actions": _unique([*policy["forbidden_actions"], "Store secrets, PII, tokens, credentials, emails, serials, or production logs."]),
        "required_validation": required_validation,
        "stop_conditions": _unique([*policy["stop_conditions"], "Stop if requested scope expands beyond this contract."]),
        "human_review_required": human_review,
        "production_cautions": production_cautions,
        "sensitive_data_cautions": sensitive_cautions,
        "contract_reasoning": _reason(policy_name, project, route_result),
    }


def check_contract(
    contract: dict[str, Any],
    changed_files: list[str],
    diff_summary: str = "",
    added_dependencies: list[str] | None = None,
) -> dict[str, Any]:
    files = [_clean_path(path) for path in changed_files if str(path).strip()]
    forbidden = _matches(files, contract.get("forbidden_file_patterns", []))
    allowed = _matches(files, contract.get("allowed_file_patterns", []))
    outside = [path for path in files if path not in forbidden and path not in allowed]
    violations = []
    warnings = []
    if forbidden:
        violations.append("Changed forbidden files: " + ", ".join(forbidden))
    if outside:
        violations.append("Changed files outside allowed scope: " + ", ".join(outside))
    if _has_any(diff_summary, FORBIDDEN_DIFF_TERMS):
        violations.append("Diff summary mentions forbidden sensitive material.")
    if added_dependencies:
        warnings.append("Unexpected dependencies added: " + ", ".join(sanitize_text(item, 80) for item in added_dependencies))
    if contract.get("human_review_required"):
        warnings.append("Human review is required by this contract.")
    if contract.get("risk_level") == "high" and _has_any(diff_summary, ROLLBACK_TERMS) is False:
        warnings.append("High-risk change should include rollback or backup notes.")

    decision = "fail" if violations else "warn" if warnings else "pass"
    return {
        "decision": decision,
        "violations": violations,
        "warnings": warnings,
        "changed_files_reviewed": files,
        "forbidden_matches": forbidden,
        "allowed_matches": allowed,
        "human_review_required": bool(contract.get("human_review_required")) or decision != "pass",
        "risk_level": contract.get("risk_level", "low"),
        "explanation": _check_explanation(decision, violations, warnings),
    }


def load_contract_file(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def format_contract(contract: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Contract ID: {contract['contract_id']}",
            f"Project: {contract['project_name']}",
            f"Task: {contract['task_summary']}",
            f"Risk: {contract['risk_level']}",
            f"Tier: {contract['model_tier']}",
            f"Human review required: {'yes' if contract['human_review_required'] else 'no'}",
            "Allowed files:\n" + _bullets(contract["allowed_file_patterns"]),
            "Forbidden files:\n" + _bullets(contract["forbidden_file_patterns"]),
            "Allowed actions:\n" + _bullets(contract["allowed_actions"]),
            "Forbidden actions:\n" + _bullets(contract["forbidden_actions"]),
            "Validation:\n" + _bullets(contract["required_validation"]),
            "Stop conditions:\n" + _bullets(contract["stop_conditions"]),
            "Reason: " + contract["contract_reasoning"],
        ]
    )


def format_scope_check(result: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Decision: {result['decision']}",
            f"Risk: {result['risk_level']}",
            f"Human review required: {'yes' if result['human_review_required'] else 'no'}",
            "Violations:\n" + _bullets(result["violations"] or ["none"]),
            "Warnings:\n" + _bullets(result["warnings"] or ["none"]),
            "Explanation: " + result["explanation"],
        ]
    )


def _policy_name(result: dict[str, Any]) -> str:
    capabilities = set(result.get("requested_capabilities", []))
    operation = result.get("operation_type")
    summary = result.get("normalized_task", {}).get("normalized_summary", "").casefold()
    if operation == "destructive":
        return "destructive"
    if operation == "deployment" or "live_prod_project" in result.get("matched_rules", []):
        return "production"
    if capabilities & {"email_file_transfer", "enterprise_system_write", "microsoft_graph_intune"}:
        return "external_write"
    if "sensitive_records" in capabilities or operation in {"upload", "download"}:
        return "sensitive_file"
    if capabilities & {"authentication_admin", "backend_api", "database_sql", "security_infrastructure", "secrets_credentials"}:
        return "backend"
    if operation == "documentation" and any(term in summary for term in ["readme", "docs", "documentation", "copy", "wording"]):
        return "docs"
    if operation == "visual_polish" or result.get("model_tier") == "cheap":
        return "static_ui"
    return "normal_app"


def _allowed_patterns(policy_name: str, files: list[str], result: dict[str, Any]) -> list[str]:
    policy = load_contract_policies()["policies"][policy_name]
    touched = [_clean_path(path) for path in files]
    if policy_name in {"docs", "static_ui"}:
        touched = [path for path in touched if _matches_one(path, policy["allowed_file_patterns"])]
    return _unique([*touched, *policy["allowed_file_patterns"]])


def _production_cautions(result: dict[str, Any], policy_name: str) -> list[str]:
    if policy_name == "production" or result.get("normalized_task", {}).get("production_sensitive"):
        return [
            "Require human approval before deployment.",
            "Document rollback or backup plan before production changes.",
            "Do not make broad refactors in live-prod scope.",
        ]
    return []


def _sensitive_cautions(result: dict[str, Any], policy_name: str) -> list[str]:
    if policy_name in {"backend", "production", "external_write", "sensitive_file", "destructive"} or result.get("human_review_required"):
        return [
            "Use sanitized context only.",
            "Do not include secrets, PII, records, tokens, credentials, emails, tenant IDs, USB serials, or production logs.",
        ]
    return []


def _reason(policy_name: str, project: dict[str, Any], result: dict[str, Any]) -> str:
    normalized = result.get("normalized_task", {})
    return (
        f"Applied {policy_name} contract from project risk={project.get('risk_level', result['risk_level'])}, "
        f"intrinsic risk={result.get('intrinsic_task_risk')}, operation={result.get('operation_type')}, "
        f"capabilities={', '.join(result.get('requested_capabilities', [])) or 'none'}."
    ) + (" " + normalized.get("risk_reason", "") if normalized.get("risk_reason") else "")


def _contract_id(route_id: str, project_name: str, task: str, files: list[str]) -> str:
    digest = hashlib.sha256("|".join([route_id, project_name, task, *files]).encode("utf-8")).hexdigest()[:12]
    return f"arc_{digest}"


def _matches(files: list[str], patterns: list[str]) -> list[str]:
    return [path for path in files if _matches_one(path, patterns)]


def _matches_one(path: str, patterns: list[str]) -> bool:
    clean = _clean_path(path).casefold()
    name = clean.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(clean, pattern.casefold()) or fnmatch.fnmatch(name, pattern.casefold()) for pattern in patterns)


def _clean_path(path: str) -> str:
    return str(path).strip().replace("\\", "/")


def _has_any(text: str, terms: list[str]) -> bool:
    folded = str(text).casefold()
    return any(term in folded for term in terms)


def _check_explanation(decision: str, violations: list[str], warnings: list[str]) -> str:
    if decision == "fail":
        return "Scope guard failed because changed files or diff summary violated the run contract."
    if decision == "warn":
        return "Scope guard found no hard file violation, but review is needed before proceeding."
    return "Changed files fit the allowed contract scope."


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _unique(items) -> list[str]:
    seen = set()
    return [item for item in items if item and not (item in seen or seen.add(item))]
