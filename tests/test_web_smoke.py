import json
import threading
import unittest
from urllib.request import Request, urlopen

from agentic_router.web import make_server


class WebSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server(port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=5)
        cls.server.server_close()

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

