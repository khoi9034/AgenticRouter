import os
import tempfile
import unittest
from pathlib import Path

from agentic_router.normalizer import normalize_task
from agentic_router.router import route


class NormalizerTests(unittest.TestCase):
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

    def test_low_risk_test_project_static_ui_stays_cheap(self):
        result = route("Diana Test Project", "make hello world page prettier", ["index.html"])

        self.assertEqual(result["model_tier"], "cheap")
        self.assertEqual(result["intrinsic_task_risk"], "low")

    def test_low_risk_project_database_sign_in_admin_routes_advanced(self):
        result = route(
            "Diana Test Project",
            "build database with sign in and admin users",
            [],
            profile_name="max_savings",
        )

        self.assertEqual(result["model_tier"], "advanced")
        self.assertEqual(result["intrinsic_task_risk"], "high")
        self.assertTrue(result["human_review_required"])

    def test_low_risk_docs_task_with_sql_migration_and_auth_roles_routes_advanced(self):
        result = route("Mark's Test Project", "add SQL migration and auth roles", ["docs/notes.md"])

        self.assertEqual(result["model_tier"], "advanced")
        self.assertEqual(result["minimum_recommended_tier"], "advanced")

    def test_veteran_typo_has_low_intrinsic_risk_but_project_floor_stays_advanced(self):
        result = route("Veteran's Intake Application", "fix typo", ["README.md"])

        self.assertEqual(result["normalized_task"]["intrinsic_risk"], "low")
        self.assertEqual(result["model_tier"], "advanced")
        self.assertTrue(result["human_review_required"])

    def test_microsoft_graph_advanced_hunting_detects_security_api(self):
        normalized = normalize_task("Connect Microsoft Graph Advanced Hunting API", [])

        self.assertEqual(normalized["intrinsic_risk"], "high")
        self.assertTrue(normalized["security_sensitive"])
        self.assertIn("microsoft_graph_intune", normalized["requested_capabilities"])
        self.assertIn("backend_api", normalized["requested_capabilities"])

    def test_csv_import_duplicate_handling_is_medium(self):
        normalized = normalize_task("Create CSV import with duplicate handling", [])

        self.assertEqual(normalized["intrinsic_risk"], "medium")
        self.assertEqual(normalized["minimum_recommended_tier"], "mid")
        self.assertIn("data_transformation", normalized["requested_capabilities"])

    def test_live_production_email_reports_route_advanced(self):
        result = route("Diana Test Project", "Send live production email reports", ["reports/email.py"])

        self.assertEqual(result["model_tier"], "advanced")
        self.assertEqual(result["intrinsic_task_risk"], "high")

    def test_max_savings_profile_cannot_downgrade_high_intrinsic_risk(self):
        result = route(
            "Mark's Test Project",
            "Create login, roles, SQL database, and admin dashboard",
            profile_name="max_savings",
        )

        self.assertEqual(result["model_tier"], "advanced")
        self.assertEqual(result["selected_model_alias"], "devspace-security")

    def test_route_output_includes_normalized_task(self):
        result = route("Diana Test Project", "Make hello world prettier")

        self.assertIn("normalized_task", result)
        self.assertIn("requested_capabilities", result)
        self.assertIn("task_ambiguity_warnings", result)


if __name__ == "__main__":
    unittest.main()
