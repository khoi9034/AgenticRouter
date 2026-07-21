from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from .autogate import complete_run, get_run, start_run
from .diff_review import review_diff
from .observability import sanitize_text

GIT_TIMEOUT_SECONDS = 8
VALIDATION_TIMEOUT_SECONDS = 30
STATIC_EXTENSIONS = {".css", ".html", ".htm", ".md", ".txt"}
JS_EXTENSIONS = {".js", ".mjs", ".cjs"}
PY_EXTENSIONS = {".py"}
PHP_EXTENSIONS = {".php"}


def collect_git_evidence(repo_path: str | Path = ".") -> dict[str, Any]:
    root = Path(repo_path)
    commands = {
        "status": ["git", "status", "--short"],
        "unstaged_names": ["git", "diff", "--name-only"],
        "unstaged_diff": ["git", "diff"],
        "staged_names": ["git", "diff", "--cached", "--name-only"],
        "staged_diff": ["git", "diff", "--cached"],
    }
    results = {name: run_command(command, root, timeout=GIT_TIMEOUT_SECONDS, allow_git=True) for name, command in commands.items()}
    warnings = []
    for name, result in results.items():
        if result["status"] not in {"passed", "failed"} or result["exit_code"]:
            warnings.append(f"{name} unavailable: {result['status']}")
    staged = _lines(results["staged_names"]["_stdout_raw"])
    unstaged = _lines(results["unstaged_names"]["_stdout_raw"])
    status_files = _status_files(results["status"]["_stdout_raw"])
    git_diff = "\n".join(part for part in [results["unstaged_diff"]["_stdout_raw"], results["staged_diff"]["_stdout_raw"]] if part.strip())
    return {
        "changed_files": _unique([*unstaged, *staged, *status_files]),
        "staged_files": staged,
        "unstaged_files": _unique([*unstaged, *[item for item in status_files if item not in staged]]),
        "git_diff": git_diff,
        "git_status_summary": sanitize_text(results["status"]["stdout"], 1000),
        "commands": {name: _public_command_result(result) for name, result in results.items()},
        "warnings": _unique(warnings),
    }


def build_validation_plan_for_run(run_id: str, repo_path: str | Path = ".") -> dict[str, Any]:
    record = get_run(run_id)
    if not record:
        raise ValueError(f"unknown run_id: {run_id}")
    git = collect_git_evidence(repo_path)
    return build_validation_plan(record, repo_path, git["changed_files"])


def build_validation_plan(record: dict[str, Any], repo_path: str | Path = ".", changed_files: list[str] | None = None) -> dict[str, Any]:
    root = Path(repo_path)
    files = [_clean_path(path) for path in (changed_files or record.get("files_touched") or [])]
    project_types = detect_project_types(root, files)
    high = record.get("risk_level") == "high"
    medium = record.get("risk_level") == "medium"
    requires_validation = bool(high or medium or _code_files(files))
    commands: list[dict[str, Any]] = []

    py_files = [path for path in files if Path(path).suffix.casefold() in PY_EXTENSIONS and _exists(root, path)]
    if "python" in project_types and (root / "tests").is_dir():
        commands.append(_command("python_unittest", ["python", "-m", "unittest", "discover", "-s", "tests"], required=high))
    if py_files:
        commands.append(_command("python_compile", ["python", "-m", "py_compile", *py_files], required=high))

    scripts = _npm_scripts(root)
    if "npm" in project_types:
        for script in ["test", "lint", "typecheck", "build"]:
            if script in scripts:
                command = ["npm", "test"] if script == "test" else ["npm", "run", script]
                commands.append(_command(f"npm_{script}", command, required=high and script == "test"))

    js_files = [path for path in files if Path(path).suffix.casefold() in JS_EXTENSIONS and _exists(root, path)]
    commands.extend(_command(f"node_check_{Path(path).name}", ["node", "--check", path], required=False) for path in js_files)

    php_files = [path for path in files if Path(path).suffix.casefold() in PHP_EXTENSIONS and _exists(root, path)]
    commands.extend(_command(f"php_lint_{Path(path).name}", ["php", "-l", path], required=high) for path in php_files)

    if "dotnet" in project_types:
        commands.append(_command("dotnet_test", ["dotnet", "test"], required=high))

    notes = _plan_notes(record, files, project_types, commands, requires_validation)
    return {
        "run_id": record.get("run_id"),
        "project_types": project_types,
        "changed_files": files,
        "commands": commands,
        "requires_validation": requires_validation,
        "static_only": _static_only(files),
        "notes": notes,
        "warnings": [] if commands or not requires_validation else ["No safe validation command was detected for this risk level."],
    }


def detect_project_types(repo_path: str | Path = ".", changed_files: list[str] | None = None) -> list[str]:
    root = Path(repo_path)
    files = [_clean_path(path) for path in (changed_files or [])]
    types = []
    if any((root / name).exists() for name in ["pyproject.toml", "requirements.txt", "setup.py"]) or any(Path(path).suffix.casefold() == ".py" for path in files):
        types.append("python")
    if (root / "package.json").exists():
        types.append("npm")
    if (root / "composer.json").exists() or any(Path(path).suffix.casefold() == ".php" for path in files):
        types.append("php")
    if any(root.glob("*.csproj")) or any(Path(path).suffix.casefold() == ".csproj" for path in files):
        types.append("dotnet")
    if files and _static_only(files):
        types.append("static")
    return _unique(types)


def run_validation_plan(plan: dict[str, Any], repo_path: str | Path = ".") -> list[dict[str, Any]]:
    return [
        _public_command_result(run_command(item["command"], repo_path, timeout=VALIDATION_TIMEOUT_SECONDS, name=item["name"]))
        for item in plan.get("commands", [])
    ]


def collect_evidence(run_id: str, repo_path: str | Path = ".") -> dict[str, Any]:
    record = get_run(run_id)
    if not record:
        raise ValueError(f"unknown run_id: {run_id}")
    git = collect_git_evidence(repo_path)
    plan = build_validation_plan(record, repo_path, git["changed_files"])
    results = run_validation_plan(plan, repo_path)
    diff = review_diff(
        project_name=record["project_name"],
        task_description=record["task_summary"],
        run_contract=record["run_contract"],
        changed_files=git["changed_files"],
        git_diff=git["git_diff"],
        tests_run=[item["name"] for item in results if item["status"] == "passed"],
        live_prod=record.get("live_prod", False),
    )
    tests_status = _tests_status(plan, results)
    missing = _missing_evidence(record, git, plan, tests_status)
    return {
        "evidence_id": f"evidence_{uuid.uuid4().hex[:12]}",
        "run_id": run_id,
        "changed_files": git["changed_files"],
        "staged_files": git["staged_files"],
        "unstaged_files": git["unstaged_files"],
        "git_status_summary": git["git_status_summary"],
        "diff_summary": _diff_summary(git["git_diff"]),
        "diff_line_count": len(git["git_diff"].splitlines()),
        "validation_plan": plan,
        "validation_results": results,
        "tests_status": tests_status,
        "rollback_plan_detected": _rollback_detected(git["git_diff"], git["changed_files"]),
        "diff_review": diff,
        "evidence_complete": not missing,
        "missing_evidence": missing,
        "warnings": _unique([*git["warnings"], *plan["warnings"], *_result_warnings(results)]),
        "_git_diff": git["git_diff"],
    }


def complete_run_with_evidence(run_id: str, repo_path: str | Path = ".") -> dict[str, Any]:
    evidence = collect_evidence(run_id, repo_path)
    complete_status = evidence["tests_status"] if evidence["tests_status"] in {"passed", "failed"} else "not_run"
    completed = complete_run(
        run_id=run_id,
        changed_files=evidence["changed_files"],
        git_diff=evidence["_git_diff"],
        tests_run=[item["name"] for item in evidence["validation_results"] if item["status"] in {"passed", "failed", "timed_out"}],
        test_status=complete_status,
        rollback_plan_present=evidence["rollback_plan_detected"],
        notes=f"Automated evidence runner: {evidence['tests_status']}",
    )
    public_evidence = {key: value for key, value in evidence.items() if not key.startswith("_")}
    return {
        "evidence": public_evidence,
        "autogate": completed,
        "final_decision": completed["final_decision"],
    }


def evidence_current(project_name: str, task_description: str, repo_path: str | Path = ".", live_prod: bool | None = None) -> dict[str, Any]:
    git = collect_git_evidence(repo_path)
    run = start_run(project_name, task_description, files_touched=git["changed_files"], live_prod=live_prod)
    return complete_run_with_evidence(run["run_id"], repo_path)


def run_command(
    command: list[str],
    repo_path: str | Path = ".",
    timeout: int = VALIDATION_TIMEOUT_SECONDS,
    name: str | None = None,
    allow_git: bool = False,
) -> dict[str, Any]:
    if not (allow_git and _is_allowed_git_command(command)) and not is_safe_validation_command(command):
        return _command_result(name, command, "skipped", None, "", "Command is not allowlisted.")
    if shutil.which(command[0]) is None:
        return _command_result(name, command, "unavailable", None, "", f"{command[0]} is not available.")
    try:
        completed = subprocess.run(
            command,
            cwd=Path(repo_path),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        return _command_result(name, command, "timed_out", None, exc.stdout or "", exc.stderr or "Command timed out.")
    except OSError as exc:
        return _command_result(name, command, "unavailable", None, "", str(exc))
    return _command_result(
        name,
        command,
        "passed" if completed.returncode == 0 else "failed",
        completed.returncode,
        completed.stdout,
        completed.stderr,
    )


def is_safe_validation_command(command: list[str]) -> bool:
    if not command or any(not isinstance(part, str) or not part.strip() for part in command):
        return False
    folded = [part.casefold() for part in command]
    if folded[:5] == ["python", "-m", "unittest", "discover", "-s"] and len(command) == 6:
        return True
    if folded[:3] == ["python", "-m", "py_compile"] and len(command) >= 4:
        return all(not part.startswith("-") and Path(part).suffix.casefold() == ".py" for part in command[3:])
    if folded == ["npm", "test"]:
        return True
    if len(folded) == 3 and folded[:2] == ["npm", "run"] and folded[2] in {"test", "lint", "typecheck", "build"}:
        return True
    if len(folded) == 3 and folded[:2] == ["node", "--check"] and Path(command[2]).suffix.casefold() in JS_EXTENSIONS:
        return True
    if len(folded) == 3 and folded[:2] == ["php", "-l"] and Path(command[2]).suffix.casefold() == ".php":
        return True
    if folded == ["dotnet", "test"]:
        return True
    return False


def format_evidence_plan(plan: dict[str, Any]) -> str:
    commands = plan.get("commands", [])
    lines = [
        f"Run ID: {plan.get('run_id') or 'current'}",
        f"Project types: {', '.join(plan['project_types']) or 'unknown'}",
        f"Static only: {plan['static_only']}",
        f"Requires validation: {plan['requires_validation']}",
        "Commands:",
        *[f"- {item['name']}: {' '.join(item['command'])} ({'required' if item['required'] else 'optional'})" for item in commands],
    ]
    if not commands:
        lines.append("- none")
    return "\n".join(lines)


def format_evidence(result: dict[str, Any]) -> str:
    evidence = result.get("evidence", result)
    lines = [
        f"Evidence ID: {evidence['evidence_id']}",
        f"Run ID: {evidence['run_id']}",
        f"Changed files: {', '.join(evidence['changed_files']) or 'none'}",
        f"Tests status: {evidence['tests_status']}",
        f"Evidence complete: {evidence['evidence_complete']}",
        "Validation results:",
        *[
            f"- {item['name']}: {item['status']} ({item.get('exit_code') if item.get('exit_code') is not None else 'n/a'})"
            for item in evidence["validation_results"]
        ],
    ]
    if not evidence["validation_results"]:
        lines.append("- none")
    if "autogate" in result:
        lines += [
            f"Final decision: {result['autogate']['final_decision']}",
            f"Reason: {result['autogate']['approval_gate_reason']}",
        ]
    return "\n".join(lines)


def public_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in evidence.items() if not key.startswith("_")}


def _is_allowed_git_command(command: list[str]) -> bool:
    return command in [
        ["git", "status", "--short"],
        ["git", "diff", "--name-only"],
        ["git", "diff"],
        ["git", "diff", "--cached", "--name-only"],
        ["git", "diff", "--cached"],
    ]


def _command(name: str, command: list[str], required: bool) -> dict[str, Any]:
    return {"name": name, "command": command, "required": required, "timeout_seconds": VALIDATION_TIMEOUT_SECONDS}


def _command_result(name: str | None, command: list[str], status: str, exit_code: int | None, stdout: str, stderr: str) -> dict[str, Any]:
    return {
        "name": name or "_".join(command[:3]),
        "command": command,
        "status": status,
        "exit_code": exit_code,
        "stdout": sanitize_text(stdout, 1200),
        "stderr": sanitize_text(stderr, 1200),
        "_stdout_raw": stdout,
        "_stderr_raw": stderr,
    }


def _public_command_result(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if not key.startswith("_")}


def _tests_status(plan: dict[str, Any], results: list[dict[str, Any]]) -> str:
    if any(item["status"] in {"failed", "timed_out"} for item in results):
        return "failed"
    if results and all(item["status"] == "passed" for item in results):
        return "passed"
    required = [item for item in plan.get("commands", []) if item.get("required")]
    if required and not any(result["status"] == "passed" for result in results):
        return "unavailable"
    if plan.get("requires_validation") and not results:
        return "unavailable"
    return "not_run"


def _missing_evidence(record: dict[str, Any], git: dict[str, Any], plan: dict[str, Any], tests_status: str) -> list[str]:
    missing = []
    if not git["changed_files"]:
        missing.append("changed_files")
    if record.get("risk_level") in {"medium", "high"} and not git["git_diff"].strip():
        missing.append("git_diff")
    if plan["requires_validation"] and tests_status in {"not_run", "unavailable"} and not plan["static_only"]:
        missing.append("validation_results")
    return missing


def _result_warnings(results: list[dict[str, Any]]) -> list[str]:
    return [f"{item['name']} {item['status']}: {item['stderr']}" for item in results if item["status"] in {"failed", "unavailable", "timed_out", "skipped"}]


def _status_files(status: str) -> list[str]:
    files = []
    for line in status.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append(path)
    return files


def _npm_scripts(root: Path) -> set[str]:
    package = root / "package.json"
    if not package.exists():
        return set()
    try:
        data = json.loads(package.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return set((data.get("scripts") or {}).keys())


def _plan_notes(record: dict[str, Any], files: list[str], project_types: list[str], commands: list[dict[str, Any]], required: bool) -> list[str]:
    notes = []
    if _static_only(files):
        notes.append("Static/docs-only changes use diff and scope checks; heavy test commands are not required.")
    if required and not commands:
        notes.append("No safe local validation command was detected; AutoGate should request more evidence.")
    if record.get("live_prod"):
        notes.append("Live/prod runs still require rollback evidence.")
    if "npm" in project_types:
        notes.append("Only existing npm scripts from package.json are allowed.")
    return notes


def _rollback_detected(diff: str, files: list[str]) -> bool:
    text = f"{diff}\n{' '.join(files)}".casefold()
    return any(term in text for term in ["rollback", "backup", "restore"])


def _diff_summary(diff: str) -> str:
    lines = []
    for line in diff.splitlines():
        if line.startswith(("+++", "---", "diff --git", "@@")):
            continue
        if line.startswith(("+", "-")):
            lines.append(line[1:])
    return sanitize_text(" ".join(lines), 1200)


def _lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _exists(root: Path, path: str) -> bool:
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return False
    return candidate.exists()


def _clean_path(path: str) -> str:
    return str(path).strip().replace("\\", "/")


def _static_only(files: list[str]) -> bool:
    return bool(files) and all(Path(path).suffix.casefold() in STATIC_EXTENSIONS for path in files)


def _code_files(files: list[str]) -> bool:
    return any(Path(path).suffix.casefold() in PY_EXTENSIONS | JS_EXTENSIONS | PHP_EXTENSIONS | {".cs", ".sql"} for path in files)


def _unique(items) -> list[str]:
    seen = set()
    return [item for item in items if item and not (item in seen or seen.add(item))]
