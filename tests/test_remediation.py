import json
import os
import tempfile
import unittest
from pathlib import Path

from agentic_router.autogate import complete_run, start_run
from agentic_router.integration import handle_remediation_plan, handle_retry_packet
from agentic_router.remediation import remediation_for_result, remediation_for_run, remediation_from_file, retry_packet_for_run


CSS_DIFF = Path("examples/css_only.diff").read_text(encoding="utf-8")
AUTH_DIFF = Path("examples/auth_change.diff").read_text(encoding="utf-8")
SQL_DIFF = Path("examples/sql_migration.diff").read_text(encoding="utf-8")


class RemediationTests(unittest.TestCase):
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

    def test_auto_approved_returns_no_action_needed(self):
        result = self._complete_low(CSS_DIFF)

        plan = remediation_for_run(result["run_id"])

        self.assertEqual(plan["next_action"], "no_action_needed")
        self.assertEqual(plan["severity"], "low")

    def test_needs_tests_returns_run_tests_with_validation_commands(self):
        result = self._complete_high_sql()
        wrapped = {
            "autogate": result,
            "evidence": {"validation_plan": {"commands": [{"name": "python_unittest", "command": ["python", "-m", "unittest", "discover", "-s", "tests"], "required": True}]}},
        }

        plan = remediation_for_result(wrapped)

        self.assertEqual(plan["next_action"], "run_tests")
        self.assertTrue(plan["validation_commands"])

    def test_needs_retry_returns_narrow_retry_packet(self):
        result = self._complete_low(CSS_DIFF, tests_run=["css smoke"], test_status="failed")

        plan = remediation_for_run(result["run_id"])

        self.assertEqual(plan["next_action"], "retry_agent")
        self.assertIn("Fix only the failing issue", plan["retry_packet"]["instructions"])
        self.assertIn("Do not expand scope", " ".join(plan["retry_packet"]["instructions"]))

    def test_needs_more_evidence_lists_missing_evidence(self):
        run = start_run("Random Test App", "Build login and database")
        result = complete_run(run["run_id"], [], "", tests_run=["unit tests"], test_status="passed")

        plan = remediation_for_run(result["run_id"])

        self.assertEqual(plan["next_action"], "collect_more_evidence")
        self.assertIn("changed_files", plan["evidence_needed"])

    def test_rollback_required_returns_rollback_checklist(self):
        result = self._complete_low(CSS_DIFF, live_prod=True, tests_run=["smoke"], test_status="passed")

        plan = remediation_for_run(result["run_id"])

        self.assertEqual(plan["next_action"], "rollback_required")
        self.assertTrue(any("Restore the previous version" in item for item in plan["rollback_steps"]))
        self.assertFalse(plan["auto_retry_allowed"])

    def test_auto_blocked_from_secret_diff_returns_blocked_fix_required(self):
        diff = """diff --git a/login.html b/login.html
--- a/login.html
+++ b/login.html
@@ -0,0 +1 @@
+token = "REDACTED_PLACEHOLDER"
"""
        result = self._complete_low(diff, changed_files=["login.html"])

        plan = remediation_for_run(result["run_id"])

        self.assertEqual(plan["next_action"], "blocked_fix_required")
        self.assertIn("secret_detected", plan["block_reasons"])
        self.assertTrue(any("Remove the secret-looking value" in item for item in plan["safe_correction_steps"]))

    def test_auto_blocked_from_forbidden_auth_file_returns_blocked_fix_required(self):
        result = self._complete_low(CSS_DIFF, changed_files=["Auth/require_auth.php"])

        plan = remediation_for_run(result["run_id"])

        self.assertEqual(plan["next_action"], "blocked_fix_required")
        self.assertIn("forbidden_file_change", plan["block_reasons"])

    def test_retry_packet_preserves_forbidden_files_from_contract(self):
        result = self._complete_low(CSS_DIFF, tests_run=["css smoke"], test_status="failed")

        packet = retry_packet_for_run(result["run_id"])

        self.assertEqual(packet["forbidden_files"], result["run_contract"]["forbidden_file_patterns"])

    def test_retry_packet_does_not_broaden_scope(self):
        result = self._complete_low(CSS_DIFF, tests_run=["css smoke"], test_status="failed")

        packet = retry_packet_for_run(result["run_id"])

        self.assertIn("Do not expand scope", " ".join(packet["instructions"]))
        self.assertEqual(packet["allowed_files"], result["run_contract"]["allowed_file_patterns"])

    def test_destructive_sql_block_returns_safe_correction_steps(self):
        run = start_run("Random Test App", "Build login, roles, SQL database, and admin dashboard")
        diff = """diff --git a/database/cleanup.sql b/database/cleanup.sql
--- a/database/cleanup.sql
+++ b/database/cleanup.sql
@@ -0,0 +1 @@
+delete from users
"""
        result = complete_run(run["run_id"], ["database/cleanup.sql"], diff, tests_run=["unit tests"], test_status="passed")

        plan = remediation_for_run(result["run_id"])

        self.assertEqual(plan["next_action"], "blocked_fix_required")
        self.assertTrue(any("destructive" in item.casefold() for item in plan["safe_correction_steps"]))

    def test_auth_bypass_block_returns_restore_auth_check_steps(self):
        result = self._complete_low(AUTH_DIFF, changed_files=["login.html"])

        plan = remediation_for_run(result["run_id"])

        self.assertEqual(plan["next_action"], "blocked_fix_required")
        self.assertIn("auth_bypass", plan["block_reasons"])
        self.assertTrue(any("Restore the auth" in item for item in plan["safe_correction_steps"]))

    def test_low_risk_retry_can_auto_retry(self):
        result = self._complete_low(CSS_DIFF, tests_run=["css smoke"], test_status="failed")

        plan = remediation_for_run(result["run_id"])

        self.assertTrue(plan["auto_retry_allowed"])

    def test_high_risk_blocked_retry_is_not_auto_allowed(self):
        run = start_run("Random Test App", "Build login, roles, SQL database, and admin dashboard")
        result = complete_run(run["run_id"], ["login.html"], AUTH_DIFF, tests_run=["unit tests"], test_status="passed")

        plan = remediation_for_run(result["run_id"])

        self.assertEqual(plan["next_action"], "blocked_fix_required")
        self.assertFalse(plan["auto_retry_allowed"])

    def test_integration_handlers_return_remediation_and_retry_packet(self):
        result = self._complete_low(CSS_DIFF, tests_run=["css smoke"], test_status="failed")

        plan = handle_remediation_plan({"run_id": result["run_id"]})
        packet = handle_retry_packet({"run_id": result["run_id"]})

        self.assertEqual(plan["contract_version"], "v1")
        self.assertEqual(plan["remediation"]["next_action"], "retry_agent")
        self.assertIn("instructions", packet["retry_packet"])

    def test_remediation_from_result_file(self):
        result = self._complete_low(CSS_DIFF, tests_run=["css smoke"], test_status="failed")
        path = Path(self.tmp.name) / "result.json"
        path.write_text(json.dumps({"autogate": result}), encoding="utf-8")

        plan = remediation_from_file(path)

        self.assertEqual(plan["next_action"], "retry_agent")

    def _complete_low(self, diff, changed_files=None, tests_run=None, test_status="not_run", live_prod=False):
        run = start_run("Diana Test Project", "Make hello world page prettier", live_prod=True if live_prod else None)
        return complete_run(
            run["run_id"],
            changed_files or ["style.css"],
            diff,
            tests_run=tests_run,
            test_status=test_status,
        )

    def _complete_high_sql(self):
        run = start_run("Random Test App", "Build login and database")
        return complete_run(run["run_id"], ["database/001_create_users.sql"], SQL_DIFF)


if __name__ == "__main__":
    unittest.main()
