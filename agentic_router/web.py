from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from .config_studio import EXPORT_CONFIG_DEFAULT, add_project, export_config
from .config_validation import config_summary, validate_config
from .evaluator import evaluate_tasks
from .integration import (
    handle_autogate_clear,
    handle_autogate_complete,
    handle_autogate_complete_auto,
    handle_autogate_list,
    handle_autogate_report,
    handle_autogate_start,
    handle_contract_check_request,
    handle_contract_request,
    handle_current_diff_review_request,
    handle_diff_review_request,
    handle_evidence_collect,
    handle_evidence_plan,
    handle_request,
    health,
    load_contract,
    version,
)
from .observability import export_file_list, observability_status, summarize_traces
from .outcomes import save_feedback, summarize_outcomes
from .packets import generate_packet, packet_from_route
from .pilot import demo_script_text, export_pilot_report, pilot_scorecard, rollout_plan_text
from .projects import load_projects
from .router import route
from .sessions import summarize_sessions
from .shadow import export_shadow_report, summarize_shadow_runs
from .simulator import list_scenarios, run_scenario

HOST = "127.0.0.1"
PORT = 8765
WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class RouterHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def do_GET(self) -> None:
        if self.path == "/api/projects":
            self._json({"projects": load_projects()})
        elif self.path == "/api/health":
            self._json(health())
        elif self.path == "/api/version":
            self._json(version())
        elif self.path == "/api/contracts":
            self._json(load_contract())
        elif self.path == "/api/v1/autogate/list":
            self._json(handle_autogate_list())
        elif self.path == "/api/eval":
            self._json(evaluate_tasks())
        elif self.path == "/api/outcomes":
            self._json(summarize_outcomes())
        elif self.path == "/api/sessions":
            self._json(summarize_sessions())
        elif self.path == "/api/observability":
            self._json(
                {
                    "status": observability_status(),
                    "summary": summarize_traces(),
                    "export_files": export_file_list(),
                }
            )
        elif self.path == "/api/config/summary":
            self._json(config_summary())
        elif self.path == "/api/config/validate":
            self._json(validate_config())
        elif self.path == "/api/config/export":
            self._json(export_config(EXPORT_CONFIG_DEFAULT))
        elif self.path == "/api/config/eval":
            self._json(evaluate_tasks())
        elif self.path == "/api/scenarios":
            self._json({"scenarios": list_scenarios()})
        elif self.path == "/api/shadow/summary":
            self._json(summarize_shadow_runs())
        elif self.path == "/api/shadow/report":
            self._json(export_shadow_report())
        elif self.path == "/api/pilot/scorecard":
            self._json(pilot_scorecard())
        elif self.path == "/api/pilot/report":
            self._json(export_pilot_report())
        elif self.path == "/api/pilot/demo-script":
            self._json({"path": "docs/demo_script.md", "content": demo_script_text()})
        elif self.path == "/api/pilot/rollout-plan":
            self._json({"path": "docs/rollout_plan.md", "content": rollout_plan_text()})
        elif self.path.startswith("/exports/"):
            self._serve_export()
        else:
            if self.path == "/":
                self.path = "/index.html"
            super().do_GET()

    def do_POST(self) -> None:
        if self.path == "/api/route":
            self._handle_route()
        elif self.path == "/api/v1/route":
            self._handle_integration()
        elif self.path == "/api/v1/packet":
            self._handle_integration("packet")
        elif self.path == "/api/v1/contract":
            self._handle_integration_contract()
        elif self.path == "/api/v1/contract/check":
            self._handle_integration_contract_check()
        elif self.path == "/api/v1/diff-review":
            self._handle_diff_review()
        elif self.path == "/api/v1/diff-review/current":
            self._handle_current_diff_review()
        elif self.path == "/api/v1/autogate/start":
            self._handle_autogate_start()
        elif self.path == "/api/v1/autogate/complete":
            self._handle_autogate_complete()
        elif self.path == "/api/v1/autogate/complete-auto":
            self._handle_autogate_complete_auto()
        elif self.path == "/api/v1/autogate/report":
            self._handle_autogate_report()
        elif self.path == "/api/v1/autogate/list":
            self._json(handle_autogate_list())
        elif self.path == "/api/v1/autogate/clear":
            self._json(handle_autogate_clear())
        elif self.path == "/api/v1/shadow":
            self._handle_integration("shadow")
        elif self.path == "/api/v1/strict-check":
            self._handle_integration("strict")
        elif self.path == "/api/v1/evidence/plan":
            self._handle_evidence_plan()
        elif self.path == "/api/v1/evidence/collect":
            self._handle_evidence_collect()
        elif self.path == "/api/context":
            self._handle_context()
        elif self.path == "/api/packet":
            self._handle_packet()
        elif self.path == "/api/feedback":
            self._handle_feedback()
        elif self.path == "/api/config/add-project":
            self._handle_add_project()
        elif self.path == "/api/simulate":
            self._handle_simulate()
        else:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _handle_route(self) -> None:
        try:
            payload = self._read_json()
            result = route(
                project_name=str(payload["project_name"]),
                task_description=str(payload["task_description"]),
                files_touched=_files(payload.get("files_touched", [])),
                previous_failure_count=int(payload.get("previous_failure_count", 0)),
                live_prod=True if payload.get("live_prod") is True else None,
                **_routing_options(payload),
            )
        except (KeyError, TypeError, ValueError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        result["run_packet"] = packet_from_route(
            str(payload["project_name"]),
            str(payload["task_description"]),
            _files(payload.get("files_touched", [])),
            result,
        )
        result["run_contract"] = result["run_packet"]["run_contract"]
        self._json(result)

    def _handle_integration(self, forced_mode: str | None = None) -> None:
        try:
            self._json(handle_request(self._read_json(), forced_mode=forced_mode))
        except (KeyError, TypeError, ValueError) as exc:
            self._json({"error": str(exc), "contract_version": "v1"}, HTTPStatus.BAD_REQUEST)

    def _handle_context(self) -> None:
        try:
            payload = self._read_json()
            result = route(
                project_name=str(payload["project_name"]),
                task_description=str(payload["task_description"]),
                files_touched=_files(payload.get("files_touched", [])),
                previous_failure_count=int(payload.get("previous_failure_count", 0)),
                live_prod=True if payload.get("live_prod") is True else None,
                **_routing_options(payload),
            )
        except (KeyError, TypeError, ValueError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        self._json(result["context_pack"])

    def _handle_packet(self) -> None:
        try:
            payload = self._read_json()
            packet = generate_packet(
                project_name=str(payload["project_name"]),
                task_description=str(payload["task_description"]),
                files_touched=_files(payload.get("files_touched", [])),
                previous_failure_count=int(payload.get("previous_failure_count", 0)),
                live_prod=True if payload.get("live_prod") is True else None,
                **_routing_options(payload),
            )
        except (KeyError, TypeError, ValueError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        self._json(packet)

    def _handle_integration_contract(self) -> None:
        try:
            self._json(handle_contract_request(self._read_json()))
        except (KeyError, TypeError, ValueError) as exc:
            self._json({"error": str(exc), "contract_version": "v1"}, HTTPStatus.BAD_REQUEST)

    def _handle_integration_contract_check(self) -> None:
        try:
            self._json(handle_contract_check_request(self._read_json()))
        except (KeyError, TypeError, ValueError) as exc:
            self._json({"error": str(exc), "contract_version": "v1"}, HTTPStatus.BAD_REQUEST)

    def _handle_diff_review(self) -> None:
        try:
            self._json(handle_diff_review_request(self._read_json()))
        except (KeyError, TypeError, ValueError) as exc:
            self._json({"error": str(exc), "contract_version": "v1"}, HTTPStatus.BAD_REQUEST)

    def _handle_current_diff_review(self) -> None:
        try:
            self._json(handle_current_diff_review_request(self._read_json(), cwd=WEB_DIR.parent))
        except (KeyError, TypeError, ValueError) as exc:
            self._json({"error": str(exc), "contract_version": "v1"}, HTTPStatus.BAD_REQUEST)

    def _handle_autogate_start(self) -> None:
        try:
            self._json(handle_autogate_start(self._read_json()))
        except (KeyError, TypeError, ValueError) as exc:
            self._json({"error": str(exc), "contract_version": "v1"}, HTTPStatus.BAD_REQUEST)

    def _handle_autogate_complete(self) -> None:
        try:
            self._json(handle_autogate_complete(self._read_json()))
        except (KeyError, TypeError, ValueError) as exc:
            self._json({"error": str(exc), "contract_version": "v1"}, HTTPStatus.BAD_REQUEST)

    def _handle_autogate_complete_auto(self) -> None:
        try:
            self._json(handle_autogate_complete_auto(self._read_json()))
        except (KeyError, TypeError, ValueError) as exc:
            self._json({"error": str(exc), "contract_version": "v1"}, HTTPStatus.BAD_REQUEST)

    def _handle_evidence_plan(self) -> None:
        try:
            self._json(handle_evidence_plan(self._read_json()))
        except (KeyError, TypeError, ValueError) as exc:
            self._json({"error": str(exc), "contract_version": "v1"}, HTTPStatus.BAD_REQUEST)

    def _handle_evidence_collect(self) -> None:
        try:
            self._json(handle_evidence_collect(self._read_json()))
        except (KeyError, TypeError, ValueError) as exc:
            self._json({"error": str(exc), "contract_version": "v1"}, HTTPStatus.BAD_REQUEST)

    def _handle_autogate_report(self) -> None:
        try:
            self._json(handle_autogate_report(self._read_json()))
        except (KeyError, TypeError, ValueError) as exc:
            self._json({"error": str(exc), "contract_version": "v1"}, HTTPStatus.BAD_REQUEST)

    def _handle_feedback(self) -> None:
        try:
            payload = self._read_json()
            record = save_feedback(
                route_id=str(payload["route_id"]),
                accepted=_bool(payload["accepted"]),
                task_succeeded=_optional_bool(payload["task_succeeded"]),
                actual_model=str(payload["actual_model"]),
                recommendation_fit=str(payload["recommendation_fit"]),
                notes=str(payload.get("notes", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        self._json({"saved": True, "record": record})

    def _handle_add_project(self) -> None:
        try:
            record = add_project(self._read_json())
        except (KeyError, TypeError, ValueError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        self._json(record)

    def _handle_simulate(self) -> None:
        try:
            payload = self._read_json()
            result = run_scenario(str(payload["scenario"]))
        except (KeyError, TypeError, ValueError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        self._json(result)

    def _serve_export(self) -> None:
        root = WEB_DIR.parent / "exports"
        requested = (WEB_DIR.parent / unquote(self.path.lstrip("/"))).resolve()
        if root.resolve() not in requested.parents or not requested.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = _content_type(requested.suffix)
        body = requested.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            raise ValueError("JSON body is required")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _files(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.replace(",", "\n").splitlines() if item.strip()]
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    raise ValueError("files_touched must be a list or string")


def _content_type(suffix: str) -> str:
    return {
        ".csv": "text/csv; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".jsonl": "application/jsonl; charset=utf-8",
        ".md": "text/markdown; charset=utf-8",
        ".yaml": "text/yaml; charset=utf-8",
        ".yml": "text/yaml; charset=utf-8",
    }.get(suffix, "text/plain; charset=utf-8")


def _routing_options(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": _optional_text(payload.get("session_id")),
        "profile_name": str(payload.get("profile_name") or payload.get("profile") or "balanced"),
        "cost_quality_tradeoff": _optional_int(payload.get("cost_quality_tradeoff")),
        "allowed_models": _optional_list(payload.get("allowed_models")),
    }


def _optional_text(value: Any) -> str | None:
    text = "" if value is None else str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    return None if value in (None, "") else int(value)


def _optional_list(value: Any) -> list[str] | None:
    if value in (None, "", []):
        return None
    return _files(value)


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError("value must be true or false")


def _optional_bool(value: Any) -> bool | None:
    return None if value is None else _bool(value)


def make_server(host: str = HOST, port: int = PORT) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), RouterHandler)


def main() -> int:
    port = int(os.environ.get("AGENTIC_ROUTER_PORT", PORT))
    with make_server(port=port) as server:
        print(f"DevSpace Smart Router running at http://{HOST}:{port}")
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
