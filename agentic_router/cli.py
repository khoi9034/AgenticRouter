from __future__ import annotations

import argparse
import json
from typing import Any

from .context import format_context_pack
from .enterprise import export_enterprise, format_export_result
from .evaluator import evaluate_tasks, format_summary
from .observability import (
    export_langsmith_files,
    format_observability_status,
    format_traces_summary,
    observability_status,
    summarize_traces,
)
from .outcomes import format_outcomes_summary, save_feedback, summarize_outcomes
from .packets import format_packet, generate_packet
from .router import route
from .sessions import format_session_summary, summarize_sessions


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
            f"Reason: {result['reason']}",
            f"Context policy: {result['context_policy']}",
            "Context pack:",
            _indent(format_context_pack(result["context_pack"])),
            f"Escalation policy: {result['escalation_policy']}",
            "Matched rules:",
            rules,
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
