from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config_validation import config_summary, validate_config
from .evaluator import evaluate_tasks
from .integration import CONTRACT_VERSION, load_contract
from .models import DATA_DIR, load_model_catalog
from .observability import observability_status
from .shadow import summarize_shadow_runs
from .simulator import run_scenario

REPORT_DIR = DATA_DIR.parent / "exports" / "reports"
ROLLOUT_SEQUENCE = [
    "local demo",
    "shadow mode",
    "advise mode for low-risk projects",
    "packet mode for normal tasks",
    "strict mode for high-risk/live-prod tasks",
]


def pilot_scorecard() -> dict[str, Any]:
    golden = evaluate_tasks()
    config = config_summary()
    validation = validate_config()
    observability = observability_status()
    contract = load_contract()
    models = load_model_catalog()["models"]
    shadow = summarize_shadow_runs()
    ready = golden["failed"] == 0 and validation["ok"] and observability["local_tracing_enabled"]
    return {
        "generated_at": _now(),
        "unit_test_count": _count_tests(),
        "golden_eval_count": golden["total"],
        "golden_eval_passed": golden["passed"],
        "golden_eval_pass_rate": _rate(golden["passed"], golden["total"]),
        "project_count": config["total_projects"],
        "projects_by_risk": config["projects_by_risk"],
        "high_risk_project_count": config["high_risk_project_count"],
        "model_tiers_available": sorted({item["tier"] for item in models}),
        "local_observability_enabled": observability["local_tracing_enabled"],
        "remote_tracing_enabled": observability["remote_tracing_enabled"],
        "shadow_analytics_enabled": True,
        "shadow_run_count": shadow["total_shadow_runs"],
        "config_validation_status": config["validation_status"],
        "integration_contract_version": contract.get("contract_version", CONTRACT_VERSION),
        "integration_modes": contract.get("modes", []),
        "readiness_status": "demo-ready" if ready else "needs-work",
    }


def build_pilot_report() -> dict[str, Any]:
    scorecard = pilot_scorecard()
    return {
        "generated_at": scorecard["generated_at"],
        "scorecard": scorecard,
        "current_router_capabilities": [
            "rule-based model routing",
            "golden regression evaluation",
            "local web UI",
            "context pack builder",
            "DevSpace run packet generator",
            "outcome feedback logging",
            "routing profiles, fallbacks, and session stickiness",
            "local observability and exports",
            "config validation and Config Studio",
            "scenario simulation",
            "DevSpace v1 integration API",
            "shadow mode analytics",
        ],
        "scenario_simulator_savings_examples": _scenario_examples(),
        "local_observability_status": _public_observability_status(),
        "shadow_mode_readiness": {
            "enabled": True,
            "total_shadow_runs": scorecard["shadow_run_count"],
            "report_path": "exports/reports/shadow_mode_report.md",
        },
        "recommended_rollout_sequence": ROLLOUT_SEQUENCE,
        "known_limitations": [
            "Rules are keyword/catalog based and do not call an AI model.",
            "Cost savings use abstract units, not real dollars.",
            "Shadow analytics depend on callers supplying actual_model_used.",
            "Config Studio has a guarded add-project form, not a full policy editor.",
            "Human review gates are reported locally; enforcement depends on the caller using strict mode.",
        ],
        "privacy_safety_rules": [
            "No secrets, API keys, bearer tokens, passwords, or credentials.",
            "No real PII/PHI, veteran records, workers comp claims, legal/client records, or student raw comments.",
            "No emails, tenant IDs, USB serials, private Windows paths, production logs, or real records.",
            "High-risk traces and shadow records store hashes/categories instead of raw task text.",
            "Everything stays local and offline.",
        ],
        "next_engineering_steps": [
            "Pilot shadow mode against real DevSpace manual choices.",
            "Review shadow mismatches and adjust routing rules/catalog entries.",
            "Use advise mode for low-risk projects after agreement is high.",
            "Add caller-side strict-mode blocking for live-prod and sensitive projects.",
            "Schedule periodic golden eval, config validation, outcome, and shadow report review.",
        ],
    }


def export_pilot_report(output_dir: Path | None = None) -> dict[str, Any]:
    folder = output_dir or REPORT_DIR
    folder.mkdir(parents=True, exist_ok=True)
    report = build_pilot_report()
    md_path = folder / "pilot_readiness_report.md"
    json_path = folder / "pilot_readiness_report.json"
    scorecard_path = folder / "demo_scorecard.json"
    md_path.write_text(format_pilot_report(report), encoding="utf-8")
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    scorecard_path.write_text(json.dumps(report["scorecard"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "export_folder": str(folder),
        "files": {"markdown": str(md_path), "json": str(json_path), "scorecard": str(scorecard_path)},
        "scorecard": report["scorecard"],
    }


def format_pilot_report(report: dict[str, Any]) -> str:
    score = report["scorecard"]
    scenarios = report["scenario_simulator_savings_examples"]
    return "\n".join(
        [
            "# Pilot Readiness Report",
            "",
            f"Generated: {report['generated_at']}",
            f"Readiness status: {score['readiness_status']}",
            "",
            "## Scorecard",
            "",
            f"- Golden eval: {score['golden_eval_passed']}/{score['golden_eval_count']} ({score['golden_eval_pass_rate']}%)",
            f"- Projects: {score['project_count']}",
            f"- High-risk projects: {score['high_risk_project_count']}",
            f"- Model tiers: {', '.join(score['model_tiers_available'])}",
            f"- Local observability enabled: {score['local_observability_enabled']}",
            f"- Shadow analytics enabled: {score['shadow_analytics_enabled']}",
            f"- Config validation: {score['config_validation_status']}",
            f"- Integration contract: {score['integration_contract_version']}",
            "",
            "## Capabilities",
            "",
            _bullets(report["current_router_capabilities"]),
            "",
            "## Scenario Savings Examples",
            "",
            _bullets(
                [
                    f"{name}: {item['estimated_units_saved']} model units saved, {item['estimated_context_units_saved']} context units saved"
                    for name, item in scenarios.items()
                ]
            ),
            "",
            "## Rollout Sequence",
            "",
            _numbered(report["recommended_rollout_sequence"]),
            "",
            "## Known Limitations",
            "",
            _bullets(report["known_limitations"]),
            "",
            "## Privacy And Safety Rules",
            "",
            _bullets(report["privacy_safety_rules"]),
            "",
            "## Next Engineering Steps",
            "",
            _bullets(report["next_engineering_steps"]),
            "",
        ]
    )


def demo_script_text() -> str:
    return "\n".join(
        [
            "# Demo Script",
            "",
            "1. Open the local web UI: `python -m agentic_router.web`, then open `http://127.0.0.1:8765`.",
            "2. Low-risk example: Diana Test Project + `Make hello world page prettier`.",
            "3. High-risk example: Veteran's Intake Application + `Fix auth ping redirect`.",
            "4. Live-prod bot example: Gap Bills Forge Conversion + `Change PDF output naming format`.",
            "5. Official content example: Local Budget Book + `Fix official fund summary table`.",
            "6. Show the Recommended Context Pack section.",
            "7. Show the DevSpace Run Packet section.",
            "8. Show Scenario Simulator and run `mixed_devspace_month`.",
            "9. Show Shadow Analytics and explain advisory comparison to actual model use.",
            "10. Show Config Studio validation and local add-project guardrails.",
            "11. Show Enterprise Exports and explain they are sanitized local templates.",
            "12. Explain rollout modes: shadow, advise, packet, strict.",
            "",
            "Close with: AgenticRouter is local, rule-based, and makes no AI, cloud, API-key, or remote tracing calls.",
        ]
    )


def rollout_plan_text() -> str:
    return "\n".join(
        [
            "# Rollout Plan",
            "",
            "## Phase A: Local-Only Demo",
            "Run the web UI and walk through low-risk, high-risk, live-prod, and official-content examples.",
            "",
            "## Phase B: Shadow Mode",
            "Call `/api/v1/shadow` with actual DevSpace model choices and review shadow reports.",
            "",
            "## Phase C: Advise Mode",
            "Use `/api/v1/route` for docs, static UI, and test projects where risk is low.",
            "",
            "## Phase D: Packet Mode",
            "Use `/api/v1/packet` for normal coding tasks that benefit from a copy-pasteable run packet.",
            "",
            "## Phase E: Strict Mode",
            "Use `/api/v1/strict-check` for live-prod, sensitive, security, auth, SQL, Laserfiche, TeamDynamix, Microsoft Graph, Intune, infrastructure, and official-content work.",
            "",
            "## Phase F: Periodic Review",
            "Review golden evals, shadow reports, outcomes, and config validation on a recurring cadence.",
        ]
    )


def format_scorecard(scorecard: dict[str, Any] | None = None) -> str:
    score = pilot_scorecard() if scorecard is None else scorecard
    return "\n".join(
        [
            f"Readiness status: {score['readiness_status']}",
            f"Unit test count: {score['unit_test_count']}",
            f"Golden eval: {score['golden_eval_passed']}/{score['golden_eval_count']} ({score['golden_eval_pass_rate']}%)",
            f"Project count: {score['project_count']}",
            f"High-risk project count: {score['high_risk_project_count']}",
            f"Local observability enabled: {score['local_observability_enabled']}",
            f"Shadow analytics enabled: {score['shadow_analytics_enabled']}",
            f"Config validation status: {score['config_validation_status']}",
            f"Integration contract version: {score['integration_contract_version']}",
        ]
    )


def _scenario_examples() -> dict[str, dict[str, Any]]:
    examples = {}
    for name in ["docs_heavy_week", "mixed_devspace_month"]:
        savings = run_scenario(name)["summary"]["savings"]
        examples[name] = {
            "estimated_units_saved": savings["estimated_units_saved"],
            "estimated_percent_saved": savings["estimated_percent_saved"],
            "estimated_context_units_saved": savings["estimated_context_units_saved"],
            "estimated_context_percent_saved": savings["estimated_context_percent_saved"],
        }
    return examples


def _public_observability_status() -> dict[str, Any]:
    status = observability_status()
    return {
        "local_tracing_enabled": status["local_tracing_enabled"],
        "remote_tracing_enabled": status["remote_tracing_enabled"],
        "langsmith_api_enabled": status["langsmith_api_enabled"],
        "langsmith_api_disabled_by_design": status["langsmith_api_disabled_by_design"],
    }


def _count_tests() -> int:
    tests_dir = DATA_DIR.parent / "tests"
    return sum(len(re.findall(r"^\s+def test_", path.read_text(encoding="utf-8"), flags=re.M)) for path in tests_dir.glob("test_*.py"))


def _rate(count: int, total: int) -> float:
    return round((count / total) * 100, 1) if total else 0.0


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _numbered(items: list[str]) -> str:
    return "\n".join(f"{index}. {item}" for index, item in enumerate(items, 1))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
