import os
import tempfile
import unittest
from pathlib import Path

from agentic_router.autogate import clear_runs, complete_run, get_run, list_runs, start_run
from agentic_router.integration import handle_autogate_complete, handle_autogate_list, handle_autogate_start


CSS_DIFF = Path("examples/css_only.diff").read_text(encoding="utf-8")
AUTH_DIFF = Path("examples/auth_change.diff").read_text(encoding="utf-8")
SQL_DIFF = Path("examples/sql_migration.diff").read_text(encoding="utf-8")


class AutoGateTests(unittest.TestCase):
    def setUp(self):
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

    def test_low_risk_css_can_auto_approve(self):
        run = start_run("Diana Test Project", "Make hello world page prettier")
        result = complete_run(run["run_id"], ["style.css"], CSS_DIFF)

        self.assertEqual(result["final_decision"], "auto_approved")

    def test_forbidden_auth_file_auto_blocks(self):
        run = start_run("Random Test App", "Change login button color")
        result = complete_run(run["run_id"], ["Auth/require_auth.php"], CSS_DIFF)

        self.assertEqual(result["final_decision"], "auto_blocked")

    def test_secret_diff_auto_blocks(self):
        run = start_run("Random Test App", "Change login button color")
        diff = """diff --git a/login.html b/login.html
--- a/login.html
+++ b/login.html
@@ -0,0 +1 @@
+token = "REDACTED_PLACEHOLDER"
"""
        result = complete_run(run["run_id"], ["login.html"], diff)

        self.assertEqual(result["final_decision"], "auto_blocked")

    def test_auth_bypass_auto_blocks(self):
        run = start_run("Random Test App", "Change login button color")
        result = complete_run(run["run_id"], ["login.html"], AUTH_DIFF)

        self.assertEqual(result["final_decision"], "auto_blocked")

    def test_sql_migration_without_tests_needs_tests(self):
        run = start_run("Random Test App", "Build login and database")
        result = complete_run(run["run_id"], ["database/001_create_users.sql"], SQL_DIFF)

        self.assertEqual(result["final_decision"], "needs_tests")

    def test_high_risk_clean_run_with_tests_can_auto_approve(self):
        run = start_run("Random Test App", "Build login, roles, SQL database, and admin dashboard")
        diff = """diff --git a/Auth/login.php b/Auth/login.php
--- a/Auth/login.php
+++ b/Auth/login.php
@@ -0,0 +1 @@
+function render_login_form() {}
"""
        result = complete_run(run["run_id"], ["Auth/login.php"], diff, tests_run=["unit tests"], test_status="passed")

        self.assertEqual(result["final_decision"], "auto_approved")

    def test_failed_tests_need_retry(self):
        run = start_run("Diana Test Project", "Make hello world page prettier")
        result = complete_run(run["run_id"], ["style.css"], CSS_DIFF, tests_run=["css smoke"], test_status="failed")

        self.assertEqual(result["final_decision"], "needs_retry")

    def test_live_prod_without_rollback_requires_rollback(self):
        run = start_run("Diana Test Project", "Make hello world page prettier", live_prod=True)
        result = complete_run(run["run_id"], ["style.css"], CSS_DIFF, tests_run=["smoke"], test_status="passed")

        self.assertEqual(result["final_decision"], "rollback_required")

    def test_missing_high_risk_evidence_needs_more_evidence(self):
        run = start_run("Random Test App", "Build login and database")
        result = complete_run(run["run_id"], [], "", tests_run=["unit tests"], test_status="passed")

        self.assertEqual(result["final_decision"], "needs_more_evidence")

    def test_scope_guard_fail_cannot_be_downgraded(self):
        run = start_run("Random Test App", "Change login button color")
        result = complete_run(run["run_id"], ["Auth/require_auth.php"], CSS_DIFF, tests_run=["smoke"], test_status="passed")

        self.assertEqual(result["final_decision"], "auto_blocked")

    def test_diff_review_fail_cannot_be_downgraded(self):
        run = start_run("Random Test App", "Change login button color")
        result = complete_run(run["run_id"], ["login.html"], AUTH_DIFF, tests_run=["smoke"], test_status="passed")

        self.assertEqual(result["final_decision"], "auto_blocked")

    def test_report_list_clear_and_api_handlers(self):
        started = handle_autogate_start({"project_name": "Diana Test Project", "task_description": "Make hello world page prettier"})
        run_id = started["autogate"]["run_id"]
        completed = handle_autogate_complete({"run_id": run_id, "changed_files": ["style.css"], "git_diff": CSS_DIFF})

        self.assertEqual(completed["autogate"]["final_decision"], "auto_approved")
        self.assertEqual(get_run(run_id)["run_id"], run_id)
        self.assertEqual(len(list_runs()), 1)
        self.assertEqual(len(handle_autogate_list()["runs"]), 1)
        self.assertTrue(clear_runs()["cleared"])
        self.assertEqual(list_runs(), [])


if __name__ == "__main__":
    unittest.main()
