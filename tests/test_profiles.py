import unittest

from agentic_router.profiles import model_family
from agentic_router.router import route


class ProfileTests(unittest.TestCase):
    def test_max_savings_does_not_downgrade_sensitive_live_prod_tasks(self):
        result = route(
            "Veteran's Intake Application",
            "Fix auth ping redirect",
            ["Auth/ping.php"],
            profile_name="max_savings",
        )

        self.assertEqual(result["model_tier"], "advanced")
        self.assertEqual(result["selected_model_alias"], "devspace-security")
        self.assertEqual(result["selected_model"], "GPT-5.5")
        self.assertTrue(result["human_review_required"])

    def test_claude_only_selects_claude_models(self):
        result = route(
            "Grant Quarter Reporting",
            "Create a dashboard report",
            ["reports/quarterly.py"],
            profile_name="claude_only",
        )

        self.assertEqual(model_family(result["selected_model"]), "claude")
        self.assertTrue(all(model_family(model) == "claude" for model in result["fallback_candidates"]))

    def test_codex_only_selects_codex_models(self):
        result = route(
            "Grant Quarter Reporting",
            "Create a dashboard report",
            ["reports/quarterly.py"],
            profile_name="codex_only",
        )

        self.assertEqual(model_family(result["selected_model"]), "codex")
        self.assertTrue(all(model_family(model) == "codex" for model in result["fallback_candidates"]))

    def test_live_prod_security_route_uses_advanced_alias(self):
        result = route(
            "USB Device Approval Application",
            "Connect Graph Advanced Hunting API and create TDX ticket",
            [],
        )

        self.assertEqual(result["selected_model_alias"], "devspace-security")
        self.assertEqual(result["fallback_candidates"], ["GPT-5.5", "Opus 4.8"])

    def test_allowed_model_pool_can_select_normal_task_model(self):
        result = route(
            "Diana Test Project",
            "Make hello world prettier",
            ["index.html"],
            allowed_models=["GPT-5.4 mini"],
        )

        self.assertEqual(result["selected_model"], "GPT-5.4 mini")

    def test_route_output_includes_profile_metadata(self):
        result = route("Diana Test Project", "Make hello world prettier", ["index.html"])

        self.assertIn("selected_model_alias", result)
        self.assertIn("fallback_candidates", result)
        self.assertEqual(result["profile_name"], "balanced")


if __name__ == "__main__":
    unittest.main()
