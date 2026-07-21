import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from agentic_router.cli import main as cli_main
from agentic_router.contracts import check_contract, generate_contract
from agentic_router.integration import handle_contract_check_request, handle_contract_request, handle_request


class ContractTests(unittest.TestCase):
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

    def test_css_contract_allows_static_and_forbids_risky_paths(self):
        contract = generate_contract("Diana Test Project", "Make the hello world page prettier", ["index.html", "style.css"])

        self.assertIn("*.html", contract["allowed_file_patterns"])
        self.assertIn("*.css", contract["allowed_file_patterns"])
        for pattern in ["Auth/*", "api/*", "config*", "database/*"]:
            self.assertIn(pattern, contract["forbidden_file_patterns"])
        self.assertFalse(contract["human_review_required"])

    def test_login_button_color_does_not_allow_auth_edits(self):
        contract = generate_contract("Random Test App", "Change login button color")
        result = check_contract(contract, ["Auth/require_auth.php"])

        self.assertEqual(contract["risk_level"], "low")
        self.assertEqual(result["decision"], "fail")
        self.assertIn("Auth/require_auth.php", result["forbidden_matches"])

    def test_full_login_database_admin_requires_human_review(self):
        contract = generate_contract("Random Test App", "Build login, roles, SQL database, and admin dashboard")

        self.assertEqual(contract["risk_level"], "high")
        self.assertTrue(contract["human_review_required"])
        self.assertIn("Auth/*", contract["allowed_file_patterns"])
        self.assertTrue(any("unauthorized" in item.casefold() for item in contract["required_validation"]))

    def test_production_deploy_requires_rollback_and_review(self):
        contract = generate_contract("Unknown App", "Deploy this live to production", live_prod=True)

        self.assertTrue(contract["human_review_required"])
        self.assertTrue(any("rollback" in item.casefold() for item in contract["required_validation"]))
        self.assertTrue(contract["production_cautions"])

    def test_email_sending_requires_review_and_cautions(self):
        contract = generate_contract("Unknown App", "Send live production email reports from production data")

        self.assertTrue(contract["human_review_required"])
        self.assertTrue(contract["sensitive_data_cautions"])
        self.assertTrue(any("dry-run" in item.casefold() or "payload" in item.casefold() for item in contract["required_validation"]))

    def test_file_upload_flags_sensitive_file_handling(self):
        contract = generate_contract("Veteran's Intake Application", "Fix file upload and download handling")

        self.assertTrue(contract["human_review_required"])
        self.assertTrue(any("upload" in item.casefold() or "download" in item.casefold() for item in contract["required_validation"]))
        self.assertTrue(contract["sensitive_data_cautions"])

    def test_destructive_bulk_delete_requires_rollback(self):
        contract = generate_contract("Random Test App", "Bulk delete old records and purge duplicates")

        self.assertEqual(contract["risk_level"], "high")
        self.assertTrue(contract["human_review_required"])
        self.assertTrue(any("rollback" in item.casefold() for item in contract["required_validation"]))

    def test_scope_guard_passes_allowed_files(self):
        contract = generate_contract("Diana Test Project", "Make the hello world page prettier")
        result = check_contract(contract, ["index.html", "style.css"])

        self.assertEqual(result["decision"], "pass")

    def test_scope_guard_fails_forbidden_file(self):
        contract = generate_contract("Diana Test Project", "Make the hello world page prettier")
        result = check_contract(contract, [".env"])

        self.assertEqual(result["decision"], "fail")
        self.assertEqual(result["forbidden_matches"], [".env"])

    def test_scope_guard_warns_on_unexpected_dependencies(self):
        contract = generate_contract("Diana Test Project", "Make the hello world page prettier")
        result = check_contract(contract, ["index.html"], added_dependencies=["new-ui-package"])

        self.assertEqual(result["decision"], "warn")

    def test_contract_api_and_integration_response(self):
        response = handle_request({"project_name": "Diana Test Project", "task_description": "Update README copy"})
        contract_response = handle_contract_request({"project_name": "Diana Test Project", "task_description": "Update README copy"})
        check_response = handle_contract_check_request(
            {"contract": contract_response["run_contract"], "changed_files": ["README.md"]}
        )

        self.assertIn("run_contract", response)
        self.assertEqual(contract_response["contract_version"], "v1")
        self.assertEqual(check_response["scope_guard"]["decision"], "pass")

    def test_cli_contract_output_file_and_check(self):
        output = Path(self.tmp.name) / "contract.json"
        with redirect_stdout(StringIO()):
            contract_exit = cli_main(
                [
                    "contract",
                    "--project",
                    "Diana Test Project",
                    "--task",
                    "Make the hello world page prettier",
                    "--output",
                    str(output),
                    "--json",
                ]
            )
        self.assertEqual(contract_exit, 0)
        self.assertTrue(output.exists())
        saved = json.loads(output.read_text(encoding="utf-8"))
        self.assertIn("contract_id", saved)
        with redirect_stdout(StringIO()):
            check_exit = cli_main(["check-contract", "--contract-file", str(output), "--changed-files", "index.html"])
        self.assertEqual(check_exit, 0)


if __name__ == "__main__":
    unittest.main()
