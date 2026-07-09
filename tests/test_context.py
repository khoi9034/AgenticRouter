import unittest

from agentic_router import route


class ContextPackTests(unittest.TestCase):
    def test_cheap_css_task_uses_tiny_or_small_context_and_excludes_backend_auth(self):
        pack = route(
            "Diana Test Project",
            "Make the hello world page CSS background prettier",
            ["web/style.css"],
        )["context_pack"]

        self.assertIn(pack["context_size"], {"tiny", "small"})
        self.assertTrue(any("auth" in item for item in pack["exclude_patterns"]))
        self.assertTrue(any("backend" in item for item in pack["forbidden_context"]))

    def test_veteran_auth_task_forbids_pii_secrets_and_includes_auth_api(self):
        pack = route(
            "Veteran's Intake Application",
            "Fix auth ping redirect bug",
            ["Auth/ping.php", "api/list_intakes.php"],
        )["context_pack"]
        forbidden = " ".join(pack["forbidden_context"]).casefold()
        include = " ".join(pack["include_patterns"]).casefold()

        self.assertIn(pack["context_size"], {"medium", "large"})
        self.assertIn("pii", forbidden)
        self.assertIn("secrets", forbidden)
        self.assertIn("auth", include)
        self.assertIn("api", include)

    def test_local_budget_book_requires_source_verification(self):
        pack = route(
            "Local Budget Book",
            "Fix official fund table",
            ["site/funds.html"],
        )["context_pack"]

        self.assertIn("source", " ".join(pack["include_notes"]).casefold())
        self.assertIn("verify", pack["redaction_warning"].casefold())
        self.assertIn("invented numbers", " ".join(pack["forbidden_context"]).casefold())

    def test_live_forge_bot_naming_change_includes_bot_docs_and_warns(self):
        pack = route(
            "Gap Bills Forge Conversion",
            "Change JPG naming convention for live Forge bot",
            ["forge/gap_bills.py"],
        )["context_pack"]
        include = " ".join(pack["include_patterns"]).casefold()

        self.assertIn("claude.md", include)
        self.assertIn("implementation notes", include)
        self.assertIn("naming", pack["redaction_warning"].casefold())

    def test_usb_device_task_forbids_serials_tokens_and_tenant_ids(self):
        pack = route(
            "USB Device Approval Application",
            "Connect Graph Advanced Hunting API and create TDX ticket",
            [],
        )["context_pack"]
        forbidden = " ".join(pack["forbidden_context"]).casefold()

        self.assertIn("usb serials", forbidden)
        self.assertIn("tokens", forbidden)
        self.assertIn("tenant ids", forbidden)

    def test_route_output_includes_context_pack(self):
        result = route("Diana Test Project", "make hello world prettier", ["index.html"])

        self.assertIn("context_pack", result)
        self.assertIn("include_patterns", result["context_pack"])


if __name__ == "__main__":
    unittest.main()

