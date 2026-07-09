from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .models import DATA_DIR

TIER_ORDER = ["cheap", "mid", "advanced"]
RISK_ORDER = ["low", "medium", "medium-high", "high", "critical"]
CODE_EXTENSIONS = {
    ".py",
    ".php",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".sql",
    ".cs",
    ".java",
    ".go",
    ".ps1",
    ".sh",
    ".yml",
    ".yaml",
    ".tf",
    ".bicep",
}


@lru_cache(maxsize=1)
def load_routing_rules() -> dict[str, Any]:
    with (DATA_DIR / "routing_rules.json").open(encoding="utf-8") as f:
        return json.load(f)


def escalate_tier(tier: str) -> str:
    return TIER_ORDER[min(TIER_ORDER.index(tier) + 1, len(TIER_ORDER) - 1)]


def max_tier(*tiers: str) -> str:
    return max(tiers, key=TIER_ORDER.index)


def max_risk(*risks: str) -> str:
    return max(risks, key=RISK_ORDER.index)


def hits(text: str, terms: list[str]) -> list[str]:
    folded = text.casefold()
    return [term for term in terms if term.casefold() in folded]


def touches_code(files: list[str]) -> bool:
    return any(Path(file).suffix.casefold() in CODE_EXTENSIONS for file in files)

