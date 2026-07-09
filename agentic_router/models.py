from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=1)
def load_model_catalog() -> dict[str, Any]:
    with (DATA_DIR / "models.json").open(encoding="utf-8") as f:
        return json.load(f)


def default_model_for_tier(tier: str) -> str:
    return load_model_catalog()["default_by_tier"][tier]

