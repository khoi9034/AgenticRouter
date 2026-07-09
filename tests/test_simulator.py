import os
import tempfile
import unittest
from pathlib import Path

from agentic_router.simulator import CONTEXT_UNITS, TIER_UNITS, list_scenarios, run_scenario


class SimulatorTests(unittest.TestCase):
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

    def test_list_scenarios_returns_names(self):
        names = list_scenarios()

        self.assertIn("mixed_devspace_month", names)
        self.assertIn("sensitive_systems_week", names)

    def test_running_scenario_returns_summary(self):
        result = run_scenario("mixed_devspace_month")

        self.assertEqual(result["summary"]["total_tasks"], len(result["tasks"]))
        self.assertIn("routes_by_tier", result["summary"])

    def test_cost_savings_calculation_is_correct(self):
        result = run_scenario("mixed_devspace_month")
        tasks = result["tasks"]
        expected_router_cost = sum(TIER_UNITS[item["model_tier"]] for item in tasks)
        expected_naive_cost = len(tasks) * TIER_UNITS["advanced"]

        savings = result["summary"]["savings"]

        self.assertEqual(savings["router_estimated_cost"], expected_router_cost)
        self.assertEqual(savings["estimated_units_saved"], expected_naive_cost - expected_router_cost)

    def test_context_savings_calculation_is_correct(self):
        result = run_scenario("docs_heavy_week")
        tasks = result["tasks"]
        expected_router_context = sum(CONTEXT_UNITS[item["context_size"]] for item in tasks)
        expected_naive_context = len(tasks) * CONTEXT_UNITS["large"]

        savings = result["summary"]["savings"]

        self.assertEqual(savings["router_estimated_context"], expected_router_context)
        self.assertEqual(savings["estimated_context_units_saved"], expected_naive_context - expected_router_context)

    def test_sensitive_scenario_requires_human_review(self):
        result = run_scenario("sensitive_systems_week")

        self.assertGreater(result["summary"]["human_review_required_count"], 0)

    def test_forge_bot_scenario_includes_advanced_live_prod_routes(self):
        result = run_scenario("forge_bot_maintenance_week")

        self.assertGreater(result["summary"]["routes_by_tier"].get("advanced", 0), 0)
        self.assertGreater(result["summary"]["live_prod_count"], 0)


if __name__ == "__main__":
    unittest.main()
