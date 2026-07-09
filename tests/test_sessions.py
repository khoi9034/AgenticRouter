import os
import tempfile
import unittest
from pathlib import Path

from agentic_router.router import route
from agentic_router.sessions import summarize_sessions


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "session_cache.jsonl"
        self.old_sessions = os.environ.get("AGENTIC_ROUTER_SESSIONS")
        os.environ["AGENTIC_ROUTER_SESSIONS"] = str(self.path)

    def tearDown(self):
        if self.old_sessions is None:
            os.environ.pop("AGENTIC_ROUTER_SESSIONS", None)
        else:
            os.environ["AGENTIC_ROUTER_SESSIONS"] = self.old_sessions
        self.tmp.cleanup()

    def test_same_session_reuses_model_for_low_risk_followup(self):
        first = route(
            "Diana Test Project",
            "Make hello world prettier",
            ["index.html"],
            session_id="low-1",
            profile_name="cost_saver",
        )
        second = route(
            "Diana Test Project",
            "Adjust the CSS color",
            ["style.css"],
            session_id="low-1",
            profile_name="max_quality",
        )

        self.assertTrue(second["sticky_route_used"])
        self.assertEqual(second["selected_model_alias"], first["selected_model_alias"])
        self.assertEqual(second["selected_model"], first["selected_model"])

    def test_same_session_does_not_reuse_if_risk_increases(self):
        route("Diana Test Project", "Make hello world prettier", ["index.html"], session_id="risk-1")
        result = route(
            "Diana Test Project",
            "Add auth SQL database login",
            ["auth/login.py"],
            session_id="risk-1",
        )

        self.assertFalse(result["sticky_route_used"])
        self.assertEqual(result["model_tier"], "advanced")

    def test_previous_failure_count_escalates_and_ignores_stickiness(self):
        route("Diana Test Project", "Update README copy", ["README.md"], session_id="fail-1")
        result = route(
            "Diana Test Project",
            "Update README copy again",
            ["README.md"],
            session_id="fail-1",
            previous_failure_count=2,
        )

        self.assertFalse(result["sticky_route_used"])
        self.assertEqual(result["model_tier"], "mid")
        self.assertIn("previous_failures_escalate", result["matched_rules"])

    def test_session_cache_does_not_store_sensitive_task_text(self):
        route(
            "Veteran's Intake Application",
            "Fix auth ping redirect",
            ["Auth/ping.php"],
            session_id="sensitive-1",
        )
        raw = self.path.read_text(encoding="utf-8")

        self.assertNotIn("Fix auth ping redirect", raw)
        self.assertIn("[redacted-sensitive-task]", raw)

    def test_session_summary_counts_records(self):
        route("Diana Test Project", "Make hello world prettier", ["index.html"], session_id="summary-1")
        route("Diana Test Project", "Adjust CSS color", ["style.css"], session_id="summary-1")
        summary = summarize_sessions(path=self.path)

        self.assertEqual(summary["total_sessions"], 1)
        self.assertEqual(summary["sticky_routes_used"], 1)
        self.assertEqual(summary["sessions_by_project"], {"Diana Test Project": 2})


if __name__ == "__main__":
    unittest.main()
