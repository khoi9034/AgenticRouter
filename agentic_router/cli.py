from __future__ import annotations

import argparse
import json
from typing import Any

from .context import format_context_pack
from .enterprise import export_enterprise, format_export_result
from .evaluator import evaluate_tasks, format_summary
from .outcomes import format_outcomes_summary, save_feedback, summarize_outcomes
from .packets import format_packet, generate_packet
from .router import route


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
    context_parser = subparsers.add_parser("context", help="recommend a context pack")
    context_parser.add_argument("--project", required=True)
    context_parser.add_argument("--task", required=True)
    context_parser.add_argument("--files", nargs="*", default=[])
    context_parser.add_argument("--json", action="store_true", dest="json_output")
    packet_parser = subparsers.add_parser("packet", help="generate a DevSpace run packet")
    packet_parser.add_argument("--project", required=True)
    packet_parser.add_argument("--task", required=True)
    packet_parser.add_argument("--files", nargs="*", default=[])
    packet_parser.add_argument("--failures", type=int, default=0)
    packet_parser.add_argument("--live-prod", action="store_true")
    packet_parser.add_argument("--json", action="store_true", dest="json_output")
    subparsers.add_parser("eval", help="run golden routing evaluation")
    feedback_parser = subparsers.add_parser("feedback", help="save routing outcome feedback")
    feedback_parser.add_argument("--route-id", required=True)
    feedback_parser.add_argument("--accepted", required=True, type=_bool_arg)
    feedback_parser.add_argument("--task-succeeded", required=True, type=_unknown_bool_arg)
    feedback_parser.add_argument("--actual-model", required=True)
    feedback_parser.add_argument("--recommendation-fit", required=True)
    feedback_parser.add_argument("--notes", default="")
    subparsers.add_parser("outcomes", help="summarize routing feedback outcomes")
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
        )
        print(json.dumps(result, indent=2) if output_format == "json" else _format_text(result))
    elif args.command == "context":
        result = route(
            project_name=args.project,
            task_description=args.task,
            files_touched=args.files,
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
    elif args.command == "export-enterprise":
        print(format_export_result(export_enterprise(args.target)))
    return 0


def _format_text(result: dict[str, Any]) -> str:
    review = "yes" if result["human_review_required"] else "no"
    rules = "\n".join(f"  - {rule}" for rule in result["matched_rules"])
    return "\n".join(
        [
            f"Recommended model: {result['recommended_model']}",
            f"Route ID: {result['route_id']}",
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
