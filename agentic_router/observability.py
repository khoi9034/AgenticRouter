from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import DATA_DIR
from .outcomes import task_category

EXPORT_DIR = DATA_DIR.parent / "exports" / "langsmith"
TRACE_COLUMNS = [
    "route_id",
    "timestamp",
    "project_name",
    "task_class",
    "risk_level",
    "model_tier",
    "selected_model_alias",
    "selected_model",
    "profile_name",
    "cost_quality_tradeoff",
    "context_size",
    "human_review_required",
    "sticky_route_used",
    "fallback_candidates",
    "matched_rules",
    "prompt_body_logged",
    "task_summary",
    "task_description_hash",
    "sanitized_task_category",
]
GOLDEN_COLUMNS = [
    "project_name",
    "task_description",
    "files_touched",
    "previous_failure_count",
    "expected_tier",
    "expected_risk",
    "expected_human_review_required",
    "expected_reason_keywords",
]
SENSITIVE_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[redacted-email]"),
    (re.compile(r"\b[A-Za-z]:\\[^\s,;\"']+"), "[redacted-windows-path]"),
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "[redacted-tenant-id]"),
    (re.compile(r"\b(bearer\s+)?(api[-_ ]?key|token|password|secret|credential)\b\s*[:=]?\s*[\w.\-]+", re.I), "[redacted-secret]"),
    (re.compile(r"\b(usb\s*)?serial(?:\s*(?:number|#|:|=))?\s+[\w-]{4,}\b", re.I), "[redacted-serial]"),
]
PRIVACY_DOMAIN_TERMS = {
    "veteran",
    "workers comp",
    "claim",
    "legal",
    "client record",
    "student",
    "raw comment",
    "production log",
    "tenant",
    "usb serial",
}


def traces_path() -> Path:
    return Path(os.environ.get("AGENTIC_ROUTER_TRACES", DATA_DIR / "traces.jsonl"))


def write_trace(
    project_name: str,
    task_description: str,
    files_touched: list[str],
    result: dict[str, Any],
    path: Path | None = None,
) -> dict[str, Any]:
    task_class = task_category(task_description, files_touched)
    high_risk = _high_risk(project_name, task_description, result)
    trace = {
        "route_id": result["route_id"],
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project_name": project_name,
        "task_class": task_class,
        "risk_level": result["risk_level"],
        "model_tier": result["model_tier"],
        "selected_model_alias": result["selected_model_alias"],
        "selected_model": result["selected_model"],
        "profile_name": result["profile_name"],
        "cost_quality_tradeoff": result["cost_quality_tradeoff"],
        "context_size": result.get("context_pack", {}).get("context_size"),
        "human_review_required": result["human_review_required"],
        "sticky_route_used": result["sticky_route_used"],
        "fallback_candidates": result["fallback_candidates"],
        "matched_rules": result["matched_rules"],
        "prompt_body_logged": not high_risk,
    }
    if high_risk:
        trace["task_description_hash"] = hashlib.sha256(task_description.encode("utf-8")).hexdigest()[:16]
        trace["sanitized_task_category"] = task_class
    else:
        trace["task_summary"] = sanitize_text(task_description, 180)

    target = path or traces_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(trace, sort_keys=True) + "\n")
    return trace


def load_traces(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or traces_path()
    if not target.exists():
        return []
    with target.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def summarize_traces(records: list[dict[str, Any]] | None = None, path: Path | None = None) -> dict[str, Any]:
    records = load_traces(path) if records is None else records
    return {
        "total_traces": len(records),
        "traces_by_risk": dict(Counter(item.get("risk_level") for item in records)),
        "traces_by_selected_model_alias": dict(Counter(item.get("selected_model_alias") for item in records)),
        "traces_by_profile": dict(Counter(item.get("profile_name") for item in records)),
        "human_review_count": sum(1 for item in records if item.get("human_review_required")),
        "sticky_route_count": sum(1 for item in records if item.get("sticky_route_used")),
        "high_risk_redacted_count": sum(1 for item in records if item.get("prompt_body_logged") is False),
        "last_route_id": records[-1]["route_id"] if records else None,
    }


def observability_status() -> dict[str, Any]:
    return {
        "local_tracing_enabled": True,
        "remote_tracing_enabled": False,
        "langsmith_api_enabled": False,
        "langsmith_api_disabled_by_design": True,
        "traces_file_path": str(traces_path()),
        "export_folder_path": str(EXPORT_DIR),
    }


def export_langsmith_files(
    output_dir: Path | None = None,
    traces: list[dict[str, Any]] | None = None,
    golden_tasks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from .evaluator import load_golden_tasks

    folder = output_dir or EXPORT_DIR
    folder.mkdir(parents=True, exist_ok=True)
    traces = load_traces() if traces is None else traces
    golden_tasks = load_golden_tasks() if golden_tasks is None else golden_tasks

    golden_rows = [_golden_row(item) for item in golden_tasks]
    trace_rows = [_csv_row(item, TRACE_COLUMNS) for item in traces]
    files = {
        "golden_jsonl": folder / "golden_tasks_dataset.jsonl",
        "golden_csv": folder / "golden_tasks_dataset.csv",
        "traces_jsonl": folder / "router_traces_example.jsonl",
        "traces_csv": folder / "router_traces_example.csv",
        "readme": folder / "README.md",
    }
    _write_jsonl(files["golden_jsonl"], [_golden_jsonl(item) for item in golden_tasks])
    _write_csv(files["golden_csv"], GOLDEN_COLUMNS, golden_rows)
    _write_jsonl(files["traces_jsonl"], traces)
    _write_csv(files["traces_csv"], TRACE_COLUMNS, trace_rows)
    files["readme"].write_text(_export_readme(), encoding="utf-8")
    return {"export_folder": str(folder), "files": {key: str(value) for key, value in files.items()}}


def export_file_list(folder: Path | None = None) -> list[dict[str, str]]:
    root = folder or EXPORT_DIR
    if not root.exists():
        return []
    repo_root = DATA_DIR.parent
    return [
        {"name": path.name, "relative_path": path.relative_to(repo_root).as_posix()}
        for path in sorted(root.iterdir())
        if path.is_file()
    ]


def format_traces_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Total traces: {summary['total_traces']}",
            f"Traces by risk: {json.dumps(summary['traces_by_risk'], sort_keys=True)}",
            f"Traces by selected model alias: {json.dumps(summary['traces_by_selected_model_alias'], sort_keys=True)}",
            f"Traces by profile: {json.dumps(summary['traces_by_profile'], sort_keys=True)}",
            f"Human review count: {summary['human_review_count']}",
            f"Sticky route count: {summary['sticky_route_count']}",
            f"High-risk redacted count: {summary['high_risk_redacted_count']}",
            f"Last route ID: {summary['last_route_id'] or 'none'}",
        ]
    )


def format_observability_status(status: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Local tracing enabled: {status['local_tracing_enabled']}",
            f"Remote tracing enabled: {status['remote_tracing_enabled']}",
            f"LangSmith API enabled: {status['langsmith_api_enabled']}",
            "LangSmith API disabled by design: true",
            f"Traces file path: {status['traces_file_path']}",
            f"Export folder path: {status['export_folder_path']}",
        ]
    )


def sanitize_text(value: str, limit: int = 180) -> str:
    text = " ".join(str(value).split())
    for pattern, replacement in SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text[:limit]


def _high_risk(project_name: str, task_description: str, result: dict[str, Any]) -> bool:
    text = f"{project_name} {task_description}".casefold()
    return (
        result.get("risk_level") not in {"low", "medium"}
        or bool(result.get("human_review_required"))
        or result.get("model_tier") == "advanced"
        or any(term in text for term in PRIVACY_DOMAIN_TERMS)
    )


def _golden_jsonl(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "inputs": {
            "project_name": task["project_name"],
            "task_description": sanitize_text(task["task_description"], 180),
            "files_touched": task.get("files_touched", []),
            "previous_failure_count": task.get("previous_failure_count", 0),
        },
        "outputs": {
            "expected_tier": task["expected_tier"],
            "expected_risk": task["expected_risk"],
            "expected_human_review_required": task["expected_human_review_required"],
            "expected_reason_keywords": task.get("expected_reason_keywords", []),
        },
        "metadata": {"source": "AgenticRouter local golden tasks"},
    }


def _golden_row(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "project_name": task["project_name"],
        "task_description": sanitize_text(task["task_description"], 180),
        "files_touched": json.dumps(task.get("files_touched", [])),
        "previous_failure_count": task.get("previous_failure_count", 0),
        "expected_tier": task["expected_tier"],
        "expected_risk": task["expected_risk"],
        "expected_human_review_required": task["expected_human_review_required"],
        "expected_reason_keywords": json.dumps(task.get("expected_reason_keywords", [])),
    }


def _csv_row(row: dict[str, Any], columns: list[str]) -> dict[str, Any]:
    return {column: _cell(row.get(column)) for column in columns}


def _cell(value: Any) -> Any:
    return json.dumps(value) if isinstance(value, (list, dict)) else value


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _export_readme() -> str:
    return """# AgenticRouter LangSmith App Files

These files are local, manual export artifacts for inspection or later import through a UI.

They are not API uploads. AgenticRouter does not use the LangSmith API, does not require an API key, does not import `langsmith`, and does not send remote traces.

Files:

- `golden_tasks_dataset.jsonl`: Golden routing tasks with expected outputs.
- `golden_tasks_dataset.csv`: Spreadsheet-friendly golden task export.
- `router_traces_example.jsonl`: Sanitized local router traces.
- `router_traces_example.csv`: Spreadsheet-friendly trace export.

Do not add secrets, tokens, private paths, PII, records, emails, tenant IDs, USB serials, production logs, or real case data to these files.
"""
