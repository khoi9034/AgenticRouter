import json
import shutil
import tempfile
import unittest
from pathlib import Path

from agentic_router.config_studio import add_project, export_config, import_config
from agentic_router.config_validation import CONFIG_FILES
from agentic_router.models import DATA_DIR


class ConfigStudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name) / "data"
        self.data_dir.mkdir()
        for filename in CONFIG_FILES.values():
            shutil.copyfile(DATA_DIR / filename, self.data_dir / filename)
        shutil.copyfile(DATA_DIR / "enterprise_gateway_templates.json", self.data_dir / "enterprise_gateway_templates.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_config_export_creates_bundle(self):
        output = Path(self.tmp.name) / "bundle.json"
        result = export_config(output, data_dir=self.data_dir)

        bundle = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result["output"], str(output))
        self.assertIn("projects", bundle)
        self.assertIn("enterprise_template_metadata", bundle)

    def test_import_dry_run_validates_without_writing(self):
        output = Path(self.tmp.name) / "bundle.json"
        export_config(output, data_dir=self.data_dir)
        before = (self.data_dir / "projects.json").read_text(encoding="utf-8")

        result = import_config(output, dry_run=True, data_dir=self.data_dir)

        self.assertFalse(result["applied"])
        self.assertEqual(before, (self.data_dir / "projects.json").read_text(encoding="utf-8"))

    def test_add_project_validates_risk_level(self):
        with self.assertRaises(ValueError):
            add_project({"project_name": "Bad Risk", "risk_level": "critical"}, data_dir=self.data_dir)

        result = add_project(
            {
                "project_name": "Facilities Work Orders",
                "department": "Facilities",
                "status": "planning",
                "risk_level": "medium",
                "live_prod": False,
                "sensitive_domains": "",
                "routing_notes": "internal workflow planning",
            },
            data_dir=self.data_dir,
        )

        self.assertTrue(result["saved"])
        self.assertEqual(result["project"]["default_tier"], "mid")

    def test_add_project_rejects_secret_looking_fields(self):
        with self.assertRaises(ValueError):
            add_project(
                {
                    "project_name": "Unsafe",
                    "department": "IT",
                    "status": "planning",
                    "risk_level": "low",
                    "live_prod": False,
                    "sensitive_domains": "",
                    "routing_notes": "token=ABC123",
                },
                data_dir=self.data_dir,
            )


if __name__ == "__main__":
    unittest.main()
