from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .config_studio import export_config, import_config
from .config_validation import config_summary, format_config_summary, format_validation, validate_config
from .contracts import check_contract, format_contract, format_scope_check, generate_contract, load_contract_file
from .context import format_context_pack
from .diff_review import format_diff_review, review_current_diff, review_diff
from .enterprise import export_enterprise, format_export_result
from .evaluator import evaluate_tasks, format_summary
from .integration import export_devspace_contract, format_contract_summary, integration_self_test
from .observability import (
    export_langsmith_files,
    format_observability_status,
    format_traces_summary,
    observability_status,
    summarize_traces,
)
from .outcomes import format_outcomes_summary, save_feedback, summarize_outcomes
from .packets import format_packet, generate_packet
from .pilot import demo_script_text, export_pilot_report, format_scorecard, pilot_scorecard, rollout_plan_text
from .normalizer import normalize_task
from .router import route
from .sessions import format_session_summary, summarize_sessions
from .shadow import add_demo_data, export_shadow_report, format_shadow_summary, summarize_shadow_runs
from .simulator import format_simulation, list_scenarios, run_scenario


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentic-router")
    subparsers = parser.add_subparsers(dest="command", required=True)

    route_parser = subparsers.add_parser("route", help="recommend a DevSpace model")
    route_parser.add_argument("--project", required=True)
    route_parser.add_argument("--task", required=True)
    route_parser.add_argument("--files", nargs="*", default=[])
    route_parser.add_argument("--failures", type=int, default=0)
    route_parser.add_argument("--live-prod", action="store_true")
    route_parser.add_argument("--sensitive", action="store_true")
    route_parser.add_argument("--format", choices=["text", "json"], default="text")
    route_parser.add_argument("--json", action="store_true", dest="json_output")
    _add_routing_controls(route_parser)
    context_parser = subparsers.add_parser("context", help="recommend a context pack")
    context_parser.add_argument("--project", required=True)
    context_parser.add_argument("--task", required=True)
    context_parser.add_argument("--files", nargs="*", default=[])
    context_parser.add_argument("--json", action="store_true", dest="json_output")
    _add_routing_controls(context_parser)
    packet_parser = subparsers.add_parser("packet", help="generate a DevSpace run packet")
    packet_parser.add_argument("--project", required=True)
    packet_parser.add_argument("--task", required=True)
    packet_parser.add_argument("--files", nargs="*", default=[])
    packet_parser.add_argument("--failures", type=int, default=0)
    packet_parser.add_argument("--live-prod", action="store_true")
    packet_parser.add_argument("--json", action="store_true", dest="json_output")
    _add_routing_controls(packet_parser)
    normalize_parser = subparsers.add_parser("normalize", help="classify intrinsic task risk without routing")
    normalize_parser.add_argument("--task", required=True)
    normalize_parser.add_argument("--files", nargs="*", default=[])
    normalize_parser.add_argument("--failures", type=int, default=0)
    normalize_parser.add_argument("--json", action="store_true", dest="json_output")
    contract_parser = subparsers.add_parser("contract", help="generate a run contract")
    contract_parser.add_argument("--project", required=True)
    contract_parser.add_argument("--task", required=True)
    contract_parser.add_argument("--files", nargs="*", default=[])
    contract_parser.add_argument("--failures", type=int, default=0)
    contract_parser.add_argument("--live-prod", action="store_true")
    contract_parser.add_argument("--output")
    contract_parser.add_argument("--json", action="store_true", dest="json_output")
    _add_routing_controls(contract_parser)
    check_parser = subparsers.add_parser("check-contract", help="check changed files against a run contract")
    check_parser.add_argument("--contract-file", required=True)
    check_parser.add_argument("--changed-files", nargs="*", default=[])
    check_parser.add_argument("--diff-summary", default="")
    check_parser.add_argument("--added-dependencies", nargs="*", default=[])
    check_parser.add_argument("--json", action="store_true", dest="json_output")
    review_parser = subparsers.add_parser("review-diff", help="review a patch/diff against local quality rules")
    review_parser.add_argument("--project", required=True)
    review_parser.add_argument("--task", required=True)
    review_parser.add_argument("--diff-file", required=True)
    review_parser.add_argument("--changed-files", nargs="*", default=[])
    review_parser.add_argument("--contract-file")
    review_parser.add_argument("--added-dependencies", nargs="*", default=[])
    review_parser.add_argument("--tests-run", nargs="*", default=[])
    review_parser.add_argument("--live-prod", action="store_true")
    review_parser.add_argument("--json", action="store_true", dest="json_output")
    current_review_parser = subparsers.add_parser("review-current-diff", help="review the current local git diff")
    current_review_parser.add_argument("--project", required=True)
    current_review_parser.add_argument("--task", required=True)
    current_review_parser.add_argument("--contract-file")
    current_review_parser.add_argument("--added-dependencies", nargs="*", default=[])
    current_review_parser.add_argument("--tests-run", nargs="*", default=[])
    current_review_parser.add_argument("--live-prod", action="store_true")
    current_review_parser.add_argument("--json", action="store_true", dest="json_output")
    subparsers.add_parser("eval", help="run golden routing evaluation")
    feedback_parser = subparsers.add_parser("feedback", help="save routing outcome feedback")
    feedback_parser.add_argument("--route-id", required=True)
    feedback_parser.add_argument("--accepted", required=True, type=_bool_arg)
    feedback_parser.add_argument("--task-succeeded", required=True, type=_unknown_bool_arg)
    feedback_parser.add_argument("--actual-model", required=True)
    feedback_parser.add_argument("--recommendation-fit", required=True)
    feedback_parser.add_argument("--notes", default="")
    subparsers.add_parser("outcomes", help="summarize routing feedback outcomes")
    subparsers.add_parser("sessions", help="summarize routing session cache")
    subparsers.add_parser("traces", help="summarize local router traces")
    subparsers.add_parser("export-langsmith-files", help="write local LangSmith-app-compatible files")
    subparsers.add_parser("observability-status", help="show local observability status")
    subparsers.add_parser("validate-config", help="validate local routing configuration")
    config_export_parser = subparsers.add_parser("export-config", help="export local config bundle")
    config_export_parser.add_argument("--output", required=True)
    config_import_parser = subparsers.add_parser("import-config", help="validate or apply local config bundle")
    config_import_parser.add_argument("--input", required=True)
    config_import_parser.add_argument("--dry-run", action="store_true")
    config_import_parser.add_argument("--apply", action="store_true")
    subparsers.add_parser("config-summary", help="summarize local routing configuration")
    simulate_parser = subparsers.add_parser("simulate", help="run a routing simulation scenario")
    simulate_parser.add_argument("--scenario", required=True)
    simulate_parser.add_argument("--json", action="store_true", dest="json_output")
    subparsers.add_parser("list-scenarios", help="list available simulation scenarios")
    subparsers.add_parser("api-contract", help="print DevSpace integration contract summary")
    subparsers.add_parser("export-devspace-contract", help="write DevSpace integration contract files")
    subparsers.add_parser("integration-test", help="run built-in integration contract checks")
    subparsers.add_parser("shadow-summary", help="summarize shadow mode analytics")
    subparsers.add_parser("export-shadow-report", help="write shadow mode rollout report")
    subparsers.add_parser("shadow-add-demo-data", help="add sanitized demo shadow records")
    subparsers.add_parser("pilot-report", help="generate pilot readiness report")
    subparsers.add_parser("demo-script", help="print demo script location and walkthrough")
    subparsers.add_parser("rollout-plan", help="print rollout plan")
    subparsers.add_parser("pilot-scorecard", help="print pilot readiness scorecard")
    export_parser = subparsers.add_parser("export-enterprise", help="generate enterprise gateway templates")
    export_parser.add_argument("--target", choices=["litellm", "gateway", "all"], default="all")

    args = parser.parse_args(argv)
    if args.command == "route":
        output_format = "json" if args.json_output else args.format
        result = route(
            project_name=args.project,
            task_description=args.task,
            files_touched=args.files,
            previous_failure_count=args.failures,
            live_prod=True if args.live_prod else None,
            sensitive=True if args.sensitive else None,
            output_format=output_format,
            session_id=args.session_id,
            profile_name=args.profile,
            cost_quality_tradeoff=args.cost_quality_tradeoff,
            allowed_models=args.allowed_models,
        )
        print(json.dumps(result, indent=2) if output_format == "json" else _format_text(result))
    elif args.command == "context":
        result = route(
            project_name=args.project,
            task_description=args.task,
            files_touched=args.files,
            session_id=args.session_id,
            profile_name=args.profile,
            cost_quality_tradeoff=args.cost_quality_tradeoff,
            allowed_models=args.allowed_models,
        )
        pack = result["context_pack"]
        print(json.dumps(pack, indent=2) if args.json_output else format_context_pack(pack))
    elif args.command == "packet":
        packet = generate_packet(
            project_name=args.project,
            task_description=args.task,
            files_touched=args.files,
            previous_failure_count=args.failures,
            live_prod=True if args.live_prod else None,
            session_id=args.session_id,
            profile_name=args.profile,
            cost_quality_tradeoff=args.cost_quality_tradeoff,
            allowed_models=args.allowed_models,
        )
        print(json.dumps(packet, indent=2) if args.json_output else format_packet(packet))
    elif args.command == "normalize":
        normalized = normalize_task(args.task, args.files, previous_failure_count=args.failures)
        print(json.dumps(normalized, indent=2) if args.json_output else _format_normalized(normalized))
    elif args.command == "contract":
        contract = generate_contract(
            project_name=args.project,
            task_description=args.task,
            files_touched=args.files,
            previous_failure_count=args.failures,
            live_prod=True if args.live_prod else None,
            profile_name=args.profile,
        )
        if args.output:
            path = Path(args.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(contract, indent=2), encoding="utf-8")
        print(json.dumps(contract, indent=2) if args.json_output else format_contract(contract))
    elif args.command == "check-contract":
        result = check_contract(
            load_contract_file(args.contract_file),
            changed_files=args.changed_files,
            diff_summary=args.diff_summary,
            added_dependencies=args.added_dependencies,
        )
        print(json.dumps(result, indent=2) if args.json_output else format_scope_check(result))
        return 1 if result["decision"] == "fail" else 0
    elif args.command == "review-diff":
        result = review_diff(
            project_name=args.project,
            task_description=args.task,
            run_contract=load_contract_file(args.contract_file) if args.contract_file else None,
            changed_files=args.changed_files,
            git_diff=Path(args.diff_file).read_text(encoding="utf-8"),
            added_dependencies=args.added_dependencies,
            tests_run=args.tests_run,
            live_prod=True if args.live_prod else None,
        )
        print(json.dumps(result, indent=2) if args.json_output else format_diff_review(result))
    elif args.command == "review-current-diff":
        result = review_current_diff(
            project_name=args.project,
            task_description=args.task,
            run_contract=load_contract_file(args.contract_file) if args.contract_file else None,
            added_dependencies=args.added_dependencies,
            tests_run=args.tests_run,
            live_prod=True if args.live_prod else None,
            cwd=Path.cwd(),
        )
        print(json.dumps(result, indent=2) if args.json_output else format_diff_review(result))
    elif args.command == "eval":
        summary = evaluate_tasks()
        print(format_summary(summary))
        return 1 if summary["failed"] else 0
    elif args.command == "feedback":
        record = save_feedback(
            route_id=args.route_id,
            accepted=args.accepted,
            task_succeeded=args.task_succeeded,
            actual_model=args.actual_model,
            recommendation_fit=args.recommendation_fit,
            notes=args.notes,
        )
        print(f"Saved feedback for {record['project_name']} ({record['recommended_tier']}).")
    elif args.command == "outcomes":
        print(format_outcomes_summary(summarize_outcomes()))
    elif args.command == "sessions":
        print(format_session_summary(summarize_sessions()))
    elif args.command == "traces":
        print(format_traces_summary(summarize_traces()))
    elif args.command == "export-langsmith-files":
        result = export_langsmith_files()
        print(f"Exported LangSmith app files to {result['export_folder']}")
        for path in result["files"].values():
            print(f"- {path}")
    elif args.command == "observability-status":
        print(format_observability_status(observability_status()))
    elif args.command == "validate-config":
        result = validate_config()
        print(format_validation(result))
        return 0 if result["ok"] else 1
    elif args.command == "config-summary":
        print(format_config_summary(config_summary()))
    elif args.command == "export-config":
        result = export_config(Path(args.output))
        print(f"Exported config bundle to {result['output']}")
    elif args.command == "import-config":
        result = import_config(Path(args.input), dry_run=not args.apply, apply=args.apply)
        print("Import dry run passed." if not result["applied"] else f"Imported config. Backup: {result['backup']}")
    elif args.command == "list-scenarios":
        print("\n".join(list_scenarios()))
    elif args.command == "simulate":
        result = run_scenario(args.scenario)
        print(json.dumps(result, indent=2) if args.json_output else format_simulation(result))
    elif args.command == "api-contract":
        print(format_contract_summary())
    elif args.command == "export-devspace-contract":
        result = export_devspace_contract()
        print(f"Exported DevSpace contract files to {result['export_folder']}")
        for path in result["files"].values():
            print(f"- {path}")
    elif args.command == "integration-test":
        result = integration_self_test()
        print(f"Integration contract checks: {'pass' if result['ok'] else 'fail'}")
        print(f"Checked requests: {result['checked']}")
        if result["failures"]:
            print(json.dumps(result["failures"], indent=2))
        return 0 if result["ok"] else 1
    elif args.command == "shadow-summary":
        print(format_shadow_summary(summarize_shadow_runs()))
    elif args.command == "export-shadow-report":
        result = export_shadow_report()
        print(f"Exported shadow mode report to {result['export_folder']}")
        for path in result["files"].values():
            print(f"- {path}")
    elif args.command == "shadow-add-demo-data":
        records = add_demo_data()
        print(f"Added {len(records)} sanitized demo shadow records.")
    elif args.command == "pilot-report":
        result = export_pilot_report()
        print(f"Exported pilot readiness report to {result['export_folder']}")
        for path in result["files"].values():
            print(f"- {path}")
    elif args.command == "demo-script":
        print("Demo script: docs/demo_script.md")
        print(demo_script_text())
    elif args.command == "rollout-plan":
        print(rollout_plan_text())
    elif args.command == "pilot-scorecard":
        print(format_scorecard(pilot_scorecard()))
    elif args.command == "export-enterprise":
        print(format_export_result(export_enterprise(args.target)))
    return 0


def _add_routing_controls(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--session-id")
    parser.add_argument("--profile", default="balanced")
    parser.add_argument("--cost-quality-tradeoff", type=int)
    parser.add_argument("--allowed-models", nargs="*")


def _format_text(result: dict[str, Any]) -> str:
    review = "yes" if result["human_review_required"] else "no"
    sticky = "yes" if result["sticky_route_used"] else "no"
    rules = "\n".join(f"  - {rule}" for rule in result["matched_rules"])
    return "\n".join(
        [
            f"Recommended model: {result['recommended_model']}",
            f"Route ID: {result['route_id']}",
            f"Selected alias: {result['selected_model_alias']}",
            f"Selected model: {result['selected_model']}",
            f"Fallback candidates: {', '.join(result['fallback_candidates'])}",
            f"Profile: {result['profile_name']} (cost/quality {result['cost_quality_tradeoff']})",
            f"Sticky route used: {sticky}",
            f"Previous model: {result['previous_model'] or 'none'}",
            f"Tier: {result['model_tier']}",
            f"Effort: {result['effort_level']}",
            f"Risk: {result['risk_level']}",
            f"Human review required: {review}",
            f"Normalized task: {result['normalized_task']['normalized_summary']}",
            f"Intrinsic task risk: {result['intrinsic_task_risk']}",
            f"Detected capabilities: {', '.join(result['requested_capabilities']) or 'none'}",
            f"Operation type: {result['operation_type']}",
            f"Minimum recommended tier: {result['minimum_recommended_tier']}",
            f"Task ambiguity warnings: {', '.join(result['task_ambiguity_warnings']) or 'none'}",
            f"False-positive controls: {', '.join(result['false_positive_controls_triggered']) or 'none'}",
            f"Reason: {result['reason']}",
            f"Context policy: {result['context_policy']}",
            "Context pack:",
            _indent(format_context_pack(result["context_pack"])),
            f"Escalation policy: {result['escalation_policy']}",
            "Matched rules:",
            rules,
        ]
    )


def _format_normalized(result: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Task: {result['normalized_summary']}",
            f"Task type: {result['task_type']}",
            f"Operation type: {result['operation_type']}",
            f"Capabilities: {', '.join(result['requested_capabilities']) or 'none'}",
            f"Intrinsic risk: {result['intrinsic_risk']}",
            f"Complexity: {result['complexity']}",
            f"Minimum tier: {result['minimum_recommended_tier']}",
            f"Human review recommended: {result['human_review_recommended']}",
            f"Ambiguity warnings: {', '.join(result['ambiguity_warnings']) or 'none'}",
            f"False-positive controls: {', '.join(result['false_positive_controls_triggered']) or 'none'}",
            f"Reason: {result['risk_reason']}",
        ]
    )


def _bool_arg(value: str) -> bool:
    if value.casefold() == "true":
        return True
    if value.casefold() == "false":
        return False
    raise argparse.ArgumentTypeError("must be true or false")


def _unknown_bool_arg(value: str) -> bool | None:
    if value.casefold() == "unknown":
        return None
    return _bool_arg(value)


def _indent(text: str) -> str:
    return "\n".join(f"  {line}" for line in text.splitlines())


if __name__ == "__main__":
    raise SystemExit(main())
