import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from agentic_router.contracts import generate_contract
from agentic_router.diff_review import review_current_diff, review_diff
from agentic_router.integration import handle_diff_review_request


CSS_DIFF = """diff --git a/style.css b/style.css
--- a/style.css
+++ b/style.css
@@ -1 +1 @@
-.button { color: blue; }
+.button { color: green; }
"""


class DiffReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_traces = os.environ.get("AGENTIC_ROUTER_TRACES")
        os.environ["AGENTIC_ROUTER_TRACES"] = str(Path(self.tmp.name) / "traces.jsonl")

    def tearDown(self):
        if self.old_traces is None:
            os.environ.pop("AGENTIC_ROUTER_TRACES", None)
        else:
            os.environ["AGENTIC_ROUTER_TRACES"] = self.old_traces
        self.tmp.cleanup()

    def test_css_only_pass(self):
        result = review_diff("Random Test App", "Change login button color", git_diff=CSS_DIFF)

        self.assertEqual(result["decision"], "pass")
        self.assertEqual(result["risk_level"], "low")

    def test_login_button_css_does_not_trigger_auth(self):
        diff = Path("examples/css_only.diff").read_text(encoding="utf-8")
        result = review_diff("Random Test App", "Change login button color", git_diff=diff)

        self.assertEqual(result["decision"], "pass")
        self.assertNotIn("auth_session_change", result["detected_change_types"])

    def test_docs_only_pass(self):
        diff = """diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1 +1 @@
-Old wording
+Clearer wording
"""
        result = review_diff("Diana Test Project", "Update README wording", git_diff=diff)

        self.assertEqual(result["decision"], "pass")

    def test_secret_detection_fails(self):
        diff = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1 +1 @@
+token = "REDACTED_PLACEHOLDER"
"""
        result = review_diff("Random Test App", "Update config", git_diff=diff)

        self.assertEqual(result["decision"], "fail")
        self.assertEqual(result["risk_level"], "high")

    def test_auth_bypass_fails(self):
        diff = Path("examples/auth_change.diff").read_text(encoding="utf-8")
        result = review_diff("Random Test App", "Change login button color", git_diff=diff)

        self.assertEqual(result["decision"], "fail")
        self.assertIn("auth_bypass_or_weakening", result["detected_change_types"])

    def test_api_endpoint_change_warns(self):
        diff = """diff --git a/login.html b/login.html
--- a/login.html
+++ b/login.html
@@ -1 +1 @@
-<form action="/login">
+<form action="/api/session/create">
"""
        contract = generate_contract("Random Test App", "Change login button color")
        result = review_diff("Random Test App", "Change login button color", contract, ["login.html"], diff)

        self.assertEqual(result["decision"], "warn")
        self.assertIn("api_contract_change", result["detected_change_types"])

    def test_sql_migration_high_risk(self):
        diff = Path("examples/sql_migration.diff").read_text(encoding="utf-8")
        result = review_diff("Random Test App", "Build login and database", git_diff=diff)

        self.assertEqual(result["risk_level"], "high")
        self.assertTrue(result["human_review_required"])

    def test_destructive_sql_fails(self):
        diff = """diff --git a/database/cleanup.sql b/database/cleanup.sql
--- a/database/cleanup.sql
+++ b/database/cleanup.sql
@@ -0,0 +1 @@
+DROP TABLE users;
"""
        result = review_diff("Random Test App", "Clean old data", git_diff=diff)

        self.assertEqual(result["decision"], "fail")
        self.assertTrue(result["rollback_required"])

    def test_dependency_file_warns(self):
        diff = """diff --git a/requirements.txt b/requirements.txt
--- a/requirements.txt
+++ b/requirements.txt
@@ -0,0 +1 @@
+some-package==1.0
"""
        result = review_diff("Random Test App", "Update UI", git_diff=diff)

        self.assertEqual(result["decision"], "warn")
        self.assertEqual(result["risk_level"], "medium")

    def test_external_write_high_risk(self):
        diff = """diff --git a/reports.py b/reports.py
--- a/reports.py
+++ b/reports.py
@@ -1 +1 @@
+send_email(report)
"""
        result = review_diff("Random Test App", "Send email report", git_diff=diff)

        self.assertEqual(result["risk_level"], "high")
        self.assertTrue(result["human_review_required"])

    def test_contract_pass_but_diff_risk_escalates(self):
        contract = generate_contract("Random Test App", "Change login button color")
        diff = """diff --git a/login.html b/login.html
--- a/login.html
+++ b/login.html
@@ -1 +1 @@
-<form action="/login">
+<form action="/api/session/create">
"""
        result = review_diff("Random Test App", "Change login button color", contract, ["login.html"], diff)

        self.assertEqual(result["decision"], "warn")

    def test_contract_fail_remains_fail(self):
        contract = generate_contract("Random Test App", "Change login button color")
        result = review_diff("Random Test App", "Change login button color", contract, ["Auth/require_auth.php"], CSS_DIFF)

        self.assertEqual(result["decision"], "fail")

    def test_review_current_diff_handles_no_diff(self):
        repo = Path(self.tmp.name) / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

        result = review_current_diff("Random Test App", "No-op review", cwd=repo)

        self.assertIn(result["decision"], {"pass", "warn"})
        self.assertIn("No git diff content supplied.", result["warnings"])

    def test_api_handler_returns_diff_review(self):
        response = handle_diff_review_request(
            {"project_name": "Random Test App", "task_description": "Change color", "git_diff": CSS_DIFF}
        )

        self.assertEqual(response["contract_version"], "v1")
        self.assertEqual(response["diff_review"]["decision"], "pass")


if __name__ == "__main__":
    unittest.main()
