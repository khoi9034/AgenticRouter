from __future__ import annotations

import json
import re
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

from .contracts import check_contract
from .models import DATA_DIR
from .observability import sanitize_text

RISK_ORDER = {"low": 0, "medium": 1, "high": 2}
DECISION_ORDER = {"pass": 0, "warn": 1, "fail": 2}
DEPENDENCY_FILES = {"requirements.txt", "pyproject.toml", "package.json", "package-lock.json", "Pipfile", "poetry.lock"}
CONFIG_DEPLOY_PATTERNS = [
    r"(^|/)\.env$",
    r"(^|/)config",
    r"(^|/)deploy",
    r"(^|/)deployment",
    r"^Dockerfile$",
    r"docker-compose.*\.ya?ml$",
    r"^\.github/workflows/",
]


@lru_cache(maxsize=1)
def load_diff_rules() -> dict[str, Any]:
    with (DATA_DIR / "diff_risk_rules.json").open(encoding="utf-8") as f:
        return json.load(f)


def review_diff(
    project_name: str,
    task_description: str,
    run_contract: dict[str, Any] | None = None,
    changed_files: list[str] | None = None,
    git_diff: str = "",
    added_dependencies: list[str] | None = None,
    tests_run: list[str] | None = None,
    live_prod: bool | None = None,
) -> dict[str, Any]:
    files = _unique([*(changed_files or []), *_files_from_diff(git_diff)])
    added, removed = _diff_lines(git_diff)
    text = "\n".join([*added, *removed])
    rules = load_diff_rules()
    detected: list[str] = []
    violations: list[str] = []
    warnings: list[str] = []
    followups: list[str] = []
    decision = "pass"
    risk = "low"
    rollback = False

    scope = None
    if run_contract:
        scope = check_contract(run_contract, files, _short_diff_summary(git_diff), added_dependencies)
        decision = _max_decision(decision, scope["decision"])
        risk = _max_risk(risk, scope["risk_level"])
        violations.extend(scope["violations"])
        warnings.extend(scope["warnings"])

    safe_surface_change = _safe_ui_or_docs(files, text)
    for rule in rules["rules"]:
        if rule["name"] == "auth_session_change" and (safe_surface_change or _sql_only(files)):
            continue
        hits = _hits(rule, text, added, removed, files)
        if not hits:
            continue
        detected.append(rule["name"])
        risk = _max_risk(risk, rule["risk_level"])
        decision = _max_decision(decision, rule["decision"])
        target = violations if rule["decision"] == "fail" else warnings
        target.append(f"{rule['label']}: {', '.join(hits[:3])}")
        followups.extend(rule.get("required_followup_checks", []))
        rollback = rollback or rule.get("rollback_required", False)

    if live_prod:
        risk = _max_risk(risk, "high")
        decision = _max_decision(decision, "warn")
        warnings.append("Live/prod review requires human approval before deployment.")
        followups.append("Confirm rollback plan and deployment approval.")
        rollback = True

    if _has_dependency_change(files, added_dependencies):
        risk = _max_risk(risk, "medium")
        decision = _max_decision(decision, "warn")
        detected.append("dependency_config_deploy")
        warnings.append("Dependency/config/deploy file changed.")
        followups.append("Verify dependency/config/deploy impact and lockfile consistency.")

    if not detected and safe_surface_change:
        detected.append("ui_docs_safe")
        followups.append("Check rendered UI/docs and confirm no unrelated files changed.")
    elif not detected and not git_diff.strip():
        warnings.append("No git diff content supplied.")

    required_followup = _unique([*followups, *("Run or document relevant tests before approval." for _ in [0] if decision != "pass" and not tests_run)])
    human_review = bool((run_contract or {}).get("human_review_required") or risk == "high" or decision == "fail" or live_prod)
    return {
        "decision": decision,
        "risk_level": risk,
        "human_review_required": human_review,
        "summary": _summary(decision, risk, detected, scope),
        "detected_change_types": _unique(detected),
        "violations": _unique(violations),
        "warnings": _unique(warnings),
        "required_followup_checks": required_followup,
        "rollback_required": rollback,
        "approval_recommendation": _approval(decision, human_review),
        "reasoning": _reasoning(decision, risk, detected, scope),
    }


def review_current_diff(
    project_name: str,
    task_description: str,
    run_contract: dict[str, Any] | None = None,
    added_dependencies: list[str] | None = None,
    tests_run: list[str] | None = None,
    live_prod: bool | None = None,
    cwd: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(cwd or Path.cwd())
    diff = subprocess.run(["git", "diff", "--no-ext-diff"], cwd=root, text=True, capture_output=True, check=False)
    names = subprocess.run(["git", "diff", "--name-only"], cwd=root, text=True, capture_output=True, check=False)
    if diff.returncode or names.returncode:
        raise ValueError((diff.stderr or names.stderr or "git diff failed").strip())
    return review_diff(
        project_name=project_name,
        task_description=task_description,
        run_contract=run_contract,
        changed_files=[line.strip() for line in names.stdout.splitlines() if line.strip()],
        git_diff=diff.stdout,
        added_dependencies=added_dependencies,
        tests_run=tests_run,
        live_prod=live_prod,
    )


def format_diff_review(result: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Decision: {result['decision']}",
            f"Risk: {result['risk_level']}",
            f"Human review required: {'yes' if result['human_review_required'] else 'no'}",
            f"Summary: {result['summary']}",
            "Detected changes:\n" + _bullets(result["detected_change_types"] or ["none"]),
            "Violations:\n" + _bullets(result["violations"] or ["none"]),
            "Warnings:\n" + _bullets(result["warnings"] or ["none"]),
            "Follow-up checks:\n" + _bullets(result["required_followup_checks"] or ["none"]),
            f"Approval: {result['approval_recommendation']}",
        ]
    )


def _hits(rule: dict[str, Any], text: str, added: list[str], removed: list[str], files: list[str]) -> list[str]:
    haystacks = {
        "added": "\n".join(added),
        "removed": "\n".join(removed),
        "all": text,
        "files": "\n".join(files),
    }
    value = haystacks[rule.get("scope", "all")].casefold()
    hits = [pattern for pattern in rule["patterns"] if re.search(pattern, value, re.I)]
    return [sanitize_text(hit, 80) for hit in hits]


def _diff_lines(diff: str) -> tuple[list[str], list[str]]:
    added = []
    removed = []
    for line in diff.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added.append(line[1:])
        elif line.startswith("-"):
            removed.append(line[1:])
    return added, removed


def _files_from_diff(diff: str) -> list[str]:
    files = []
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                files.append(parts[3][2:] if parts[3].startswith("b/") else parts[3])
        elif line.startswith("+++ b/"):
            files.append(line[6:])
    return _unique(files)


def _safe_ui_or_docs(files: list[str], text: str) -> bool:
    safe_ext = {".css", ".html", ".md", ".txt"}
    return bool(files) and all(Path(path).suffix.casefold() in safe_ext for path in files) and not re.search(
        r"fetch|axios|form action|require_auth|password|token|secret|sql|delete|drop|insert|update", text, re.I
    )


def _sql_only(files: list[str]) -> bool:
    return bool(files) and all(Path(path).suffix.casefold() == ".sql" for path in files)


def _has_dependency_change(files: list[str], added_dependencies: list[str] | None) -> bool:
    names = {Path(path).name for path in files}
    if names & DEPENDENCY_FILES or added_dependencies:
        return True
    return any(re.search(pattern, path.replace("\\", "/"), re.I) for path in files for pattern in CONFIG_DEPLOY_PATTERNS)


def _short_diff_summary(diff: str) -> str:
    added, removed = _diff_lines(diff)
    return sanitize_text(" ".join([*added[:12], *removed[:12]]), 500)


def _summary(decision: str, risk: str, detected: list[str], scope: dict[str, Any] | None) -> str:
    base = f"Diff review {decision} with {risk} risk."
    if scope:
        base += f" Scope Guard was {scope['decision']}."
    if detected:
        base += " Detected: " + ", ".join(_unique(detected)[:5]) + "."
    return base


def _approval(decision: str, human_review: bool) -> str:
    if decision == "fail":
        return "block_until_fixed"
    if human_review:
        return "human_review_before_approval"
    if decision == "warn":
        return "approve_only_after_followup_checks"
    return "approve"


def _reasoning(decision: str, risk: str, detected: list[str], scope: dict[str, Any] | None) -> str:
    pieces = [f"Decision uses max severity across scope and diff rules: {decision}/{risk}."]
    if scope:
        pieces.append(f"Scope Guard result: {scope['decision']}.")
    if detected:
        pieces.append("Matched diff rules: " + ", ".join(_unique(detected)) + ".")
    return " ".join(pieces)


def _max_risk(left: str, right: str) -> str:
    return left if RISK_ORDER.get(left, 0) >= RISK_ORDER.get(right, 0) else right


def _max_decision(left: str, right: str) -> str:
    return left if DECISION_ORDER[left] >= DECISION_ORDER[right] else right


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _unique(items) -> list[str]:
    seen = set()
    return [item for item in items if item and not (item in seen or seen.add(item))]
