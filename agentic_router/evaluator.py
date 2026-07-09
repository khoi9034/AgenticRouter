from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .models import DATA_DIR
from .router import route

RouteFn = Callable[..., dict[str, Any]]


def load_golden_tasks(path: Path | None = None) -> list[dict[str, Any]]:
    with (path or DATA_DIR / "golden_tasks.json").open(encoding="utf-8") as f:
        return json.load(f)["tasks"]


def evaluate_tasks(tasks: list[dict[str, Any]] | None = None, route_fn: RouteFn = route) -> dict[str, Any]:
    tasks = load_golden_tasks() if tasks is None else tasks
    failures = []

    for index, task in enumerate(tasks, 1):
        actual = route_fn(
            project_name=task["project_name"],
            task_description=task["task_description"],
            files_touched=task.get("files_touched", []),
            previous_failure_count=task.get("previous_failure_count", 0),
        )
        mismatches = _mismatches(task, actual)
        if mismatches:
            failures.append(
                {
                    "index": index,
                    "project_name": task["project_name"],
                    "task_description": task["task_description"],
                    "mismatches": mismatches,
                }
            )

    return {
        "total": len(tasks),
        "passed": len(tasks) - len(failures),
        "failed": len(failures),
        "failures": failures,
    }


def format_summary(summary: dict[str, Any]) -> str:
    lines = [f"Golden eval: {summary['passed']}/{summary['total']} passed"]
    if summary["failed"]:
        lines.append(f"Failed cases: {summary['failed']}")
    for failure in summary["failures"]:
        lines.append(f"\n[{failure['index']}] {failure['project_name']}: {failure['task_description']}")
        for mismatch in failure["mismatches"]:
            lines.append(f"  - {mismatch}")
    return "\n".join(lines)


def _mismatches(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    checks = [
        ("tier", expected["expected_tier"], actual["model_tier"]),
        ("risk", expected["expected_risk"], actual["risk_level"]),
        (
            "human_review_required",
            expected["expected_human_review_required"],
            actual["human_review_required"],
        ),
    ]
    mismatches = [
        f"{name}: expected {want!r}, got {got!r}"
        for name, want, got in checks
        if want != got
    ]

    haystack = " ".join(
        [
            actual.get("reason", ""),
            actual.get("context_policy", ""),
            actual.get("escalation_policy", ""),
            " ".join(actual.get("matched_rules", [])),
        ]
    ).casefold()
    for keyword in expected.get("expected_reason_keywords", []):
        if keyword.casefold() not in haystack:
            mismatches.append(f"missing reason keyword: {keyword!r}")

    return mismatches

