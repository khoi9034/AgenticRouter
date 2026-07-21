import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from agentic_router.cli import main as cli_main
from agentic_router.models import DATA_DIR
from agentic_router.normalizer import normalize_task
from agentic_router.router import route


class NormalizerAdversarialTests(unittest.TestCase):
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

    def test_dataset_has_at_least_75_examples(self):
        self.assertGreaterEqual(len(_tasks()), 75)

    def test_adversarial_examples_match_expected_risk_and_tier(self):
        failures = []
        for task in _tasks():
            result = _route(task)
            normalized = result["normalized_task"]
            if normalized["intrinsic_risk"] != task["expected_intrinsic_risk"]:
                failures.append(f"{task['id']} intrinsic expected {task['expected_intrinsic_risk']} got {normalized['intrinsic_risk']}")
            if result["model_tier"] != task["expected_model_tier"]:
                failures.append(f"{task['id']} tier expected {task['expected_model_tier']} got {result['model_tier']}")
            for control in task.get("expected_false_positive_controls", []):
                if control not in normalized["false_positive_controls_triggered"]:
                    failures.append(f"{task['id']} missing false-positive control {control}")
            if task.get("expected_ambiguity") and not normalized["ambiguity_warnings"]:
                failures.append(f"{task['id']} expected ambiguity warning")
        self.assertEqual([], failures)

    def test_required_manual_examples(self):
        expected = {
            "low_001": ("low", "cheap"),
            "high_002": ("high", "advanced"),
            "high_003": ("high", "advanced"),
            "high_004": ("high", "advanced"),
            "low_005": ("low", "cheap"),
            "low_006": ("low", "cheap"),
            "low_007": ("low", "cheap"),
            "high_008": ("high", "advanced"),
            "high_009": ("high", "advanced"),
            "medium_010": ("medium", "mid"),
            "high_011": ("high", "advanced"),
            "high_012": ("high", "advanced"),
            "medium_013": ("medium", "mid"),
            "low_014": ("low", "advanced"),
            "high_015": ("high", "advanced"),
        }
        by_id = {task["id"]: task for task in _tasks()}
        for case_id, (risk, tier) in expected.items():
            result = _route(by_id[case_id])
            self.assertEqual(risk, result["intrinsic_task_risk"], case_id)
            self.assertEqual(tier, result["model_tier"], case_id)

    def test_normalize_cli_shape_without_routing_trace(self):
        normalized = normalize_task("build database with sign in and admin users")

        self.assertEqual(normalized["intrinsic_risk"], "high")
        self.assertEqual(normalized["operation_type"], "implementation")
        self.assertIn("false_positive_controls_triggered", normalized)
        with redirect_stdout(StringIO()):
            self.assertEqual(cli_main(["normalize", "--task", "change login button color", "--json"]), 0)


def _tasks():
    return json.loads((DATA_DIR / "normalizer_adversarial_tasks.json").read_text(encoding="utf-8"))["tasks"]


def _route(task):
    return route(
        project_name=task["project_name"],
        task_description=task["task_description"],
        files_touched=task.get("files_touched", []),
        previous_failure_count=task.get("previous_failure_count", 0),
        profile_name=task.get("profile_name", "balanced"),
    )


if __name__ == "__main__":
    unittest.main()
