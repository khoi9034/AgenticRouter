from __future__ import annotations

import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .evaluator import evaluate_tasks
from .projects import load_projects
from .router import route

HOST = "127.0.0.1"
PORT = 8765
WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class RouterHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def do_GET(self) -> None:
        if self.path == "/api/projects":
            self._json({"projects": load_projects()})
        elif self.path == "/api/eval":
            self._json(evaluate_tasks())
        else:
            if self.path == "/":
                self.path = "/index.html"
            super().do_GET()

    def do_POST(self) -> None:
        if self.path != "/api/route":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        try:
            payload = self._read_json()
            result = route(
                project_name=str(payload["project_name"]),
                task_description=str(payload["task_description"]),
                files_touched=_files(payload.get("files_touched", [])),
                previous_failure_count=int(payload.get("previous_failure_count", 0)),
                live_prod=True if payload.get("live_prod") is True else None,
            )
        except (KeyError, TypeError, ValueError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        self._json(result)

    def log_message(self, format: str, *args: Any) -> None:
        return

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


def make_server(host: str = HOST, port: int = PORT) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), RouterHandler)


def main() -> int:
    with make_server() as server:
        print(f"DevSpace Smart Router running at http://{HOST}:{PORT}")
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

