from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from .models import DATA_DIR

CLAUDE_PREFIXES = ("Haiku", "Sonnet", "Opus")
TIER_ALIAS = {"cheap": "devspace-cheap", "mid": "devspace-mid", "advanced": "devspace-advanced"}
ALIAS_POLICY = {
    "devspace-cheap": "cheap",
    "devspace-docs": "cheap",
    "devspace-mid": "mid",
    "devspace-advanced": "advanced",
    "devspace-live-prod": "live_prod",
    "devspace-security": "security",
    "devspace-public-official-content": "public_official_content",
}
SAFETY_TERMS = {
    "auth",
    "authentication",
    "sql",
    "database",
    "laserfiche",
    "teamdynamix",
    "tdx",
    "microsoft graph",
    "advanced hunting",
    "intune",
    "cybersecurity",
    "active directory",
    "infrastructure",
    "credentials",
    "secrets",
    "pii",
    "hr",
    "payroll",
    "veteran",
    "legal records",
    "public safety",
    "workers comp",
    "official public budget",
    "live forge",
    "forge prod",
}


@lru_cache(maxsize=1)
def load_model_aliases() -> dict[str, Any]:
    with (DATA_DIR / "model_aliases.json").open(encoding="utf-8") as f:
        return json.load(f)["aliases"]


@lru_cache(maxsize=1)
def load_routing_profiles() -> dict[str, Any]:
    with (DATA_DIR / "routing_profiles.json").open(encoding="utf-8") as f:
        return json.load(f)["profiles"]


@lru_cache(maxsize=1)
def load_fallback_policies() -> dict[str, list[str]]:
    with (DATA_DIR / "fallback_policies.json").open(encoding="utf-8") as f:
        return json.load(f)


def select_model(
    project_name: str,
    task_description: str,
    files_touched: list[str],
    model_tier: str,
    risk_level: str,
    matched_rules: list[str],
    live_prod: bool,
    profile_name: str = "balanced",
    cost_quality_tradeoff: int | None = None,
    allowed_models: list[str] | None = None,
    sticky_alias: str | None = None,
    sticky_model: str | None = None,
) -> dict[str, Any]:
    profile = _profile(profile_name)
    tradeoff = _tradeoff(cost_quality_tradeoff, profile)
    locked = safety_locked(project_name, task_description, files_touched, model_tier, risk_level, matched_rules, live_prod)
    alias = sticky_alias or _default_alias(project_name, task_description, files_touched, model_tier, matched_rules, live_prod)
    if sticky_alias is None:
        alias = _apply_tradeoff(alias, model_tier, tradeoff, locked)
        alias = _apply_profile_pool(alias, profile, locked)
        alias = _apply_allowed_aliases(alias, allowed_models, locked)

    family = None if sticky_alias else profile.get("model_family")
    candidates = _fallbacks(alias, family)
    selected = sticky_model if sticky_model in candidates else _pick_model(alias, candidates, allowed_models, locked)
    return {
        "selected_model_alias": alias,
        "selected_model": selected,
        "fallback_candidates": candidates,
        "profile_name": profile_name or "balanced",
        "cost_quality_tradeoff": tradeoff,
        "safety_locked": locked,
        "human_review_default": bool(profile.get("human_review_default")),
    }


def safety_locked(
    project_name: str,
    task_description: str,
    files_touched: list[str],
    model_tier: str,
    risk_level: str,
    matched_rules: list[str],
    live_prod: bool,
) -> bool:
    text = " ".join([project_name, task_description, *files_touched, *matched_rules]).casefold()
    return (
        live_prod
        or model_tier == "advanced"
        or risk_level in {"high", "critical"}
        or any(rule.split(":", 1)[0] in {"advanced_risk", "sensitive_project", "sensitive_data", "security_controls"} for rule in matched_rules)
        or any(term in text for term in SAFETY_TERMS)
    )


def model_family(model: str) -> str:
    return "claude" if model.startswith(CLAUDE_PREFIXES) else "codex"


def _profile(name: str | None) -> dict[str, Any]:
    profiles = load_routing_profiles()
    normalized = name or "balanced"
    if normalized not in profiles:
        raise ValueError(f"unknown routing profile: {normalized}")
    return profiles[normalized]


def _tradeoff(value: int | None, profile: dict[str, Any]) -> int:
    tradeoff = profile["cost_quality_tradeoff"] if value is None else value
    if not isinstance(tradeoff, int) or not 0 <= tradeoff <= 10:
        raise ValueError("cost_quality_tradeoff must be an integer from 0 to 10")
    return tradeoff


def _default_alias(
    project_name: str,
    task_description: str,
    files_touched: list[str],
    model_tier: str,
    matched_rules: list[str],
    live_prod: bool,
) -> str:
    text = " ".join([project_name, task_description, *files_touched, *matched_rules]).casefold()
    if "official public" in text or project_name in {"Local Budget Book", "Transparency Portal"}:
        return "devspace-public-official-content"
    if any(term in text for term in ["graph", "intune", "cybersecurity", "auth", "active directory", "advanced hunting"]):
        return "devspace-security"
    if live_prod or "live_prod_project" in matched_rules:
        return "devspace-live-prod"
    if model_tier == "cheap" and any(term in text for term in ["docs", "documentation", "readme", "copy", ".md"]):
        return "devspace-docs"
    return TIER_ALIAS[model_tier]


def _apply_tradeoff(alias: str, model_tier: str, tradeoff: int, locked: bool) -> str:
    if locked:
        return alias
    if tradeoff >= 8 and model_tier == "mid":
        return "devspace-cheap"
    if tradeoff <= 2 and model_tier in {"cheap", "mid"}:
        return "devspace-mid" if model_tier == "cheap" else "devspace-advanced"
    return alias


def _apply_profile_pool(alias: str, profile: dict[str, Any], locked: bool) -> str:
    allowed = profile["allowed_model_aliases"]
    if alias in allowed:
        return alias
    if locked:
        return "devspace-advanced" if "devspace-advanced" in allowed else alias
    return allowed[0]


def _apply_allowed_aliases(alias: str, allowed_models: list[str] | None, locked: bool) -> str:
    if not allowed_models:
        return alias
    allowed = {item.strip() for item in allowed_models if item.strip()}
    if alias in allowed:
        return alias
    aliases = load_model_aliases()
    usable_aliases = [name for name, spec in aliases.items() if name in allowed or spec["primary"] in allowed or spec["fallback"] in allowed]
    if not usable_aliases:
        return alias
    if locked:
        advanced = [name for name in usable_aliases if aliases[name]["tier"] == "advanced"]
        return advanced[0] if advanced else alias
    return usable_aliases[0]


def _pick_model(alias: str, candidates: list[str], allowed_models: list[str] | None, locked: bool) -> str:
    aliases = load_model_aliases()
    preferred = [aliases[alias]["primary"], aliases[alias]["fallback"]]
    allowed = {item.strip() for item in allowed_models or [] if item.strip()}
    if allowed and not locked:
        for model in [*preferred, *candidates]:
            if model in allowed:
                return model
    for model in preferred:
        if model in candidates:
            return model
    return candidates[0]


def _fallbacks(alias: str, family: str | None) -> list[str]:
    policy = load_fallback_policies()[ALIAS_POLICY[alias]]
    filtered = [model for model in policy if family is None or model_family(model) == family]
    if filtered:
        return filtered
    spec = load_model_aliases()[alias]
    return [model for model in [spec["primary"], spec["fallback"]] if family is None or model_family(model) == family]
