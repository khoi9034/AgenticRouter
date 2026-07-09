from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import DATA_DIR, load_model_catalog
from .observability import sanitize_text
from .outcomes import task_category
from .router import route
from .rules import TIER_ORDER
from .simulator import TIER_UNITS

SHADOW_PREFIX = "sh_"
REPORT_DIR = DATA_DIR.parent / "exports" / "reports"


def shadow_path() -> Path:
    return Path(os.environ.get("AGENTIC_ROUTER_SHADOW_RUNS", DATA_DIR / "shadow_runs.jsonl"))


def write_shadow_run(
    project_name: str,
    task_description: str,
    files_touched: list[str],
    result: dict[str, Any],
    actual_model_used: str | None,
    router_would_block_in_strict: bool,
    path: Path | None = None,
) -> dict[str, Any]:
    actual_model = sanitize_text(actual_model_used or "unknown", 80) or "unknown"
    actual_tier = tier_for_model(actual_model)
    comparison = compare_tiers(result["model_tier"], actual_tier, result["human_review_required"], router_would_block_in_strict)
    category = task_category(task_description, files_touched)
    high_risk = _high_risk(result)
    record = {
        "shadow_id": SHADOW_PREFIX + uuid.uuid4().hex,
        "route_id": result["route_id"],
        "timestamp": _now(),
        "project_name": project_name,
        "task_class": category,
        "risk_level": result["risk_level"],
        "recommended_model": result["recommended_model"],
        "recommended_model_alias": result["selected_model_alias"],
        "recommended_tier": result["model_tier"],
        "actual_model_used": actual_model,
        "actual_tier": actual_tier,
        "profile_name": result["profile_name"],
        "context_size": result["context_pack"]["context_size"],
        "human_review_required": result["human_review_required"],
        "router_would_block_in_strict": router_would_block_in_strict,
        "matched_rules": result["matched_rules"],
        "prompt_body_logged": not high_risk,
        "sanitized_task_category": category,
        "overkill_or_underpowered": comparison["overkill_or_underpowered"],
        "abstract_cost_delta": comparison["abstract_cost_delta"],
    }
    if high_risk:
        record["task_description_hash"] = hashlib.sha256(task_description.encode("utf-8")).hexdigest()[:16]

    target = path or shadow_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    return {"record": record, "comparison": comparison}


def load_shadow_runs(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or shadow_path()
    if not target.exists():
        return []
    with target.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def summarize_shadow_runs(records: list[dict[str, Any]] | None = None, path: Path | None = None) -> dict[str, Any]:
    records = load_shadow_runs(path) if records is None else records
    total = len(records)
    exact_model = sum(1 for item in records if item.get("actual_model_used") == item.get("recommended_model"))
    tier_agree = sum(1 for item in records if item.get("actual_tier") == item.get("recommended_tier"))
    overkill = [item for item in records if item.get("overkill_or_underpowered") == "human_stronger"]
    too_weak = [item for item in records if item.get("overkill_or_underpowered") in {"human_weaker", "safety_risk"}]
    cost_records = [item for item in records if item.get("actual_tier") in TIER_UNITS and item.get("recommended_tier") in TIER_UNITS]
    actual_cost = sum(TIER_UNITS[item["actual_tier"]] for item in cost_records)
    router_cost = sum(TIER_UNITS[item["recommended_tier"]] for item in cost_records)
    mismatches = overkill + too_weak
    return {
        "total_shadow_runs": total,
        "recommended_tier_distribution": dict(Counter(item.get("recommended_tier") for item in records)),
        "actual_tier_distribution": dict(Counter(item.get("actual_tier") for item in records)),
        "exact_model_agreement_count": exact_model,
        "exact_model_agreement_rate": _rate(exact_model, total),
        "tier_agreement_count": tier_agree,
        "tier_agreement_rate": _rate(tier_agree, total),
        "human_used_stronger_than_router_count": len(overkill),
        "human_used_weaker_than_router_count": sum(1 for item in records if item.get("overkill_or_underpowered") == "human_weaker"),
        "estimated_overkill_count": len(overkill),
        "estimated_too_weak_safety_risk_count": len(too_weak),
        "human_review_required_count": sum(1 for item in records if item.get("human_review_required")),
        "strict_mode_would_block_count": sum(1 for item in records if item.get("router_would_block_in_strict")),
        "estimated_abstract_cost_of_actual_usage": actual_cost,
        "estimated_abstract_cost_of_router_recommendation": router_cost,
        "estimated_units_saved_lost": actual_cost - router_cost,
        "projects_with_most_overkill": Counter(item["project_name"] for item in overkill).most_common(5),
        "projects_with_most_too_weak_safety_mismatches": Counter(item["project_name"] for item in too_weak).most_common(5),
        "top_mismatch_projects": Counter(item["project_name"] for item in mismatches).most_common(5),
        "tasks_where_human_used_cheap_but_router_recommended_advanced": _cases(
            records, actual_tier="cheap", recommended_tier="advanced"
        ),
        "tasks_where_human_used_advanced_but_router_recommended_cheap_mid": [
            _case(item) for item in records if item.get("actual_tier") == "advanced" and item.get("recommended_tier") in {"cheap", "mid"}
        ],
    }


def format_shadow_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Total shadow runs: {summary['total_shadow_runs']}",
            f"Recommended tiers: {json.dumps(summary['recommended_tier_distribution'], sort_keys=True)}",
            f"Actual tiers: {json.dumps(summary['actual_tier_distribution'], sort_keys=True)}",
            f"Exact model agreement: {summary['exact_model_agreement_count']} ({_percent(summary['exact_model_agreement_rate'])})",
            f"Tier agreement: {summary['tier_agreement_count']} ({_percent(summary['tier_agreement_rate'])})",
            f"Human used stronger than router: {summary['human_used_stronger_than_router_count']}",
            f"Human used weaker than router: {summary['human_used_weaker_than_router_count']}",
            f"Estimated overkill count: {summary['estimated_overkill_count']}",
            f"Estimated too-weak/safety risk count: {summary['estimated_too_weak_safety_risk_count']}",
            f"Human review required count: {summary['human_review_required_count']}",
            f"Strict-mode would-block count: {summary['strict_mode_would_block_count']}",
            f"Actual usage cost units: {summary['estimated_abstract_cost_of_actual_usage']}",
            f"Router recommendation cost units: {summary['estimated_abstract_cost_of_router_recommendation']}",
            f"Estimated units saved/lost: {summary['estimated_units_saved_lost']}",
            f"Projects with most overkill: {summary['projects_with_most_overkill']}",
            f"Projects with most too-weak/safety mismatches: {summary['projects_with_most_too_weak_safety_mismatches']}",
        ]
    )


def export_shadow_report(output_dir: Path | None = None, records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    folder = output_dir or REPORT_DIR
    folder.mkdir(parents=True, exist_ok=True)
    summary = summarize_shadow_runs(records)
    report = {"generated_at": _now(), "summary": summary}
    json_path = folder / "shadow_mode_report.json"
    md_path = folder / "shadow_mode_report.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown_report(report), encoding="utf-8")
    return {"export_folder": str(folder), "files": {"markdown": str(md_path), "json": str(json_path)}, "summary": summary}


def add_demo_data(path: Path | None = None) -> list[dict[str, Any]]:
    records = []
    for item in _demo_requests():
        result = route(
            project_name=item["project_name"],
            task_description=item["task_description"],
            files_touched=item.get("files_touched", []),
            previous_failure_count=item.get("previous_failure_count", 0),
            live_prod=item.get("live_prod"),
        )
        shadow = write_shadow_run(
            item["project_name"],
            item["task_description"],
            item.get("files_touched", []),
            result,
            item["actual_model_used"],
            result["human_review_required"],
            path=path,
        )
        records.append(shadow["record"])
    return records


def tier_for_model(model_or_alias: str | None) -> str:
    normalized = (model_or_alias or "").strip().casefold()
    if not normalized or normalized == "unknown":
        return "unknown"
    catalog = load_model_catalog()
    for model in catalog["models"]:
        if model["name"].casefold() == normalized:
            return model["tier"]
    aliases_path = DATA_DIR / "model_aliases.json"
    if aliases_path.exists():
        aliases = json.loads(aliases_path.read_text(encoding="utf-8"))["aliases"]
        for name, spec in aliases.items():
            if name.casefold() == normalized:
                return spec["tier"]
    return "unknown"


def compare_tiers(recommended_tier: str, actual_tier: str, human_review_required: bool = False, router_would_block: bool = False) -> dict[str, Any]:
    if recommended_tier not in TIER_UNITS or actual_tier not in TIER_UNITS:
        return {
            "recommended_tier": recommended_tier,
            "actual_tier": actual_tier,
            "overkill_or_underpowered": "unknown",
            "abstract_cost_delta": None,
        }
    rec_index = TIER_ORDER.index(recommended_tier)
    actual_index = TIER_ORDER.index(actual_tier)
    if actual_index == rec_index:
        label = "agreement"
    elif actual_index > rec_index:
        label = "human_stronger"
    elif recommended_tier == "advanced" or human_review_required or router_would_block:
        label = "safety_risk"
    else:
        label = "human_weaker"
    return {
        "recommended_tier": recommended_tier,
        "actual_tier": actual_tier,
        "overkill_or_underpowered": label,
        "abstract_cost_delta": TIER_UNITS[actual_tier] - TIER_UNITS[recommended_tier],
    }


def _demo_requests() -> list[dict[str, Any]]:
    return [
        {
            "project_name": "Diana Test Project",
            "task_description": "Refresh hello world page copy",
            "files_touched": ["index.html"],
            "actual_model_used": "GPT-5.5",
        },
        {
            "project_name": "Mark's Test Project",
            "task_description": "Update placeholder documentation",
            "files_touched": ["README.md"],
            "actual_model_used": "Opus 4.8",
        },
        {
            "project_name": "Veteran's Intake Application",
            "task_description": "Fix sanitized auth redirect bug",
            "files_touched": ["Auth/ping.php"],
            "actual_model_used": "Haiku 4.5",
        },
        {
            "project_name": "Grant Quarter Reporting",
            "task_description": "Create quarterly dashboard report summary",
            "files_touched": ["reports/quarterly.py"],
            "actual_model_used": "Sonnet 4.6",
        },
        {
            "project_name": "Gap Bills Forge Conversion",
            "task_description": "Change PDF output naming format",
            "files_touched": ["forge_bot/gap_bills_bot.py"],
            "actual_model_used": "GPT-5.5",
            "live_prod": True,
        },
    ]


def _cases(records: list[dict[str, Any]], actual_tier: str, recommended_tier: str) -> list[dict[str, Any]]:
    return [_case(item) for item in records if item.get("actual_tier") == actual_tier and item.get("recommended_tier") == recommended_tier]


def _case(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "shadow_id": item["shadow_id"],
        "route_id": item["route_id"],
        "project_name": item["project_name"],
        "risk_level": item["risk_level"],
        "recommended_model": item["recommended_model"],
        "recommended_tier": item["recommended_tier"],
        "actual_model_used": item["actual_model_used"],
        "actual_tier": item["actual_tier"],
    }


def _markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    return "\n".join(
        [
            "# Shadow Mode Report",
            "",
            "Shadow mode is advisory. It does not change DevSpace model selection.",
            "",
            f"Generated: {report['generated_at']}",
            f"Total shadow runs: {summary['total_shadow_runs']}",
            f"Tier agreement rate: {_percent(summary['tier_agreement_rate'])}",
            f"Estimated overkill count: {summary['estimated_overkill_count']}",
            f"Estimated too-weak/safety risk count: {summary['estimated_too_weak_safety_risk_count']}",
            f"Estimated units saved/lost: {summary['estimated_units_saved_lost']}",
            "",
            "## Top Mismatch Projects",
            "",
            json.dumps(summary["top_mismatch_projects"], indent=2),
            "",
            "## Cheap Actual / Advanced Router",
            "",
            json.dumps(summary["tasks_where_human_used_cheap_but_router_recommended_advanced"], indent=2),
            "",
            "## Advanced Actual / Cheap Or Mid Router",
            "",
            json.dumps(summary["tasks_where_human_used_advanced_but_router_recommended_cheap_mid"], indent=2),
            "",
        ]
    )


def _high_risk(result: dict[str, Any]) -> bool:
    return result["risk_level"] not in {"low", "medium"} or result["model_tier"] == "advanced" or result["human_review_required"]


def _rate(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
