import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from agentic_router.cli import main as cli_main
from agentic_router.integration import export_devspace_contract, handle_request, integration_self_test
from agentic_router.web import make_server


class IntegrationContractTests(unittest.TestCase):
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

    def test_health_version_and_v1_endpoint_fields(self):
        server = make_server(port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        try:
            health = self._get_json(base_url, "/api/health")
            version = self._get_json(base_url, "/api/version")
            result = self._post_json(
                base_url,
                "/api/v1/route",
                {"project_name": "Diana Test Project", "task_description": "Update README copy"},
            )
            old = self._post_json(
                base_url,
                "/api/route",
                {"project_name": "Diana Test Project", "task_description": "Update README copy"},
            )
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

        self.assertTrue(health["ok"])
        self.assertEqual(version["contract_version"], "v1")
        self.assertEqual(result["contract_version"], "v1")
        self.assertTrue(result["route_id"].startswith("ar_"))
        self.assertIn("context_pack", result)
        self.assertIn("route_id", old)

    def test_packet_mode_includes_run_packet(self):
        result = handle_request(
            {
                "mode": "packet",
                "project_name": "Diana Test Project",
                "task_description": "Make hello world page prettier",
                "files_touched": ["index.html"],
            }
        )

        self.assertEqual(result["mode"], "packet")
        self.assertIn("execution_prompt", result["devspace_run_packet"])

    def test_shadow_mode_accepts_actual_model_and_writes_trace(self):
        result = handle_request(
            {
                "mode": "shadow",
                "project_name": "Grant Quarter Reporting",
                "task_description": "Create a dashboard report for quarter totals",
                "files_touched": ["reports/quarterly.py"],
                "actual_model_used": "Sonnet 4.6",
            }
        )
        trace = json.loads(Path(os.environ["AGENTIC_ROUTER_TRACES"]).read_text(encoding="utf-8").strip())

        self.assertEqual(result["mode"], "shadow")
        self.assertEqual(result["observability"]["actual_model_used"], "Sonnet 4.6")
        self.assertEqual(trace["route_id"], result["route_id"])

    def test_strict_mode_blocks_high_risk_human_review_tasks(self):
        result = handle_request(
            {
                "mode": "strict",
                "project_name": "Veteran's Intake Application",
                "task_description": "Fix auth ping redirect bug",
                "files_touched": ["Auth/ping.php"],
            }
        )

        self.assertTrue(result["block"])
        self.assertEqual(result["block_reason"], "human_review_required")

    def test_strict_mode_allows_low_risk_static_task(self):
        result = handle_request(
            {
                "mode": "strict",
                "project_name": "Diana Test Project",
                "task_description": "Update README copy",
                "files_touched": ["README.md"],
            }
        )

        self.assertFalse(result["block"])

    def test_forbidden_context_suppresses_packet(self):
        result = handle_request(
            {
                "mode": "packet",
                "project_name": "Diana Test Project",
                "task_description": "Update docs with token=ABC123",
                "files_touched": ["README.md"],
            }
        )

        self.assertEqual(result["devspace_run_packet"], {})
        self.assertTrue(any("suppressed" in item for item in result["warnings"]))

    def test_export_contract_creates_json_files(self):
        result = export_devspace_contract(output_dir=Path(self.tmp.name) / "exports")

        for path in result["files"].values():
            self.assertTrue(Path(path).exists())
        contract = json.loads(Path(result["files"]["contract"]).read_text(encoding="utf-8"))
        examples = json.loads(Path(result["files"]["examples"]).read_text(encoding="utf-8"))
        self.assertEqual(contract["contract_version"], "v1")
        self.assertGreater(len(examples["requests"]), 0)

    def test_integration_test_command_passes(self):
        self.assertTrue(integration_self_test()["ok"])
        self.assertEqual(cli_main(["integration-test"]), 0)

    def _get_json(self, base_url, path):
        return json.loads(urlopen(f"{base_url}{path}", timeout=5).read())

    def _post_json(self, base_url, path, payload):
        request = Request(
            f"{base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return json.loads(urlopen(request, timeout=5).read())


if __name__ == "__main__":
    unittest.main()
