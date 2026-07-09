import json
import shutil
import tempfile
import unittest
from pathlib import Path

from agentic_router.config_validation import CONFIG_FILES, config_summary, validate_config
from agentic_router.models import DATA_DIR


class ConfigValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmp.name)
        for filename in CONFIG_FILES.values():
            shutil.copyfile(DATA_DIR / filename, self.data_dir / filename)

    def tearDown(self):
        self.tmp.cleanup()

    def test_valid_config_passes(self):
        self.assertTrue(validate_config(data_dir=self.data_dir)["ok"])

    def test_broken_alias_fails(self):
        aliases = self._read("model_aliases.json")
        aliases["aliases"]["devspace-cheap"]["primary"] = "Nope 1.0"
        self._write("model_aliases.json", aliases)

        result = validate_config(data_dir=self.data_dir)

        self.assertFalse(result["ok"])
        self.assertTrue(any("unknown model" in error for error in result["errors"]))

    def test_profile_pointing_to_unknown_alias_fails(self):
        profiles = self._read("routing_profiles.json")
        profiles["profiles"]["balanced"]["allowed_model_aliases"].append("devspace-missing")
        self._write("routing_profiles.json", profiles)

        result = validate_config(data_dir=self.data_dir)

        self.assertFalse(result["ok"])
        self.assertTrue(any("unknown alias" in error for error in result["errors"]))

    def test_golden_task_with_unknown_project_is_flagged(self):
        golden = self._read("golden_tasks.json")
        golden["tasks"][0]["project_name"] = "Missing Project"
        self._write("golden_tasks.json", golden)

        result = validate_config(data_dir=self.data_dir)

        self.assertTrue(result["ok"])
        self.assertTrue(any("unknown project" in warning for warning in result["warnings"]))

    def test_secret_looking_config_value_is_rejected(self):
        projects = self._read("projects.json")
        projects["projects"][0]["keywords"].append("token=ABC123")
        self._write("projects.json", projects)

        self.assertFalse(validate_config(data_dir=self.data_dir)["ok"])

    def test_config_summary_counts(self):
        summary = config_summary(data_dir=self.data_dir)

        self.assertGreater(summary["total_projects"], 0)
        self.assertEqual(summary["validation_status"], "pass")

    def _read(self, filename):
        return json.loads((self.data_dir / filename).read_text(encoding="utf-8"))

    def _write(self, filename, data):
        (self.data_dir / filename).write_text(json.dumps(data), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
