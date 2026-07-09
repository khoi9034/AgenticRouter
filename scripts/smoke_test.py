from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


COMMANDS = [
    ("unit tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests"]),
    ("golden eval", [sys.executable, "-m", "agentic_router.cli", "eval"]),
    ("validate config", [sys.executable, "-m", "agentic_router.cli", "validate-config"]),
    ("integration test", [sys.executable, "-m", "agentic_router.cli", "integration-test"]),
    ("pilot scorecard", [sys.executable, "-m", "agentic_router.cli", "pilot-scorecard"]),
]


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env["AGENTIC_ROUTER_TRACES"] = str(Path(tmp) / "traces.jsonl")
        env["AGENTIC_ROUTER_SHADOW_RUNS"] = str(Path(tmp) / "shadow_runs.jsonl")
        env["AGENTIC_ROUTER_OUTCOMES"] = str(Path(tmp) / "outcomes.jsonl")
        for label, command in COMMANDS:
            print(f"== {label} ==")
            completed = subprocess.run(command, cwd=root, env=env, text=True, capture_output=True)
            if completed.stdout:
                print(completed.stdout.rstrip())
            if completed.stderr:
                print(completed.stderr.rstrip())
            results.append((label, completed.returncode))

    print("\nSmoke test summary")
    failed = False
    for label, code in results:
        ok = code == 0
        failed = failed or not ok
        print(f"- {label}: {'PASS' if ok else f'FAIL ({code})'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
