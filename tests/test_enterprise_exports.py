import re
import tempfile
import unittest
from pathlib import Path

from agentic_router.enterprise import export_enterprise


class EnterpriseExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.paths = export_enterprise("all", self.base)
        self.contents = {path.relative_to(self.base).as_posix(): path.read_text(encoding="utf-8") for path in self.paths}

    def tearDown(self):
        self.tmp.cleanup()

    def test_export_files_are_generated(self):
        expected = {
            "litellm/config.example.yaml",
            "litellm/model_aliases.example.yaml",
            "litellm/team_budget_policy.example.yaml",
            "litellm/virtual_keys.example.md",
            "gateway/routing_policy.example.yaml",
            "gateway/context_policy.example.yaml",
            "gateway/guardrails_policy.example.yaml",
            "gateway/observability_policy.example.yaml",
            "gateway/devspace_integration_contract.md",
        }

        self.assertEqual(set(self.contents), expected)

    def test_exports_do_not_contain_obvious_secret_values(self):
        text = "\n".join(self.contents.values())

        self.assertNotIn("sk-", text)
        self.assertIsNone(re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text))
        self.assertIsNone(re.search(r"C:\\Users\\", text))
        self.assertIsNone(re.search(r"https?://", text))
        self.assertIsNone(re.search(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b", text))

    def test_litellm_config_has_required_sections(self):
        config = self.contents["litellm/config.example.yaml"]

        self.assertIn("model_list:", config)
        self.assertIn("router_settings:", config)
        self.assertIn("litellm_settings:", config)
        self.assertIn("general_settings:", config)
        self.assertIn("environment_variables:", config)
        self.assertIn("fallbacks:", config)

    def test_routing_policy_has_required_fields(self):
        policy = self.contents["gateway/routing_policy.example.yaml"]

        self.assertIn("task_class:", policy)
        self.assertIn("human_review_required:", policy)
        self.assertIn("default_model_alias:", policy)

    def test_guardrails_policy_contains_prohibitions(self):
        policy = self.contents["gateway/guardrails_policy.example.yaml"].casefold()

        self.assertIn("no pii", policy)
        self.assertIn("no secrets", policy)
        self.assertIn("no usb serials", policy)

    def test_observability_policy_avoids_sensitive_prompt_bodies(self):
        policy = self.contents["gateway/observability_policy.example.yaml"]

        self.assertIn("do_not_log_prompt_bodies: true", policy)
        self.assertIn("do_not_log_secrets_or_pii: true", policy)


if __name__ == "__main__":
    unittest.main()

