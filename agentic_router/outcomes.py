from __future__ import annotations

import base64
import json
import os
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import DATA_DIR

ROUTE_PREFIX = "ar_"
FIT_VALUES = {"too_cheap", "right", "overkill"}
SENSITIVE_NOTE_PATTERNS = [
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b[a-fA-F0-9]{32,}\b"),
    re.compile(r"\b(password|secret|credential|bearer|token|ssn|pii|phi|serial)\b", re.I),
]


def make_route_id(
    project_name: str,
    task_description: str,
    files_touched: list[str],
    result: dict[str, Any],
) -> str:
    metadata = {
        "id": uuid.uuid4().hex,
        "issued_at": _now(),
        "project_name": project_name,
        "task_category": task_category(task_description, files_touched),
        "recommended_tier": result["model_tier"],
        "recommended_model": result["recommended_model"],
        "escalation_reasons": _reason_names(result["matched_rules"]),
    }
    encoded = base64.urlsafe_b64encode(json.dumps(metadata, separators=(",", ":")).encode())
    return ROUTE_PREFIX + encoded.decode().rstrip("=")


def decode_route_id(route_id: str) -> dict[str, Any]:
    if not route_id.startswith(ROUTE_PREFIX):
        raise ValueError("route_id is invalid")
    raw = route_id[len(ROUTE_PREFIX) :]
    try:
        data = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError("route_id is invalid") from exc

    required = {"project_name", "task_category", "recommended_tier", "recommended_model"}
    if not required <= data.keys():
        raise ValueError("route_id is missing routing metadata")
    return data


def save_feedback(
    route_id: str,
    accepted: bool,
    task_succeeded: bool | None,
    actual_model: str,
    recommendation_fit: str,
    notes: str = "",
    path: Path | None = None,
) -> dict[str, Any]:
    metadata = decode_route_id(route_id)
    fit = _fit(recommendation_fit)
    if not isinstance(accepted, bool):
        raise ValueError("accepted must be true or false")
    if task_succeeded is not None and not isinstance(task_succeeded, bool):
        raise ValueError("task_succeeded must be true, false, or unknown")

    record = {
        "created_at": _now(),
        "route_id": route_id,
        "project_name": metadata["project_name"],
        "task_category": metadata["task_category"],
        "recommended_tier": metadata["recommended_tier"],
        "recommended_model": metadata["recommended_model"],
        "actual_model": _clean_text(actual_model, "actual_model", 80),
        "accepted": accepted,
        "task_succeeded": task_succeeded,
        "recommendation_fit": fit,
        "escalation_reasons": metadata.get("escalation_reasons", []),
        "notes": _clean_text(notes, "notes", 500, allow_blank=True),
    }

    target = path or outcomes_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def load_feedback(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or outcomes_path()
    if not target.exists():
        return []
    with target.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def summarize_outcomes(records: list[dict[str, Any]] | None = None, path: Path | None = None) -> dict[str, Any]:
    records = load_feedback(path) if records is None else records
    total = len(records)
    known_success = [item for item in records if item.get("task_succeeded") is not None]
    success = [item for item in records if item.get("task_succeeded") is True]
    failures = [item for item in records if item.get("task_succeeded") is False]

    return {
        "total_feedback_records": total,
        "acceptance_rate": _rate(sum(1 for item in records if item.get("accepted")), total),
        "task_success_rate": _rate(len(success), len(known_success)),
        "overkill_count": sum(1 for item in records if item.get("recommendation_fit") == "overkill"),
        "too_weak_count": sum(1 for item in records if item.get("recommendation_fit") == "too_cheap"),
        "success_by_recommended_tier": dict(Counter(item["recommended_tier"] for item in success)),
        "failure_by_project": dict(Counter(item["project_name"] for item in failures)),
        "most_common_escalation_reasons": Counter(
            reason for item in records for reason in item.get("escalation_reasons", [])
        ).most_common(5),
    }


def format_outcomes_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Total feedback records: {summary['total_feedback_records']}",
            f"Acceptance rate: {_percent(summary['acceptance_rate'])}",
            f"Task success rate: {_percent(summary['task_success_rate'])}",
            f"Overkill count: {summary['overkill_count']}",
            f"Too-weak count: {summary['too_weak_count']}",
            f"Success by recommended tier: {summary['success_by_recommended_tier']}",
            f"Failure by project: {summary['failure_by_project']}",
            f"Most common escalation reasons: {summary['most_common_escalation_reasons']}",
        ]
    )


def task_category(task_description: str, files_touched: list[str]) -> str:
    text = " ".join([task_description, *files_touched]).casefold()
    if any(term in text for term in ["auth", "cyber", "intune", "graph", "network"]):
        return "security"
    if any(term in text for term in ["laserfiche", "api", "teamdynamix", "tdx"]):
        return "integration"
    if any(term in text for term in ["sql", "database", "dashboard", "report"]):
        return "data_report"
    if any(term in text for term in ["forge", "bot", "automation"]):
        return "automation"
    if any(term in text for term in ["html", "css", "ui", "form", "color", "background", "hello world", "prettier"]):
        return "ui"
    if any(term in text for term in ["readme", "docs", "documentation", "copy", "summary"]):
        return "docs"
    return "general"


def outcomes_path() -> Path:
    return Path(os.environ.get("AGENTIC_ROUTER_OUTCOMES", DATA_DIR / "outcomes.jsonl"))


def _reason_names(matched_rules: list[str]) -> list[str]:
    skipped = {"project_default", "project_risk", "cheap_content", "mid_complexity"}
    return sorted({rule.split(":", 1)[0] for rule in matched_rules if rule.split(":", 1)[0] not in skipped})


def _clean_text(value: str, field: str, limit: int, allow_blank: bool = False) -> str:
    text = str(value).strip()
    if not text and not allow_blank:
        raise ValueError(f"{field} is required")
    if len(text) > limit:
        raise ValueError(f"{field} must be {limit} characters or fewer")
    if any(pattern.search(text) for pattern in SENSITIVE_NOTE_PATTERNS):
        raise ValueError(f"{field} appears to contain sensitive content")
    return text


def _fit(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized == "too_weak":
        normalized = "too_cheap"
    if normalized not in FIT_VALUES:
        raise ValueError("recommendation_fit must be too_cheap, right, or overkill")
    return normalized


def _rate(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
