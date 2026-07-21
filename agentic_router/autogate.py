from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import check_contract
from .diff_review import review_diff
from .models import DATA_DIR
from .observability import sanitize_text
from .packets import packet_from_route
from .router import route

RUN_RECORDS = DATA_DIR / "run_records.jsonl"
FINAL_DECISIONS = {"auto_approved", "auto_blocked", "needs_tests", "needs_retry", "needs_more_evidence", "rollback_required"}


def run_records_path() -> Path:
    return Path(os.environ.get("AGENTIC_ROUTER_RUN_RECORDS", RUN_RECORDS))


def start_run(
    project_name: str,
    task_description: str,
    files_touched: list[str] | None = None,
    live_prod: bool | None = None,
    previous_failure_count: int = 0,
    routing_profile: str = "balanced",
) -> dict[str, Any]:
    files = files_touched or []
    result = route(
        project_name=project_name,
        task_description=task_description,
        files_touched=files,
        previous_failure_count=previous_failure_count,
        live_prod=live_prod,
        profile_name=routing_profile,
    )
    packet = packet_from_route(project_name, task_description, files, result)
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    requirements = automated_requirements(result["risk_level"], bool(live_prod))
    start_status = "caution" if result["risk_level"] != "low" or live_prod else "ready"
    record = _start_record(run_id, project_name, task_description, files, result, packet, requirements, start_status, bool(live_prod), routing_profile)
    _append_record(record)
    return {
        "run_id": run_id,
        "project_name": project_name,
        "normalized_task": result["normalized_task"],
        "recommended_model": result["recommended_model"],
        "model_tier": result["model_tier"],
        "risk_level": result["risk_level"],
        "context_pack": result["context_pack"],
        "run_packet": packet,
        "run_contract": packet["run_contract"],
        "automated_requirements": requirements,
        "start_status": start_status,
        "reason": _start_reason(result["risk_level"], start_status),
    }


def complete_run(
    run_id: str,
    changed_files: list[str],
    git_diff: str = "",
    tests_run: list[str] | None = None,
    test_status: str = "not_run",
    rollback_plan_present: bool = False,
    notes: str = "",
) -> dict[str, Any]:
    record = get_run(run_id)
    if not record:
        raise ValueError(f"unknown run_id: {run_id}")
    if test_status not in {"passed", "failed", "not_run"}:
        raise ValueError("test_status must be passed, failed, or not_run")
    tests = tests_run or []
    contract = record["run_contract"]
    files = changed_files or []
    scope = check_contract(contract, files, _diff_summary(git_diff), [])
    diff = review_diff(
        project_name=record["project_name"],
        task_description=record["task_summary"],
        run_contract=contract,
        changed_files=files,
        git_diff=git_diff,
        tests_run=tests,
        live_prod=record.get("live_prod", False),
    )
    decision, reason = _final_decision(record, files, git_diff, tests, test_status, rollback_plan_present, scope, diff)
    completion = {
        **record,
        "event": "completed",
        "timestamp": _now(),
        "status": decision,
        "final_decision": decision,
        "changed_files": [sanitize_text(item, 160) for item in files],
        "tests_run": [sanitize_text(item, 120) for item in tests],
        "test_status": test_status,
        "rollback_plan_present": rollback_plan_present,
        "notes": sanitize_text(notes, 220),
        "scope_guard": scope,
        "diff_review": diff,
        "approval_gate_reason": reason,
        "requirements_met": decision == "auto_approved",
    }
    _append_record(completion)
    return completion


def get_run(run_id: str) -> dict[str, Any] | None:
    return latest_runs().get(run_id)


def list_runs() -> list[dict[str, Any]]:
    return sorted(latest_runs().values(), key=lambda item: item.get("timestamp", ""), reverse=True)


def clear_runs() -> dict[str, Any]:
    path = run_records_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    return {"cleared": True, "path": str(path)}


def latest_runs() -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for record in load_run_records():
        latest[record["run_id"]] = record
    return latest


def load_run_records() -> list[dict[str, Any]]:
    path = run_records_path()
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def automated_requirements(risk_level: str, live_prod: bool = False) -> dict[str, Any]:
    checks = ["contract_pass_required", "diff_pass_required"]
    tests_required = risk_level == "high"
    tests_or_validation = risk_level == "medium"
    rollback_required = bool(live_prod)
    if tests_or_validation:
        checks.append("tests_or_validation_required")
    if tests_required:
        checks += [
            "tests_required",
            "no_secret_detection_required",
            "no_auth_bypass_required",
            "no_destructive_operation_without_safety_required",
        ]
    if rollback_required:
        checks.append("rollback_plan_required")
    return {
        "risk_level": risk_level,
        "required_checks": checks,
        "tests_required": tests_required,
        "tests_or_validation_required": tests_or_validation,
        "rollback_plan_required": rollback_required,
        "legacy_human_review_field_is_not_primary": True,
    }


def format_run(result: dict[str, Any]) -> str:
    decision = result.get("final_decision") or result.get("start_status") or result.get("status")
    return "\n".join(
        [
            f"Run ID: {result['run_id']}",
            f"Project: {result['project_name']}",
            f"Decision/status: {decision}",
            f"Risk: {result['risk_level']}",
            f"Tier: {result['model_tier']}",
            f"Model: {result['recommended_model']}",
            f"Reason: {result.get('approval_gate_reason') or result.get('reason', '')}",
        ]
    )


def format_run_list(runs: list[dict[str, Any]]) -> str:
    if not runs:
        return "No runs recorded."
    return "\n".join(
        f"{item['run_id']} | {item['project_name']} | {item['risk_level']} | {item['model_tier']} | {item.get('final_decision') or item.get('start_status')}"
        for item in runs
    )


def _start_record(
    run_id: str,
    project_name: str,
    task_description: str,
    files: list[str],
    result: dict[str, Any],
    packet: dict[str, Any],
    requirements: dict[str, Any],
    start_status: str,
    live_prod: bool,
    profile: str,
) -> dict[str, Any]:
    high = result["risk_level"] == "high" or result["model_tier"] == "advanced"
    summary = "[redacted-high-risk-task]" if high else sanitize_text(task_description, 180)
    record = {
        "event": "started",
        "timestamp": _now(),
        "run_id": run_id,
        "project_name": project_name,
        "task_summary": summary,
        "risk_level": result["risk_level"],
        "model_tier": result["model_tier"],
        "recommended_model": result["recommended_model"],
        "route_id": result["route_id"],
        "normalized_task": result["normalized_task"],
        "context_size": result["context_pack"]["context_size"],
        "run_contract": packet["run_contract"],
        "automated_requirements": requirements,
        "start_status": start_status,
        "status": start_status,
        "live_prod": live_prod,
        "routing_profile": profile,
        "files_touched": [sanitize_text(item, 160) for item in files],
        "legacy_human_review_required": result["human_review_required"],
    }
    if high:
        record["task_description_hash"] = hashlib.sha256(task_description.encode("utf-8")).hexdigest()[:16]
    return record


def _final_decision(
    record: dict[str, Any],
    files: list[str],
    git_diff: str,
    tests_run: list[str],
    test_status: str,
    rollback_plan_present: bool,
    scope: dict[str, Any],
    diff: dict[str, Any],
) -> tuple[str, str]:
    req = record["automated_requirements"]
    if scope["decision"] == "fail":
        return "auto_blocked", "Scope Guard failed; forbidden or out-of-contract files changed."
    if diff["decision"] == "fail":
        return "auto_blocked", "Diff Review found a blocking violation."
    if record.get("live_prod") and "dependency_config_deploy" in diff["detected_change_types"]:
        return "auto_blocked", "Live-prod config/deploy changes are blocked automatically."
    if test_status == "failed":
        return "needs_retry", "Tests failed; retry with a fix."
    if _missing_evidence(record["risk_level"], files, git_diff):
        return "needs_more_evidence", "Changed files or diff evidence is missing."
    if req["tests_required"] and test_status != "passed":
        return "needs_tests", "High-risk run requires passing automated tests."
    if req["tests_or_validation_required"] and test_status != "passed" and not tests_run:
        return "needs_tests", "Medium-risk run requires tests or documented validation."
    if req["rollback_plan_required"] and not rollback_plan_present:
        return "rollback_required", "Live-prod run requires rollback evidence."
    return "auto_approved", "All automated requirements passed."


def _missing_evidence(risk_level: str, files: list[str], git_diff: str) -> bool:
    if not files and not git_diff.strip():
        return True
    return risk_level in {"medium", "high"} and not git_diff.strip()


def _append_record(record: dict[str, Any]) -> None:
    path = run_records_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def _diff_summary(git_diff: str) -> str:
    return sanitize_text(" ".join(line[1:] for line in git_diff.splitlines() if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))), 500)


def _start_reason(risk: str, status: str) -> str:
    if status == "ready":
        return "Low-risk run is ready for automated execution."
    return f"{risk} risk run is ready with stronger automated evidence requirements."


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
