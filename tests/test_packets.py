import unittest

from agentic_router.packets import generate_packet


class PacketTests(unittest.TestCase):
    def test_diana_static_ui_packet_is_cheap_with_simple_validation(self):
        packet = generate_packet(
            "Diana Test Project",
            "Make the hello world page prettier",
            [],
        )

        self.assertEqual(packet["recommended_model"], "Haiku 4.5")
        self.assertIn(packet["context_pack"]["context_size"], {"tiny", "small"})
        self.assertEqual(packet["validation_playbook"], "static_ui_docs")
        self.assertIn("HTML/CSS", " ".join(packet["validation_checklist"]))

    def test_veteran_auth_packet_forbids_pii_and_secrets(self):
        packet = generate_packet(
            "Veteran's Intake Application",
            "Fix auth ping redirect bug",
            ["Auth/ping.php", "api/list_intakes.php"],
        )
        text = " ".join(
            packet["context_pack"]["forbidden_context"]
            + packet["safety_checklist"]
            + [packet["execution_prompt"]]
        ).casefold()

        self.assertIn("pii", text)
        self.assertIn("secrets", text)
        self.assertTrue(packet["human_review_required"])

    def test_usb_device_packet_includes_graph_intune_security_warnings(self):
        packet = generate_packet(
            "USB Device Approval Application",
            "Connect Graph Advanced Hunting API and create TDX ticket",
            [],
        )
        text = " ".join(packet["validation_checklist"] + packet["execution_prompt"].splitlines()).casefold()

        self.assertEqual(packet["validation_playbook"], "microsoft_graph_cybersecurity")
        self.assertIn("graph", text)
        self.assertIn("intune", text)
        self.assertIn("security", text)

    def test_local_budget_packet_requires_source_verification(self):
        packet = generate_packet(
            "Local Budget Book",
            "Fix official fund table",
            ["site/funds.html"],
        )
        text = " ".join(packet["validation_checklist"] + packet["stop_conditions"] + [packet["execution_prompt"]]).casefold()

        self.assertEqual(packet["validation_playbook"], "public_official_budget_content")
        self.assertIn("verify", text)
        self.assertIn("do not invent numbers", text)

    def test_gap_bills_live_prod_naming_packet_warns_about_dependencies_and_review(self):
        packet = generate_packet(
            "Gap Bills Forge Conversion",
            "Change PDF output naming format",
            ["forge_bot/gap_bills_bot.py"],
        )
        text = " ".join(
            packet["safety_checklist"] + packet["stop_conditions"] + packet["escalation_plan"] + [packet["execution_prompt"]]
        ).casefold()

        self.assertEqual(packet["validation_playbook"], "live_prod_forge_bot")
        self.assertIn("filename dependencies", text)
        self.assertIn("human review", text)
        self.assertIn("do not make broad refactors", text)


if __name__ == "__main__":
    unittest.main()

