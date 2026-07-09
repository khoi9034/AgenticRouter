from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentic_router.web import HOST, make_server


PORTS = range(8765, 8770)


def main() -> int:
    last_error = None
    for port in PORTS:
        try:
            server = make_server(port=port)
        except OSError as exc:
            last_error = exc
            continue
        with server:
            print(f"DevSpace Smart Router running at http://{HOST}:{port}")
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                print("\nServer stopped.")
                return 0
    print(f"No available port found in 8765-8769. Last error: {last_error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
