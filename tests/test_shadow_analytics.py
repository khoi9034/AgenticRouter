import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from agentic_router.integration import handle_request
from agentic_router.shadow import (
    add_demo_data,
    compare_tiers,
    export_shadow_report,
    load_shadow_runs,
    summarize_shadow_runs,
    tier_for_model,
)
from agentic_router.web import make_server


class ShadowAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.shadow_path = Path(self.tmp.name) / "shadow_runs.jsonl"
        self.trace_path = Path(self.tmp.name) / "traces.jsonl"
        self.old_shadow = os.environ.get("AGENTIC_ROUTER_SHADOW_RUNS")
        self.old_traces = os.environ.get("AGENTIC_ROUTER_TRACES")
        os.environ["AGENTIC_ROUTER_SHADOW_RUNS"] = str(self.shadow_path)
        os.environ["AGENTIC_ROUTER_TRACES"] = str(self.trace_path)

    def tearDown(self):
        if self.old_shadow is None:
            os.environ.pop("AGENTIC_ROUTER_SHADOW_RUNS", None)
        else:
            os.environ["AGENTIC_ROUTER_SHADOW_RUNS"] = self.old_shadow
        if self.old_traces is None:
            os.environ.pop("AGENTIC_ROUTER_TRACES", None)
        else:
            os.environ["AGENTIC_ROUTER_TRACES"] = self.old_traces
        self.tmp.cleanup()

    def test_shadow_record_is_written_on_shadow_call(self):
        server = make_server(port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            response = self._post_json(
                f"http://127.0.0.1:{server.server_port}",
                "/api/v1/shadow",
                {
                    "project_name": "Diana Test Project",
                    "task_description": "Update README copy",
                    "files_touched": ["README.md"],
                    "actual_model_used": "GPT-5.5",
                },
            )
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
        records = load_shadow_runs()

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["shadow_id"], response["shadow_id"])
        self.assertEqual(response["actual_tier"], "advanced")
        self.assertEqual(response["overkill_or_underpowered"], "human_stronger")

    def _post_json(self, base_url, path, payload):
        request = Request(
            f"{base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return json.loads(urlopen(request, timeout=5).read())

    def test_direct_shadow_handler_writes_record(self):
        response = handle_request(
            {
                "mode": "shadow",
                "project_name": "Diana Test Project",
                "task_description": "Update README copy",
                "files_touched": ["README.md"],
                "actual_model_used": "GPT-5.5",
            }
        )
        records = load_shadow_runs()

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["shadow_id"], response["shadow_id"])
        self.assertEqual(response["actual_tier"], "advanced")
        self.assertEqual(response["overkill_or_underpowered"], "human_stronger")

    def test_high_risk_shadow_does_not_store_raw_task_text(self):
        handle_request(
            {
                "mode": "shadow",
                "project_name": "Veteran's Intake Application",
                "task_description": "Fix auth ping redirect with bearer token ABC123",
                "files_touched": ["Auth/ping.php"],
                "actual_model_used": "Haiku 4.5",
            }
        )
        raw = self.shadow_path.read_text(encoding="utf-8")
        record = json.loads(raw)

        self.assertFalse(record["prompt_body_logged"])
        self.assertIn("task_description_hash", record)
        self.assertNotIn("Fix auth ping redirect", raw)
        self.assertNotIn("ABC123", raw)

    def test_tier_comparison_and_cost_delta(self):
        self.assertEqual(tier_for_model("GPT-5.5"), "advanced")
        self.assertEqual(tier_for_model("devspace-cheap"), "cheap")

        stronger = compare_tiers("cheap", "advanced")
        weaker = compare_tiers("advanced", "cheap", human_review_required=True)

        self.assertEqual(stronger["overkill_or_underpowered"], "human_stronger")
        self.assertEqual(stronger["abstract_cost_delta"], 7)
        self.assertEqual(weaker["overkill_or_underpowered"], "safety_risk")
        self.assertEqual(weaker["abstract_cost_delta"], -7)

    def test_summary_computes_overkill_and_too_weak_counts(self):
        add_demo_data()
        summary = summarize_shadow_runs()

        self.assertEqual(summary["total_shadow_runs"], 5)
        self.assertGreaterEqual(summary["estimated_overkill_count"], 1)
        self.assertGreaterEqual(summary["estimated_too_weak_safety_risk_count"], 1)
        self.assertGreaterEqual(summary["strict_mode_would_block_count"], 1)
        self.assertNotEqual(summary["estimated_units_saved_lost"], 0)

    def test_export_report_creates_markdown_and_json(self):
        add_demo_data()
        result = export_shadow_report(output_dir=Path(self.tmp.name) / "reports")

        self.assertTrue(Path(result["files"]["markdown"]).exists())
        self.assertTrue(Path(result["files"]["json"]).exists())
        self.assertIn("Shadow Mode Report", Path(result["files"]["markdown"]).read_text(encoding="utf-8"))
        self.assertEqual(json.loads(Path(result["files"]["json"]).read_text(encoding="utf-8"))["summary"]["total_shadow_runs"], 5)

    def test_web_endpoint_returns_summary(self):
        add_demo_data()
        server = make_server(port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            summary = json.loads(urlopen(f"http://127.0.0.1:{server.server_port}/api/shadow/summary", timeout=5).read())
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

        self.assertEqual(summary["total_shadow_runs"], 5)


if __name__ == "__main__":
    unittest.main()
