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
        os.environ["AGENTIC_ROUTER_OUTCOMES"] = os.path.join(cls.tmp.name, "outcomes.jsonl")
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
        cls.tmp.cleanup()

    def test_index_loads(self):
        body = urlopen(f"{self.base_url}/", timeout=5).read().decode("utf-8")

        self.assertIn("DevSpace Smart Router", body)

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
