import json
import os
import shutil
import tempfile
import unittest
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from communication.message import Message
from communication.message_channel import MessageChannel
from workspace.workspace_manager import WorkspaceManager
from agents.tester import Tester
import config


class MockExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, filepath, working_directory=None, timeout_seconds=10, args=None):
        self.calls.append({
            "filepath": filepath,
            "working_directory": working_directory,
            "timeout_seconds": timeout_seconds,
            "args": args,
        })
        basename = os.path.basename(filepath)
        if basename == "missing.py":
            return {"status": "error", "return_code": -1, "stdout": "", "stderr": "nope", "execution_time": 0}
        if basename == "fail_stdout.py":
            return {"status": "passed", "return_code": 0, "stdout": "hello", "stderr": "", "execution_time": 0}
        if basename == "fail_return.py":
            return {"status": "passed", "return_code": 1, "stdout": "expected", "stderr": "", "execution_time": 0}
        if basename == "timeout.py":
            return {"status": "timeout", "return_code": -1, "stdout": "", "stderr": "timeout", "execution_time": 10}
        if basename == "good.py":
            return {"status": "passed", "return_code": 0, "stdout": "expected output", "stderr": "", "execution_time": 0}
        return {"status": "passed", "return_code": 0, "stdout": "", "stderr": "", "execution_time": 0}

    def classify_error(self, stderr):
        return "unknown"


class TestTesterGenericAcceptance(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.original_output = config.OUTPUT_DIR
        config.OUTPUT_DIR = self.temp_dir

        for filename in ["good.py", "fail_stdout.py", "fail_return.py", "timeout.py"]:
            with open(os.path.join(self.temp_dir, filename), "w") as f:
                f.write("pass")

        self.wm = WorkspaceManager()
        self.channel = MessageChannel()
        self.executor = MockExecutor()
        self.tester = Tester(self.channel, self.wm, self.executor)

    def tearDown(self):
        config.OUTPUT_DIR = self.original_output
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _build_message(self, acceptance_tests):
        return Message(
            sender="supervisor",
            receiver="tester",
            msg_type="CommandMsg",
            phase=1,
            payload={"acceptance_tests": acceptance_tests}
        )

    def test_valid_test_passes(self):
        tests = [{
            "description": "Good test",
            "entrypoint": "good.py",
            "args": [],
            "expected_stdout_contains": ["expected"],
            "expected_return_code": 0,
            "timeout_seconds": 5
        }]
        result = self.tester.process_command(self._build_message(tests))
        self.assertEqual(result.payload["status"], "passed")
        self.assertEqual(len(result.payload["tests"]), 1)
        self.assertTrue(result.payload["tests"][0]["passed"])
        self.assertEqual(result.payload["tests"][0]["status"], "passed")

    def test_stdout_missing_substring_fails(self):
        tests = [{
            "description": "Fail stdout",
            "entrypoint": "fail_stdout.py",
            "args": [],
            "expected_stdout_contains": ["missing"],
            "expected_return_code": 0,
            "timeout_seconds": 5
        }]
        result = self.tester.process_command(self._build_message(tests))
        self.assertEqual(result.payload["status"], "failed")
        self.assertFalse(result.payload["tests"][0]["passed"])
        self.assertEqual(result.payload["tests"][0]["status"], "failed")

    def test_return_code_mismatch_fails(self):
        tests = [{
            "description": "Fail return code",
            "entrypoint": "fail_return.py",
            "args": [],
            "expected_stdout_contains": ["expected"],
            "expected_return_code": 0,
            "timeout_seconds": 5
        }]
        result = self.tester.process_command(self._build_message(tests))
        self.assertEqual(result.payload["status"], "failed")
        self.assertFalse(result.payload["tests"][0]["passed"])

    def test_missing_entrypoint(self):
        tests = [{
            "description": "Missing entrypoint",
            "entrypoint": "missing.py",
            "args": [],
            "expected_stdout_contains": [],
            "expected_return_code": 0,
            "timeout_seconds": 5
        }]
        result = self.tester.process_command(self._build_message(tests))
        self.assertEqual(result.payload["status"], "failed")
        self.assertEqual(result.payload["tests"][0]["status"], "missing_entrypoint")

    def test_empty_acceptance_tests_unsupported(self):
        result = self.tester.process_command(self._build_message([]))
        self.assertEqual(result.payload["status"], "unsupported")
        self.assertIn("No acceptance tests provided", result.payload.get("reason", ""))

    def test_mixed_results_fail(self):
        tests = [
            {
                "description": "Good",
                "entrypoint": "good.py",
                "args": [],
                "expected_stdout_contains": ["expected"],
                "expected_return_code": 0,
                "timeout_seconds": 5
            },
            {
                "description": "Fail",
                "entrypoint": "fail_return.py",
                "args": [],
                "expected_stdout_contains": ["expected"],
                "expected_return_code": 0,
                "timeout_seconds": 5
            }
        ]
        result = self.tester.process_command(self._build_message(tests))
        self.assertEqual(result.payload["status"], "failed")
        self.assertFalse(all(t["passed"] for t in result.payload["tests"]))

    def test_acceptance_test_runs_in_isolated_temporary_directory(self):
        tests = [{
            "description": "Isolation test",
            "entrypoint": "good.py",
            "args": [],
            "expected_stdout_contains": ["expected"],
            "expected_return_code": 0,
            "timeout_seconds": 7
        }]
        self.tester.process_command(self._build_message(tests))
        self.assertEqual(len(self.executor.calls), 1)
        call = self.executor.calls[0]
        self.assertNotEqual(call["working_directory"], config.OUTPUT_DIR)
        self.assertFalse(os.path.exists(call["working_directory"]))

    def test_acceptance_test_forwards_args_and_timeout(self):
        tests = [{
            "description": "Args and timeout test",
            "entrypoint": "good.py",
            "args": ["add", "2", "3"],
            "expected_stdout_contains": ["expected"],
            "expected_return_code": 0,
            "timeout_seconds": 12
        }]
        self.tester.process_command(self._build_message(tests))
        self.assertEqual(len(self.executor.calls), 1)
        call = self.executor.calls[0]
        self.assertEqual(call["args"], ["add", "2", "3"])
        self.assertEqual(call["timeout_seconds"], 12)


if __name__ == "__main__":
    unittest.main()