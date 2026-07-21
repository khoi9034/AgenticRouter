import json
import os
import threading
import tempfile
import unittest
from urllib.request import Request, urlopen

from agentic_router.web import make_server


class WebSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.old_outcomes = os.environ.get("AGENTIC_ROUTER_OUTCOMES")
        cls.old_traces = os.environ.get("AGENTIC_ROUTER_TRACES")
        os.environ["AGENTIC_ROUTER_OUTCOMES"] = os.path.join(cls.tmp.name, "outcomes.jsonl")
        os.environ["AGENTIC_ROUTER_TRACES"] = os.path.join(cls.tmp.name, "traces.jsonl")
        cls.server = make_server(port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=5)
        cls.server.server_close()
        if cls.old_outcomes is None:
            os.environ.pop("AGENTIC_ROUTER_OUTCOMES", None)
        else:
            os.environ["AGENTIC_ROUTER_OUTCOMES"] = cls.old_outcomes
        if cls.old_traces is None:
            os.environ.pop("AGENTIC_ROUTER_TRACES", None)
        else:
            os.environ["AGENTIC_ROUTER_TRACES"] = cls.old_traces
        cls.tmp.cleanup()

    def test_index_loads(self):
        body = urlopen(f"{self.base_url}/", timeout=5).read().decode("utf-8")

        self.assertIn("DevSpace Smart Router", body)
        self.assertIn("Enterprise Exports", body)

    def test_export_template_link_loads(self):
        body = urlopen(f"{self.base_url}/exports/gateway/guardrails_policy.example.yaml", timeout=5).read().decode("utf-8")

        self.assertIn("guardrails_policy", body)

    def test_projects_route_and_eval_apis(self):
        projects = self._get_json("/api/projects")
        self.assertTrue(any(item["name"] == "Diana Test Project" for item in projects["projects"]))

        result = self._post_json(
            "/api/route",
            {
                "project_name": "Diana Test Project",
                "task_description": "Make the hello world page background prettier",
                "files_touched": ["index.html", "style.css"],
                "previous_failure_count": 0,
            },
        )
        self.assertEqual(result["model_tier"], "cheap")
        self.assertTrue(result["route_id"].startswith("ar_"))
        self.assertIn("context_pack", result)
        self.assertIn("run_packet", result)
        self.assertIn("normalized_task", result)
        self.assertEqual(result["run_packet"]["route_id"], result["route_id"])

        context = self._post_json(
            "/api/context",
            {
                "project_name": "Diana Test Project",
                "task_description": "Make the hello world page background prettier",
                "files_touched": ["index.html", "style.css"],
                "previous_failure_count": 0,
            },
        )
        self.assertIn(context["context_size"], {"tiny", "small"})

        packet = self._post_json(
            "/api/packet",
            {
                "project_name": "Diana Test Project",
                "task_description": "Make the hello world page background prettier",
                "files_touched": ["index.html", "style.css"],
                "previous_failure_count": 0,
            },
        )
        self.assertIn("execution_prompt", packet)
        self.assertIn("run_contract", packet)

        contract = self._post_json(
            "/api/v1/contract",
            {
                "project_name": "Diana Test Project",
                "task_description": "Make the hello world page background prettier",
                "files_touched": ["index.html", "style.css"],
            },
        )
        guard = self._post_json(
            "/api/v1/contract/check",
            {"contract": contract["run_contract"], "changed_files": ["index.html", "style.css"]},
        )
        self.assertEqual(guard["scope_guard"]["decision"], "pass")
        diff_review = self._post_json(
            "/api/v1/diff-review",
            {
                "project_name": "Diana Test Project",
                "task_description": "Make page prettier",
                "git_diff": "diff --git a/style.css b/style.css\n--- a/style.css\n+++ b/style.css\n@@ -1 +1 @@\n-.x{color:blue}\n+.x{color:green}\n",
            },
        )
        self.assertEqual(diff_review["diff_review"]["decision"], "pass")

        feedback = self._post_json(
            "/api/feedback",
            {
                "route_id": result["route_id"],
                "accepted": True,
                "task_succeeded": True,
                "actual_model": "Haiku 4.5",
                "recommendation_fit": "right",
                "notes": "web smoke",
            },
        )
        self.assertTrue(feedback["saved"])

        summary = self._get_json("/api/eval")
        self.assertEqual(summary["failed"], 0)

        observability = self._get_json("/api/observability")
        self.assertFalse(observability["status"]["remote_tracing_enabled"])
        self.assertGreaterEqual(observability["summary"]["total_traces"], 1)

        config = self._get_json("/api/config/summary")
        self.assertEqual(config["validation_status"], "pass")
        self.assertGreater(config["total_projects"], 0)

        scenarios = self._get_json("/api/scenarios")
        self.assertIn("mixed_devspace_month", scenarios["scenarios"])
        simulation = self._post_json("/api/simulate", {"scenario": "docs_heavy_week"})
        self.assertGreater(simulation["summary"]["total_tasks"], 0)

    def _get_json(self, path):
        return json.loads(urlopen(f"{self.base_url}{path}", timeout=5).read())

    def _post_json(self, path, payload):
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return json.loads(urlopen(request, timeout=5).read())


if __name__ == "__main__":
    unittest.main()
