import os
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

from agentic_router.evidence import (
    build_validation_plan,
    collect_git_evidence,
    complete_run_with_evidence,
    is_safe_validation_command,
    run_command,
)
from agentic_router.autogate import start_run
from agentic_router.integration import handle_autogate_complete_auto, handle_evidence_collect, handle_evidence_plan


class EvidenceRunnerTests(unittest.TestCase):
    def setUp(self):
        if shutil.which("git") is None:
            self.skipTest("git is required for evidence tests")
        self.tmp = tempfile.TemporaryDirectory()
        self.old_runs = os.environ.get("AGENTIC_ROUTER_RUN_RECORDS")
        self.old_traces = os.environ.get("AGENTIC_ROUTER_TRACES")
        os.environ["AGENTIC_ROUTER_RUN_RECORDS"] = str(Path(self.tmp.name) / "run_records.jsonl")
        os.environ["AGENTIC_ROUTER_TRACES"] = str(Path(self.tmp.name) / "traces.jsonl")

    def tearDown(self):
        if self.old_runs is None:
            os.environ.pop("AGENTIC_ROUTER_RUN_RECORDS", None)
        else:
            os.environ["AGENTIC_ROUTER_RUN_RECORDS"] = self.old_runs
        if self.old_traces is None:
            os.environ.pop("AGENTIC_ROUTER_TRACES", None)
        else:
            os.environ["AGENTIC_ROUTER_TRACES"] = self.old_traces
        self.tmp.cleanup()

    def test_git_evidence_collector_handles_clean_repo(self):
        repo = self._repo()

        evidence = collect_git_evidence(repo)

        self.assertEqual(evidence["changed_files"], [])
        self.assertEqual(evidence["git_diff"], "")

    def test_git_evidence_collector_handles_changed_files(self):
        repo = self._repo()
        self._tracked(repo, "style.css", "body { color: black; }\n")
        (repo / "style.css").write_text("body { color: blue; }\n", encoding="utf-8")

        evidence = collect_git_evidence(repo)

        self.assertIn("style.css", evidence["changed_files"])
        self.assertIn("color: blue", evidence["git_diff"])

    def test_validation_plan_detects_python_project(self):
        repo = self._repo()
        (repo / "pyproject.toml").write_text("[project]\nname='sample'\n", encoding="utf-8")
        (repo / "tests").mkdir()
        (repo / "app.py").write_text("print('ok')\n", encoding="utf-8")
        plan = build_validation_plan(self._record("medium"), repo, ["app.py"])

        self.assertIn("python", plan["project_types"])
        self.assertIn("python_unittest", [item["name"] for item in plan["commands"]])
        self.assertIn("python_compile", [item["name"] for item in plan["commands"]])

    def test_validation_plan_detects_npm_project(self):
        repo = self._repo()
        (repo / "package.json").write_text('{"scripts":{"test":"node --check app.js","lint":"node --check app.js"}}', encoding="utf-8")

        plan = build_validation_plan(self._record("medium"), repo, ["app.js"])

        self.assertIn("npm", plan["project_types"])
        self.assertIn("npm_test", [item["name"] for item in plan["commands"]])
        self.assertIn("npm_lint", [item["name"] for item in plan["commands"]])

    def test_validation_plan_detects_php_files(self):
        repo = self._repo()
        (repo / "index.php").write_text("<?php echo 'ok';\n", encoding="utf-8")

        plan = build_validation_plan(self._record("high"), repo, ["index.php"])

        self.assertIn("php", plan["project_types"])
        self.assertIn("php_lint_index.php", [item["name"] for item in plan["commands"]])

    def test_validation_plan_detects_static_without_heavy_tests(self):
        repo = self._repo()
        plan = build_validation_plan(self._record("low"), repo, ["index.html", "style.css"])

        self.assertIn("static", plan["project_types"])
        self.assertTrue(plan["static_only"])
        self.assertFalse(plan["requires_validation"])
        self.assertEqual(plan["commands"], [])

    def test_unsafe_commands_are_rejected(self):
        self.assertFalse(is_safe_validation_command(["npm", "install"]))
        self.assertFalse(is_safe_validation_command(["python", "-m", "pip", "install", "x"]))
        self.assertFalse(is_safe_validation_command(["deploy", "production"]))

    def test_command_runner_times_out_without_shell(self):
        repo = self._repo()
        (repo / "tests").mkdir()
        (repo / "tests" / "test_slow.py").write_text("import time\nimport unittest\nclass T(unittest.TestCase):\n    def test_slow(self):\n        time.sleep(3)\n", encoding="utf-8")

        result = run_command(["python", "-m", "unittest", "discover", "-s", "tests"], repo, timeout=1)

        self.assertEqual(result["status"], "timed_out")

    def test_passing_validation_returns_passed(self):
        repo = self._repo()
        self._python_project(repo, "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n")
        self._tracked(repo, "app.py", "VALUE = 1\n")
        (repo / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
        run = start_run("Random Test App", "Create CSV import with duplicate handling", files_touched=["app.py"])

        result = complete_run_with_evidence(run["run_id"], repo)

        self.assertEqual(result["evidence"]["tests_status"], "passed")

    def test_failing_validation_returns_failed(self):
        repo = self._repo()
        self._python_project(repo, "import unittest\nclass T(unittest.TestCase):\n    def test_bad(self):\n        self.assertTrue(False)\n")
        self._tracked(repo, "app.py", "VALUE = 1\n")
        (repo / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
        run = start_run("Random Test App", "Create CSV import with duplicate handling", files_touched=["app.py"])

        result = complete_run_with_evidence(run["run_id"], repo)

        self.assertEqual(result["evidence"]["tests_status"], "failed")
        self.assertEqual(result["final_decision"], "needs_retry")

    def test_missing_command_returns_skipped_or_unavailable(self):
        repo = self._repo()
        result = run_command(["definitely_missing_tool_for_agentic_router", "--version"], repo)

        self.assertIn(result["status"], {"skipped", "unavailable"})

    def test_high_risk_unavailable_validation_needs_tests(self):
        repo = self._repo()
        self._tracked(repo, "database/001_create_users.sql", "create table users (id int);\n")
        (repo / "database" / "001_create_users.sql").write_text("create table users (id int, role text);\n", encoding="utf-8")
        run = start_run("Random Test App", "Build login and database", files_touched=["database/001_create_users.sql"])

        result = complete_run_with_evidence(run["run_id"], repo)

        self.assertIn(result["final_decision"], {"needs_tests", "needs_more_evidence"})

    def test_low_risk_css_can_auto_approve(self):
        repo = self._repo()
        self._tracked(repo, "style.css", "body { color: black; }\n")
        (repo / "style.css").write_text("body { color: blue; }\n", encoding="utf-8")
        run = start_run("Diana Test Project", "Make hello world page prettier", files_touched=["style.css"])

        result = complete_run_with_evidence(run["run_id"], repo)

        self.assertEqual(result["final_decision"], "auto_approved")

    def test_secret_diff_auto_blocks_even_if_tests_pass(self):
        repo = self._repo()
        self._python_project(repo, "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n")
        self._tracked(repo, "login.html", "<button>Login</button>\n")
        (repo / "login.html").write_text('<button>Login</button>\n<script>token = "REDACTED_PLACEHOLDER"</script>\n', encoding="utf-8")
        run = start_run("Random Test App", "Change login button color", files_touched=["login.html"])

        result = complete_run_with_evidence(run["run_id"], repo)

        self.assertEqual(result["evidence"]["tests_status"], "passed")
        self.assertEqual(result["final_decision"], "auto_blocked")

    def test_integration_handlers_return_evidence(self):
        repo = self._repo()
        self._tracked(repo, "style.css", "body { color: black; }\n")
        (repo / "style.css").write_text("body { color: blue; }\n", encoding="utf-8")
        run = start_run("Diana Test Project", "Make hello world page prettier", files_touched=["style.css"])

        plan = handle_evidence_plan({"run_id": run["run_id"], "repo_path": str(repo)})
        evidence = handle_evidence_collect({"run_id": run["run_id"], "repo_path": str(repo)})
        completed = handle_autogate_complete_auto({"run_id": run["run_id"], "repo_path": str(repo)})

        self.assertEqual(plan["contract_version"], "v1")
        self.assertIn("evidence", evidence)
        self.assertEqual(completed["final_decision"], "auto_approved")

    def _repo(self) -> Path:
        repo = Path(self.tmp.name) / uuidish()
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, text=True, capture_output=True, check=True)
        return repo

    def _tracked(self, repo: Path, path: str, content: str) -> None:
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", path], cwd=repo, text=True, capture_output=True, check=True)

    def _python_project(self, repo: Path, test_content: str) -> None:
        (repo / "pyproject.toml").write_text("[project]\nname='sample'\n", encoding="utf-8")
        (repo / "tests").mkdir(exist_ok=True)
        (repo / "tests" / "test_sample.py").write_text(test_content, encoding="utf-8")
        (repo / ".git" / "info" / "exclude").write_text("pyproject.toml\ntests/\n", encoding="utf-8")

    def _record(self, risk: str) -> dict:
        return {"run_id": "run_test", "risk_level": risk, "files_touched": [], "live_prod": False}


def uuidish() -> str:
    return uuid.uuid4().hex


if __name__ == "__main__":
    unittest.main()
