import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import json
import shutil
import tempfile
import unittest

import config
from workspace.workspace_manager import WorkspaceManager


class TestWorkspaceManagerAcceptance(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

        self.original_values = {
            "WORKSPACE_DIR": config.WORKSPACE_DIR,
            "STRUCTURE_FILE": config.STRUCTURE_FILE,
            "PHASE_FILE": config.PHASE_FILE,
            "LOG_FILE": config.LOG_FILE,
            "TEST_RESULTS_FILE": config.TEST_RESULTS_FILE,
        }

        config.WORKSPACE_DIR = self.temp_dir
        config.STRUCTURE_FILE = os.path.join(
            self.temp_dir,
            "project_structure.json",
        )
        config.PHASE_FILE = os.path.join(
            self.temp_dir,
            "current_phase.json",
        )
        config.LOG_FILE = os.path.join(
            self.temp_dir,
            "build_log.json",
        )
        config.TEST_RESULTS_FILE = os.path.join(
            self.temp_dir,
            "test_results.json",
        )

    def tearDown(self):
        for name, value in self.original_values.items():
            setattr(config, name, value)

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_workspace_creates_empty_acceptance_tests(self):
        WorkspaceManager()

        self.assertTrue(os.path.exists(config.STRUCTURE_FILE))

        with open(config.STRUCTURE_FILE, "r", encoding="utf-8") as file:
            structure = json.load(file)

        self.assertEqual(
            structure,
            {
                "project_name": "",
                "phases": [],
                "acceptance_tests": [],
            },
        )


if __name__ == "__main__":
    unittest.main()