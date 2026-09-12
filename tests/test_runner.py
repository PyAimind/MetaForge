import os
import sys
import time
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import tempfile
import shutil
import json

from project_store import ProjectStore
from ui.runner import RunManager


EVENT_STARTED = json.dumps({
    "v": 1, "ts": 1.0, "run_id": "r",
    "type": "run_started", "payload": {"idea": "x"},
})
EVENT_COMPLETED = json.dumps({
    "v": 1, "ts": 2.0, "run_id": "r",
    "type": "run_completed", "payload": {"total_runtime": 1.0, "iterations": 1},
})
EVENT_FAILED = json.dumps({
    "v": 1, "ts": 2.0, "run_id": "r",
    "type": "run_failed", "payload": {"reason": "boom", "total_runtime": 1.0},
})


class FakeProcess:
    """Fake subprocess that emits a fixed list of lines on stderr."""

    def __init__(self, lines):
        self.stderr = iter(lines)
        self.terminated = False

    def wait(self, timeout=None):
        return 0

    def terminate(self):
        self.terminated = True


class FakeBlockingProcess:
    """Fake subprocess that never ends unless terminated."""

    def __init__(self):
        self.terminated = False
        self.stderr = self._gen()

    def _gen(self):
        # Empty generator: yields nothing, blocks until terminated.
        while not self.terminated:
            time.sleep(0.05)
        if False:
            yield  # unreachable, keeps this function a generator

    def wait(self, timeout=None):
        return 0

    def terminate(self):
        self.terminated = True


class TestRunner(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="metaforge_runner_test_")
        self.projects_dir = os.path.join(self.temp_dir, "projects")
        self.store = ProjectStore(self.projects_dir)
        self.manager = RunManager(self.store)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _wait_for_status(self, project_id, expected, timeout=5.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            meta = self.store.get(project_id)
            if meta and meta.get("status") == expected:
                return True
            time.sleep(0.05)
        return False

    @patch("ui.runner.subprocess.Popen")
    def test_start_creates_project_and_emits_events(self, mock_popen):
        fake = FakeProcess([EVENT_STARTED, EVENT_COMPLETED])
        mock_popen.return_value = fake

        project_id = self.manager.start(idea="x", name="Test")
        self.assertTrue(project_id)

        self.assertTrue(self._wait_for_status(project_id, "completed"))

        events_path = os.path.join(self.projects_dir, project_id, "thinking.jsonl")
        with open(events_path, "r", encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
        self.assertEqual(len(lines), 2)

    @patch("ui.runner.subprocess.Popen")
    def test_start_rejects_concurrent_run(self, mock_popen):
        fake = FakeBlockingProcess()
        mock_popen.return_value = fake

        first_id = self.manager.start(idea="x", name="First")
        self.assertTrue(first_id)

        with self.assertRaises(RuntimeError):
            self.manager.start(idea="y", name="Second")

        self.manager.stop(first_id)

    @patch("ui.runner.subprocess.Popen")
    def test_subscribe_receives_events(self, mock_popen):
        real_id = self.store.create(name="S", idea="x")
        self.assertTrue(real_id)

        with patch.object(self.store, "create", return_value=real_id):
            fake = FakeProcess([EVENT_STARTED, EVENT_COMPLETED])
            mock_popen.return_value = fake

            q = self.manager.subscribe(real_id)
            self.manager.start(idea="x", name="S")

            self.assertTrue(self._wait_for_status(real_id, "completed"))

            received = []
            while not q.empty():
                received.append(q.get_nowait())
            self.assertEqual(len(received), 2)
            self.manager.unsubscribe(real_id, q)

    @patch("ui.runner.subprocess.Popen")
    def test_run_failed_status(self, mock_popen):
        fake = FakeProcess([EVENT_STARTED, EVENT_FAILED])
        mock_popen.return_value = fake

        project_id = self.manager.start(idea="x", name="Fail")
        self.assertTrue(self._wait_for_status(project_id, "failed"))

    @patch("ui.runner.subprocess.Popen")
    def test_stop_terminates_process(self, mock_popen):
        fake = FakeBlockingProcess()
        mock_popen.return_value = fake

        project_id = self.manager.start(idea="x", name="Block")
        self.assertTrue(self.manager.is_running(project_id))

        result = self.manager.stop(project_id)
        self.assertTrue(result)
        self.assertTrue(fake.terminated)


if __name__ == "__main__":
    unittest.main()