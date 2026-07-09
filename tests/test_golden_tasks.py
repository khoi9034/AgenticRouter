import unittest

from agentic_router.evaluator import evaluate_tasks, load_golden_tasks


class GoldenTaskTests(unittest.TestCase):
    def test_golden_tasks_pass(self):
        summary = evaluate_tasks()

        self.assertGreaterEqual(summary["total"], 50)
        self.assertEqual(summary["failed"], 0, summary["failures"])

    def test_forced_bad_result_is_caught(self):
        task = load_golden_tasks()[0]

        def bad_route(**_kwargs):
            return {
                "model_tier": "advanced",
                "risk_level": "critical",
                "human_review_required": True,
                "reason": "",
                "context_policy": "",
                "escalation_policy": "",
                "matched_rules": [],
            }

        summary = evaluate_tasks([task], route_fn=bad_route)

        self.assertEqual(summary["failed"], 1)
        self.assertTrue(summary["failures"][0]["mismatches"])


if __name__ == "__main__":
    unittest.main()

