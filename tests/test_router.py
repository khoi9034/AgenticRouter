import unittest

from agentic_router import route


class RouterTests(unittest.TestCase):
    def test_cheap_static_ui_task_routes_cheap(self):
        result = route(
            "Diana Test Project",
            "Make the hello world page background prettier",
            ["index.html", "style.css"],
        )

        self.assertEqual(result["model_tier"], "cheap")
        self.assertIn(result["recommended_model"], {"Haiku 4.5", "GPT-5.4 mini"})

    def test_normal_dashboard_report_task_routes_mid(self):
        result = route(
            "Grant Quarter Reporting",
            "Create a dashboard report for quarter totals",
            ["reports/quarterly.py"],
        )

        self.assertEqual(result["model_tier"], "mid")

    def test_veteran_laserfiche_auth_task_routes_advanced(self):
        result = route(
            "Veteran's Intake Application",
            "Fix auth ping endpoint redirect bug for Laserfiche intake",
            ["Auth/ping.php", "api/list_intakes.php"],
            previous_failure_count=1,
        )

        self.assertEqual(result["model_tier"], "advanced")
        self.assertTrue(result["human_review_required"])

    def test_live_prod_forge_bot_code_change_routes_advanced(self):
        result = route(
            "TD Refresh Users Bot Conversion",
            "Change live Forge bot code that writes TeamDynamix users",
            ["bots/refresh_users.py"],
        )

        self.assertEqual(result["model_tier"], "advanced")

    def test_repeated_failures_escalate_one_tier(self):
        result = route(
            "Diana Test Project",
            "Update README copy",
            ["README.md"],
            previous_failure_count=2,
        )

        self.assertEqual(result["model_tier"], "mid")
        self.assertIn("previous_failures_escalate", result["matched_rules"])

    def test_sensitive_project_sets_human_review_required(self):
        result = route(
            "Workers Comp V2",
            "Summarize claim workflow",
            ["docs/workflow.md"],
        )

        self.assertTrue(result["human_review_required"])

    def test_context_policy_excludes_secrets_and_pii_for_sensitive_tasks(self):
        result = route(
            "Veteran's Intake Application",
            "Fix auth bug without exposing credentials or PII",
            ["Auth/ping.php"],
        )
        policy = result["context_policy"].casefold()

        self.assertIn("secrets", policy)
        self.assertIn("pii", policy)


if __name__ == "__main__":
    unittest.main()

