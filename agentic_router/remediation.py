from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from .autogate import get_run
from .evidence import build_validation_plan
from .observability import sanitize_text

NEXT_ACTIONS = {
    "auto_approved": "no_action_needed",
    "needs_tests": "run_tests",
    "needs_retry": "retry_agent",
    "needs_more_evidence": "collect_more_evidence",
    "rollback_required": "rollback_required",
    "auto_blocked": "blocked_fix_required",
}


def remediation_for_run(run_id: str, repo_path: str | Path | None = None) -> dict[str, Any]:
    run = get_run(run_id)
    if not run:
        raise ValueError(f"unknown run_id: {run_id}")
    return remediation_for_result(run, repo_path=repo_path)


def remediation_for_result(result: dict[str, Any], repo_path: str | Path | None = None) -> dict[str, Any]:
    autogate, evidence = _split_result(result)
    decision = autogate.get("final_decision") or autogate.get("status") or autogate.get("start_status") or "needs_more_evidence"
    contract = autogate.get("run_contract", {})
    scope = autogate.get("scope_guard", {})
    diff = autogate.get("diff_review", {})
    validation_results = evidence.get("validation_results") or _validation_results_from_run(autogate)
    validation_commands = _validation_commands(autogate, evidence, repo_path)
    missing = _missing_evidence(autogate, evidence)
    block_reasons = _block_reasons(autogate, scope, diff)
    corrective_steps = _corrective_steps(block_reasons, diff)
    next_action = NEXT_ACTIONS.get(decision, "collect_more_evidence")
    severity = _severity(decision, autogate, block_reasons)
    retry_packet = _retry_packet(autogate, contract, validation_results, validation_commands, corrective_steps, next_action)
    plan = {
        "remediation_id": f"remediation_{uuid.uuid4().hex[:12]}",
        "source_run_id": autogate.get("run_id"),
        "current_decision": decision,
        "next_action": next_action,
        "severity": severity,
        "explanation": _explanation(decision, autogate, evidence, block_reasons, missing),
        "retry_task_summary": retry_packet["task_summary"],
        "retry_packet": retry_packet,
        "allowed_files": contract.get("allowed_file_patterns", []),
        "forbidden_files": contract.get("forbidden_file_patterns", []),
        "validation_commands": validation_commands,
        "evidence_needed": _evidence_needed(decision, missing, evidence, validation_commands),
        "rollback_steps": _rollback_steps(autogate) if decision == "rollback_required" else [],
        "block_reasons": block_reasons,
        "safe_correction_steps": corrective_steps,
        "stop_conditions": _stop_conditions(contract, decision),
        "auto_retry_allowed": _auto_retry_allowed(decision, autogate, scope, diff, corrective_steps),
    }
    return plan


def retry_packet_for_run(run_id: str, repo_path: str | Path | None = None) -> dict[str, Any]:
    return remediation_for_run(run_id, repo_path=repo_path)["retry_packet"]


def remediation_from_file(path: str | Path, repo_path: str | Path | None = None) -> dict[str, Any]:
    return remediation_for_result(json.loads(Path(path).read_text(encoding="utf-8")), repo_path=repo_path)


def format_remediation(plan: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Remediation ID: {plan['remediation_id']}",
            f"Run ID: {plan.get('source_run_id') or 'unknown'}",
            f"Decision: {plan['current_decision']}",
            f"Next action: {plan['next_action']}",
            f"Severity: {plan['severity']}",
            f"Auto retry allowed: {plan['auto_retry_allowed']}",
            f"Explanation: {plan['explanation']}",
            "Validation commands:\n" + _bullets([" ".join(item["command"]) for item in plan["validation_commands"]] or ["none"]),
            "Evidence needed:\n" + _bullets(plan["evidence_needed"] or ["none"]),
            "Block reasons:\n" + _bullets(plan["block_reasons"] or ["none"]),
            "Rollback steps:\n" + _bullets(plan["rollback_steps"] or ["none"]),
            "Stop conditions:\n" + _bullets(plan["stop_conditions"] or ["none"]),
        ]
    )


def _split_result(result: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if "autogate" in result:
        return result["autogate"], result.get("evidence", {})
    return result, result.get("evidence", {})


def _validation_results_from_run(run: dict[str, Any]) -> list[dict[str, Any]]:
    status = run.get("test_status")
    if status not in {"passed", "failed"}:
        return []
    return [
        {"name": name, "command": [name], "status": status, "stdout": "", "stderr": run.get("notes", "")}
        for name in run.get("tests_run", [])
    ]


def _validation_commands(run: dict[str, Any], evidence: dict[str, Any], repo_path: str | Path | None) -> list[dict[str, Any]]:
    commands = (evidence.get("validation_plan") or {}).get("commands", [])
    if commands:
        return commands
    if repo_path:
        try:
            return build_validation_plan(run, repo_path, run.get("changed_files") or run.get("files_touched") or [])["commands"]
        except (OSError, ValueError):
            return []
    return []


def _missing_evidence(run: dict[str, Any], evidence: dict[str, Any]) -> list[str]:
    if evidence.get("missing_evidence"):
        return evidence["missing_evidence"]
    missing = []
    if run.get("final_decision") == "needs_more_evidence":
        if not run.get("changed_files"):
            missing.append("changed_files")
        if run.get("risk_level") in {"medium", "high"} and not run.get("diff_review", {}).get("detected_change_types") and not run.get("scope_guard"):
            missing.append("git_diff")
    if run.get("final_decision") == "needs_tests":
        missing.append("test_output")
    if run.get("final_decision") == "rollback_required":
        missing.append("rollback_plan")
    return missing


def _block_reasons(run: dict[str, Any], scope: dict[str, Any], diff: dict[str, Any]) -> list[str]:
    reasons = []
    for item in scope.get("violations", []):
        folded = item.casefold()
        if "forbidden" in folded:
            reasons.append("forbidden_file_change")
        elif "outside allowed" in folded:
            reasons.append("out_of_contract_change")
    detected = set(diff.get("detected_change_types", []))
    if "secret_credential_added" in detected:
        reasons.append("secret_detected")
    if "auth_bypass_or_weakening" in detected:
        reasons.append("auth_bypass")
    if "destructive_or_bulk_operation" in detected:
        reasons.append("destructive_operation")
    if "database_schema_or_persistence" in detected:
        reasons.append("destructive_sql_or_schema_risk")
    if run.get("approval_gate_reason"):
        text = run["approval_gate_reason"].casefold()
        if "config/deploy" in text:
            reasons.append("production_config_risk")
        if "diff review" in text and not reasons:
            reasons.append("diff_review_block")
        if "scope guard" in text and not reasons:
            reasons.append("scope_guard_block")
    return _unique(reasons)


def _corrective_steps(block_reasons: list[str], diff: dict[str, Any]) -> list[str]:
    steps = []
    if "secret_detected" in block_reasons:
        steps.append("Remove the secret-looking value and use a sanitized placeholder or environment variable name.")
    if "forbidden_file_change" in block_reasons or "out_of_contract_change" in block_reasons:
        steps.append("Undo forbidden or out-of-contract file changes, or start a new run with a contract that explicitly covers that scope.")
    if "auth_bypass" in block_reasons:
        steps.append("Restore the auth, permission, or validation check and add/confirm unauthorized-access validation.")
    if "destructive_operation" in block_reasons or "destructive_sql_or_schema_risk" in block_reasons:
        steps.append("Remove destructive or unbounded operations, or add bounded safety guards plus rollback evidence.")
    if "production_config_risk" in block_reasons:
        steps.append("Revert production config/deploy changes until rollback and approval evidence are available.")
    if diff.get("decision") == "fail" or block_reasons:
        steps.append("Rerun Diff Review and AutoGate after the correction.")
    return _unique(steps)


def _retry_packet(
    run: dict[str, Any],
    contract: dict[str, Any],
    validation_results: list[dict[str, Any]],
    validation_commands: list[dict[str, Any]],
    corrective_steps: list[str],
    next_action: str,
) -> dict[str, Any]:
    failed = [item for item in validation_results if item.get("status") in {"failed", "timed_out"}]
    changed_files = run.get("changed_files") or run.get("files_touched") or []
    task = run.get("task_summary") or contract.get("task_summary") or "Retry the original task safely."
    instructions = [
        "Fix only the failing issue",
        "Do not expand scope",
        "Do not touch forbidden files.",
        "Rerun failed validation commands.",
    ]
    if next_action == "blocked_fix_required":
        instructions = [*corrective_steps, "Do not continue until the blocking issue is removed."]
    return {
        "task_summary": sanitize_text(task, 220),
        "changed_files": changed_files,
        "failed_commands": [_failed_command(item) for item in failed],
        "failed_output_summary": sanitize_text(" ".join(item.get("stderr") or item.get("stdout") or "" for item in failed), 500),
        "validation_commands_to_rerun": validation_commands,
        "allowed_files": contract.get("allowed_file_patterns", []),
        "forbidden_files": contract.get("forbidden_file_patterns", []),
        "instructions": _unique(instructions),
        "stop_conditions": contract.get("stop_conditions", []),
        "prompt": _retry_prompt(task, changed_files, contract, failed, validation_commands, instructions),
    }


def _retry_prompt(
    task: str,
    changed_files: list[str],
    contract: dict[str, Any],
    failed: list[dict[str, Any]],
    validation_commands: list[dict[str, Any]],
    instructions: list[str],
) -> str:
    return "\n".join(
        [
            "DevSpace AutoGate retry packet.",
            f"Original task: {sanitize_text(task, 220)}",
            f"Changed files to inspect: {', '.join(changed_files) or 'none supplied'}",
            f"Allowed files: {', '.join(contract.get('allowed_file_patterns', [])) or 'none'}",
            f"Forbidden files: {', '.join(contract.get('forbidden_file_patterns', [])) or 'none'}",
            "Instructions:",
            *_prefixed(instructions),
            "Failed validation:",
            *_prefixed([_failed_command(item) for item in failed] or ["none recorded"]),
            "Validation commands to rerun:",
            *_prefixed([" ".join(item["command"]) for item in validation_commands] or ["rerun the safest relevant local validation"]),
            "Report back with changed files, sanitized diff summary, validation status, and whether rollback evidence exists.",
        ]
    )


def _evidence_needed(decision: str, missing: list[str], evidence: dict[str, Any], validation_commands: list[dict[str, Any]]) -> list[str]:
    needed = list(missing)
    if decision == "needs_tests":
        needed.append("passing_validation_results")
        if not validation_commands:
            needed.append("safe_validation_command_or_manual_test_summary")
    if decision == "needs_more_evidence" and evidence.get("tests_status") in {"unavailable", "not_run"}:
        needed.append("test_output")
    if decision == "rollback_required":
        needed.append("rollback_plan")
    return _unique(needed)


def _rollback_steps(run: dict[str, Any]) -> list[str]:
    return [
        "Identify every changed file in the run.",
        "Preserve current evidence, diff summary, and validation output.",
        "Restore the previous version or apply the documented rollback path.",
        "Rerun the safest relevant validation commands.",
        "Rerun AutoGate with rollback evidence present.",
    ]


def _stop_conditions(contract: dict[str, Any], decision: str) -> list[str]:
    base = contract.get("stop_conditions", [])
    extra = []
    if decision == "auto_blocked":
        extra.append("Stop until the blocking Scope Guard or Diff Review issue is corrected.")
    if decision == "rollback_required":
        extra.append("Stop before further changes until rollback evidence exists.")
    return _unique([*base, *extra])


def _auto_retry_allowed(decision: str, run: dict[str, Any], scope: dict[str, Any], diff: dict[str, Any], corrective_steps: list[str]) -> bool:
    risk = run.get("risk_level", "low")
    if decision == "needs_retry":
        return risk in {"low", "medium"} and scope.get("decision", "pass") != "fail" and diff.get("decision", "pass") != "fail"
    if decision == "needs_tests":
        return risk in {"low", "medium"}
    if decision == "auto_blocked":
        return False
    return False


def _severity(decision: str, run: dict[str, Any], block_reasons: list[str]) -> str:
    if decision == "auto_approved":
        return "low"
    if decision in {"auto_blocked", "rollback_required"} or run.get("risk_level") == "high":
        return "high"
    if block_reasons or decision in {"needs_retry", "needs_tests", "needs_more_evidence"}:
        return "medium"
    return "low"


def _explanation(decision: str, run: dict[str, Any], evidence: dict[str, Any], block_reasons: list[str], missing: list[str]) -> str:
    if decision == "auto_approved":
        return "AutoGate approved the run because scope, diff, validation, and rollback requirements were satisfied."
    if decision == "needs_tests":
        return "AutoGate needs passing safe validation evidence before this run can complete."
    if decision == "needs_retry":
        return "Validation failed; retry narrowly against the failing command output without expanding scope."
    if decision == "needs_more_evidence":
        return "AutoGate needs more local evidence: " + ", ".join(missing or ["changed files, diff, or validation output"]) + "."
    if decision == "rollback_required":
        return "Live/prod or rollback-sensitive work needs rollback evidence before approval."
    if decision == "auto_blocked":
        return "AutoGate blocked the run because of: " + ", ".join(block_reasons or ["blocking scope or diff review result"]) + "."
    return run.get("approval_gate_reason") or evidence.get("warnings", ["Remediation requires more evidence."])[0]


def _failed_command(result: dict[str, Any]) -> str:
    command = result.get("command")
    if isinstance(command, list):
        return " ".join(command)
    return str(command or result.get("name") or "validation command")


def _prefixed(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items]


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _unique(items) -> list[str]:
    seen = set()
    return [item for item in items if item and not (item in seen or seen.add(item))]
