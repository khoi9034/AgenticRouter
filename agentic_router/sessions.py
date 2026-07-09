from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import DATA_DIR
from .outcomes import task_category
from .rules import RISK_ORDER


def session_cache_path() -> Path:
    return Path(os.environ.get("AGENTIC_ROUTER_SESSIONS", DATA_DIR / "session_cache.jsonl"))


def load_session_records(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or session_cache_path()
    if not target.exists():
        return []
    with target.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def latest_session(session_id: str, path: Path | None = None) -> dict[str, Any] | None:
    # ponytail: linear JSONL scan is fine for a local MVP; switch to SQLite if this becomes a real shared service.
    for record in reversed(load_session_records(path)):
        if record.get("session_id") == session_id:
            return record
    return None


def can_reuse_session(
    previous: dict[str, Any] | None,
    project_name: str,
    risk_level: str,
    safety_locked: bool,
    previous_failure_count: int,
) -> bool:
    return bool(
        previous
        and previous.get("project_name") == project_name
        and _risk_rank(risk_level) <= _risk_rank(str(previous.get("risk_level", "low")))
        and not (safety_locked and not previous.get("safety_locked"))
        and previous_failure_count < 2
    )


def save_session_route(
    session_id: str,
    project_name: str,
    task_description: str,
    files_touched: list[str],
    result: dict[str, Any],
    safety_locked: bool,
    path: Path | None = None,
) -> dict[str, Any]:
    record = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "session_id": session_id,
        "project_name": project_name,
        "task_category": task_category(task_description, files_touched),
        "task_hash": hashlib.sha256(task_description.encode("utf-8")).hexdigest()[:16],
        "task_summary": "[redacted-sensitive-task]" if safety_locked else _summary(task_description),
        "risk_level": result["risk_level"],
        "model_tier": result["model_tier"],
        "selected_model_alias": result["selected_model_alias"],
        "selected_model": result["selected_model"],
        "sticky_route_used": result["sticky_route_used"],
        "escalation_due_to_failures": "previous_failures_escalate" in result["matched_rules"],
        "safety_locked": safety_locked,
    }
    target = path or session_cache_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def summarize_sessions(records: list[dict[str, Any]] | None = None, path: Path | None = None) -> dict[str, Any]:
    records = load_session_records(path) if records is None else records
    return {
        "total_sessions": len({item["session_id"] for item in records}),
        "sticky_routes_used": sum(1 for item in records if item.get("sticky_route_used")),
        "escalations_due_to_failures": sum(1 for item in records if item.get("escalation_due_to_failures")),
        "sessions_by_project": dict(Counter(item["project_name"] for item in records)),
        "most_common_selected_aliases": Counter(item["selected_model_alias"] for item in records).most_common(5),
    }


def format_session_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Total sessions: {summary['total_sessions']}",
            f"Sticky routes used: {summary['sticky_routes_used']}",
            f"Escalations due to failures: {summary['escalations_due_to_failures']}",
            f"Sessions by project: {json.dumps(summary['sessions_by_project'], sort_keys=True)}",
            f"Most common selected aliases: {json.dumps(summary['most_common_selected_aliases'])}",
        ]
    )


def _risk_rank(risk: str) -> int:
    return RISK_ORDER.index(risk) if risk in RISK_ORDER else 0


def _summary(task_description: str) -> str:
    text = " ".join(task_description.split())
    return text[:80]
