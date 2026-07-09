import json
import os
import tempfile
import unittest
from pathlib import Path

from agentic_router.observability import (
    export_langsmith_files,
    observability_status,
    sanitize_text,
    summarize_traces,
    write_trace,
)
from agentic_router.router import route


class ObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "traces.jsonl"
        self.old_traces = os.environ.get("AGENTIC_ROUTER_TRACES")
        os.environ["AGENTIC_ROUTER_TRACES"] = str(self.path)

    def tearDown(self):
        if self.old_traces is None:
            os.environ.pop("AGENTIC_ROUTER_TRACES", None)
        else:
            os.environ["AGENTIC_ROUTER_TRACES"] = self.old_traces
        self.tmp.cleanup()

    def test_traces_are_written_locally(self):
        result = route("Diana Test Project", "Make hello world page prettier", ["index.html"])
        trace = json.loads(self.path.read_text(encoding="utf-8").strip())

        self.assertEqual(trace["route_id"], result["route_id"])
        self.assertEqual(trace["selected_model_alias"], result["selected_model_alias"])
        self.assertTrue(trace["prompt_body_logged"])

    def test_high_risk_trace_redacts_raw_task_text(self):
        route(
            "Veteran's Intake Application",
            "Fix auth ping redirect with bearer token ABC123",
            ["Auth/ping.php"],
        )
        raw = self.path.read_text(encoding="utf-8")
        trace = json.loads(raw.strip())

        self.assertFalse(trace["prompt_body_logged"])
        self.assertIn("task_description_hash", trace)
        self.assertNotIn("Fix auth ping redirect", raw)
        self.assertNotIn("ABC123", raw)

    def test_sensitive_patterns_are_redacted(self):
        text = sanitize_text("Email a.user@example.com token ABC123 from C:\\Users\\khoia\\secret.txt")

        self.assertNotIn("a.user@example.com", text)
        self.assertNotIn("ABC123", text)
        self.assertNotIn("C:\\Users\\khoia", text)

    def test_jsonl_and_csv_exports_are_created(self):
        route("Diana Test Project", "Make hello world page prettier", ["index.html"])
        output = Path(self.tmp.name) / "exports"
        result = export_langsmith_files(output_dir=output)

        for path in result["files"].values():
            self.assertTrue(Path(path).exists())
        self.assertTrue((output / "golden_tasks_dataset.jsonl").read_text(encoding="utf-8"))
        self.assertIn("route_id", (output / "router_traces_example.csv").read_text(encoding="utf-8").splitlines()[0])

    def test_observability_status_says_remote_disabled(self):
        status = observability_status()

        self.assertTrue(status["local_tracing_enabled"])
        self.assertFalse(status["remote_tracing_enabled"])
        self.assertFalse(status["langsmith_api_enabled"])

    def test_trace_summary_counts(self):
        result = route("Diana Test Project", "Make hello world page prettier", ["index.html"])
        write_trace(
            "Diana Test Project",
            "follow up",
            [],
            {**result, "sticky_route_used": True},
            path=self.path,
        )
        summary = summarize_traces(path=self.path)

        self.assertEqual(summary["total_traces"], 2)
        self.assertEqual(summary["sticky_route_count"], 1)


if __name__ == "__main__":
    unittest.main()
