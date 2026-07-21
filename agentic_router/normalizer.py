from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from .models import DATA_DIR
from .observability import sanitize_text
from .rules import max_tier

COMPLEXITY_ORDER = ["low", "medium", "high"]
INTRINSIC_RISK_ORDER = ["low", "medium", "high"]


@lru_cache(maxsize=1)
def load_task_taxonomy() -> dict[str, Any]:
    with (DATA_DIR / "task_taxonomy.json").open(encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_task_risk_signals() -> dict[str, Any]:
    with (DATA_DIR / "task_risk_signals.json").open(encoding="utf-8") as f:
        return json.load(f)


def normalize_task(task_description: str, files_touched: list[str] | None = None) -> dict[str, Any]:
    files = files_touched or []
    signal_config = load_task_risk_signals()
    text = _fold(" ".join([task_description, *files]))
    matches = _matched_signals(text, signal_config["signals"])
    top_signal = max(matches, key=lambda item: INTRINSIC_RISK_ORDER.index(item["risk"])) if matches else None
    security_sensitive = any(item.get("security_sensitive") for item in matches)
    data_sensitive = any(item.get("data_sensitive") for item in matches)
    production_sensitive = any(item.get("production_sensitive") for item in matches)
    intrinsic_risk = _max_order(INTRINSIC_RISK_ORDER, [item["risk"] for item in matches] or ["low"])
    complexity = _max_order(COMPLEXITY_ORDER, [item["complexity"] for item in matches] or ["low"])
    minimum_tier = "cheap"
    for item in matches:
        minimum_tier = max_tier(minimum_tier, item["minimum_tier"])

    return {
        "normalized_summary": sanitize_text(task_description, 180),
        "task_type": top_signal["task_type"] if top_signal else "general",
        "requested_capabilities": _unique(item["capability"] for item in matches),
        "complexity": complexity,
        "intrinsic_risk": intrinsic_risk,
        "security_sensitive": security_sensitive,
        "data_sensitive": data_sensitive,
        "production_sensitive": production_sensitive,
        "minimum_recommended_tier": minimum_tier,
        "human_review_recommended": security_sensitive or data_sensitive,
        "ambiguity_warnings": _ambiguity_warnings(task_description, files, matches, signal_config["ambiguous_terms"]),
        "extracted_constraints": _constraints(task_description),
        "forbidden_context_hints": _forbidden_hints(security_sensitive, data_sensitive, production_sensitive, signal_config),
        "matched_task_signals": [f"{item['risk']}:{item['name']}:{', '.join(item['hits'][:3])}" for item in matches],
    }


def _matched_signals(text: str, signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches = []
    for signal in signals:
        hits = [term for term in signal["terms"] if _term_hit(text, term)]
        if hits:
            item = dict(signal)
            item["hits"] = hits
            matches.append(item)
    return matches


def _term_hit(text: str, term: str) -> bool:
    folded = _fold(term)
    if folded in {"production", "prod"} and any(marker in text for marker in ["non production", "non-production", "non prod", "non-prod"]):
        return False
    if " " in folded or "." in folded or "-" in folded:
        return folded in text
    return re.search(rf"\b{re.escape(folded)}\b", text) is not None


def _ambiguity_warnings(task: str, files: list[str], matches: list[dict[str, Any]], ambiguous_terms: list[str]) -> list[str]:
    text = _fold(task)
    warnings = []
    if len(task.split()) < 4:
        warnings.append("Task description is very short; include the exact desired change and acceptance criteria.")
    if any(term in text for term in ambiguous_terms):
        warnings.append("Task wording is ambiguous; clarify scope before routing or execution.")
    if matches and not files and max((item["risk"] for item in matches), key=INTRINSIC_RISK_ORDER.index) == "high":
        warnings.append("High-risk task has no files listed; include only directly relevant files or patterns.")
    return warnings


def _constraints(task: str) -> list[str]:
    constraints = []
    for sentence in re.split(r"(?<=[.!?])\s+|;", task):
        folded = sentence.casefold()
        if any(marker in folded for marker in ["must", "only", "without", "do not", "don't", "keep", "avoid"]):
            constraints.append(sanitize_text(sentence.strip(), 160))
    return constraints


def _forbidden_hints(security: bool, data: bool, production: bool, signal_config: dict[str, Any]) -> list[str]:
    hints = []
    groups = signal_config["forbidden_context_hints"]
    if security:
        hints.extend(groups["security"])
    if data:
        hints.extend(groups["data"])
    if production:
        hints.extend(groups["production"])
    return _unique(hints)


def _max_order(order: list[str], values: list[str]) -> str:
    return max(values, key=order.index)


def _fold(value: str) -> str:
    return " ".join(str(value).casefold().replace("_", " ").split())


def _unique(items) -> list[str]:
    seen = set()
    return [item for item in items if not (item in seen or seen.add(item))]
