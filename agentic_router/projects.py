from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from .models import DATA_DIR


@lru_cache(maxsize=1)
def load_projects() -> list[dict[str, Any]]:
    with (DATA_DIR / "projects.json").open(encoding="utf-8") as f:
        return json.load(f)["projects"]


def find_project(name: str) -> dict[str, Any]:
    wanted = name.casefold()
    for project in load_projects():
        names = [project["name"], *project.get("aliases", [])]
        if wanted in {item.casefold() for item in names}:
            return project

    return {
        "name": name,
        "risk_level": "low",
        "default_tier": "cheap",
        "live_prod": False,
        "sensitive": False,
        "keywords": [],
    }

