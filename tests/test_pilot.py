import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen

from agentic_router.pilot import (
    demo_script_text,
    export_pilot_report,
    pilot_scorecard,
    rollout_plan_text,
)
from agentic_router.web import make_server


class PilotReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_traces = os.environ.get("AGENTIC_ROUTER_TRACES")
        self.old_shadow = os.environ.get("AGENTIC_ROUTER_SHADOW_RUNS")
        os.environ["AGENTIC_ROUTER_TRACES"] = str(Path(self.tmp.name) / "traces.jsonl")
        os.environ["AGENTIC_ROUTER_SHADOW_RUNS"] = str(Path(self.tmp.name) / "shadow_runs.jsonl")

    def tearDown(self):
        if self.old_traces is None:
            os.environ.pop("AGENTIC_ROUTER_TRACES", None)
        else:
            os.environ["AGENTIC_ROUTER_TRACES"] = self.old_traces
        if self.old_shadow is None:
            os.environ.pop("AGENTIC_ROUTER_SHADOW_RUNS", None)
        else:
            os.environ["AGENTIC_ROUTER_SHADOW_RUNS"] = self.old_shadow
        self.tmp.cleanup()

    def test_pilot_report_generation_creates_markdown_and_json(self):
        result = export_pilot_report(output_dir=Path(self.tmp.name) / "reports")

        self.assertTrue(Path(result["files"]["markdown"]).exists())
        self.assertTrue(Path(result["files"]["json"]).exists())
        self.assertTrue(Path(result["files"]["scorecard"]).exists())
        self.assertIn("Pilot Readiness Report", Path(result["files"]["markdown"]).read_text(encoding="utf-8"))
        self.assertEqual(json.loads(Path(result["files"]["json"]).read_text(encoding="utf-8"))["scorecard"]["readiness_status"], "demo-ready")

    def test_scorecard_includes_golden_eval_count_and_pass_rate(self):
        scorecard = pilot_scorecard()

        self.assertEqual(scorecard["golden_eval_count"], 51)
        self.assertEqual(scorecard["golden_eval_pass_rate"], 100.0)
        self.assertEqual(scorecard["config_validation_status"], "pass")
        self.assertEqual(scorecard["integration_contract_version"], "v1")

    def test_rollout_plan_includes_shadow_advise_packet_strict_sequence(self):
        plan = rollout_plan_text().casefold()

        for term in ["shadow", "advise", "packet", "strict"]:
            self.assertIn(term, plan)

    def test_demo_script_includes_low_and_high_risk_examples(self):
        script = demo_script_text()

        self.assertIn("Diana Test Project", script)
        self.assertIn("Veteran's Intake Application", script)
        self.assertIn("Gap Bills Forge Conversion", script)
        self.assertIn("Local Budget Book", script)

    def test_web_endpoints_return_expected_fields(self):
        server = make_server(port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            scorecard = self._get_json(base, "/api/pilot/scorecard")
            report = self._get_json(base, "/api/pilot/report")
            demo = self._get_json(base, "/api/pilot/demo-script")
            rollout = self._get_json(base, "/api/pilot/rollout-plan")
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

        self.assertEqual(scorecard["readiness_status"], "demo-ready")
        self.assertIn("markdown", report["files"])
        self.assertIn("Diana Test Project", demo["content"])
        self.assertIn("strict", rollout["content"].casefold())

    def _get_json(self, base_url, path):
        return json.loads(urlopen(f"{base_url}{path}", timeout=10).read())


if __name__ == "__main__":
    unittest.main()
