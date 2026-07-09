import json
import tempfile
import unittest
from pathlib import Path

from agentic_router.outcomes import save_feedback, summarize_outcomes
from agentic_router.router import route


class OutcomesTests(unittest.TestCase):
    def test_saving_feedback_creates_valid_jsonl_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "outcomes.jsonl"
            result = route("Diana Test Project", "make hello world prettier", ["index.html"])

            record = save_feedback(
                result["route_id"],
                accepted=True,
                task_succeeded=True,
                actual_model="Haiku 4.5",
                recommendation_fit="right",
                notes="worked well",
                path=path,
            )

            saved = json.loads(path.read_text(encoding="utf-8").strip())
            self.assertEqual(saved, record)
            self.assertEqual(saved["project_name"], "Diana Test Project")
            self.assertEqual(saved["recommended_tier"], "cheap")
            self.assertNotIn("task_description", saved)

    def test_malformed_feedback_is_rejected(self):
        result = route("Diana Test Project", "make hello world prettier", ["index.html"])

        with self.assertRaises(ValueError):
            save_feedback(result["route_id"], "true", True, "Haiku 4.5", "right")
        with self.assertRaises(ValueError):
            save_feedback(result["route_id"], True, True, "Haiku 4.5", "right", "contains token")
        with self.assertRaises(ValueError):
            save_feedback("not-a-route-id", True, True, "Haiku 4.5", "right")

    def test_outcomes_summary_computes_counts(self):
        records = [
            {
                "project_name": "Diana Test Project",
                "recommended_tier": "cheap",
                "accepted": True,
                "task_succeeded": True,
                "recommendation_fit": "right",
                "escalation_reasons": ["cheap_content"],
            },
            {
                "project_name": "Veteran's Intake Application",
                "recommended_tier": "advanced",
                "accepted": False,
                "task_succeeded": False,
                "recommendation_fit": "too_cheap",
                "escalation_reasons": ["advanced_risk", "sensitive_project"],
            },
            {
                "project_name": "Grant Quarter Reporting",
                "recommended_tier": "mid",
                "accepted": True,
                "task_succeeded": None,
                "recommendation_fit": "overkill",
                "escalation_reasons": ["mid_complexity"],
            },
        ]

        summary = summarize_outcomes(records)

        self.assertEqual(summary["total_feedback_records"], 3)
        self.assertEqual(summary["acceptance_rate"], 0.6667)
        self.assertEqual(summary["task_success_rate"], 0.5)
        self.assertEqual(summary["overkill_count"], 1)
        self.assertEqual(summary["too_weak_count"], 1)
        self.assertEqual(summary["success_by_recommended_tier"], {"cheap": 1})
        self.assertEqual(summary["failure_by_project"], {"Veteran's Intake Application": 1})

    def test_route_result_has_route_id(self):
        result = route("Diana Test Project", "make hello world prettier", ["index.html"])

        self.assertTrue(result["route_id"].startswith("ar_"))


if __name__ == "__main__":
    unittest.main()

