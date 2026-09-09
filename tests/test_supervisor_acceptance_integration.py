import os
import sys
import json
import tempfile
import shutil
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import config
from workspace.workspace_manager import WorkspaceManager
from communication.message import Message
from communication.message_channel import MessageChannel
from agents.supervisor import Supervisor
from agents.engineer import Engineer
from agents.coder import Coder
from agents.tester import Tester


class RecordingMessageChannel(MessageChannel):
    def __init__(self):
        super().__init__()
        self.sent_messages = []

    def send(self, message):
        self.sent_messages.append(message)
        return super().send(message)


class MockDesigner:
    def __init__(self, structure):
        self.structure = structure
        self.calls = []

    def design(self, idea):
        self.calls.append(idea)
        return self.structure


class MockGenerator:
    def __init__(self, code="# generated code\n"):
        self.code = code
        self.calls = []

    def generate(self, module_info):
        self.calls.append(module_info)
        if "repair_prompt" in module_info:
            return json.dumps({
                "storage.py": "fixed storage code",
                "cli.py": "fixed cli code"
            })
        return self.code


class MockExecutor:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def execute(self, filepath, working_directory=None, timeout_seconds=10, args=None):
        self.calls.append({
            "filepath": filepath,
            "working_directory": working_directory,
            "timeout_seconds": timeout_seconds,
            "args": args,
        })
        if self.results:
            return self.results.pop(0)
        return {"status": "passed", "return_code": 0, "stdout": "", "stderr": "", "execution_time": 0.0}

    def classify_error(self, stderr):
        return "unknown"


class TestSupervisorAcceptanceIntegration(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.original_config = {
            "WORKSPACE_DIR": config.WORKSPACE_DIR,
            "OUTPUT_DIR": config.OUTPUT_DIR,
            "PHASE_FILE": config.PHASE_FILE,
            "LOG_FILE": config.LOG_FILE,
            "STRUCTURE_FILE": config.STRUCTURE_FILE,
            "TEST_RESULTS_FILE": config.TEST_RESULTS_FILE,
        }
        config.WORKSPACE_DIR = os.path.join(self.temp_dir, "workspace")
        config.OUTPUT_DIR = os.path.join(self.temp_dir, "output")
        config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
        config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
        config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
        config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
        os.makedirs(config.WORKSPACE_DIR, exist_ok=True)
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)

        self.structure = {
            "project_name": "TestProject",
            "description": "Integration test",
            "phases": [
                {
                    "phase_number": 1,
                    "name": "Core",
                    "modules": [
                        {
                            "filename": "storage.py",
                            "description": "Storage module",
                            "dependencies": [],
                            "purpose": "storage",
                            "exports": [],
                            "required_imports": []
                        },
                        {
                            "filename": "cli.py",
                            "description": "CLI module",
                            "dependencies": ["storage.py"],
                            "purpose": "entry",
                            "exports": [],
                            "required_imports": []
                        }
                    ]
                }
            ],
            "acceptance_tests": [
                {
                    "description": "Help command works",
                    "entrypoint": "cli.py",
                    "args": ["--help"],
                    "expected_stdout_contains": ["usage:"],
                    "expected_return_code": 0,
                    "timeout_seconds": 10
                }
            ]
        }

        self.channel = RecordingMessageChannel()
        self.workspace = WorkspaceManager()
        self._write_contracts()

    def tearDown(self):
        for key, value in self.original_config.items():
            setattr(config, key, value)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_contracts(self):
        contracts = {}
        for phase in self.structure["phases"]:
            for mod in phase["modules"]:
                contracts[mod["filename"]] = {
                    "module": mod["filename"],
                    "dependencies": mod["dependencies"],
                    "exports": mod["exports"],
                    "required_imports": mod["required_imports"],
                    "generated": True,
                    "validated": True
                }
        with open(os.path.join(config.WORKSPACE_DIR, "contracts.json"), "w", encoding="utf-8") as f:
            json.dump(contracts, f, indent=2)

    def _setup_components(self, executor_results):
        designer = MockDesigner(self.structure)
        generator = MockGenerator("# generated code\n")
        executor = MockExecutor(executor_results)

        supervisor = Supervisor(self.channel, self.workspace, debugger=None, api_inspector=None, semantic_analyzer=None)
        engineer = Engineer(self.channel, self.workspace, designer, knowledge_base=None)
        coder = Coder(self.channel, self.workspace, generator, context_manager=None, knowledge_base=None)
        tester = Tester(self.channel, self.workspace, executor)

        agents = [engineer, coder, tester]
        return supervisor, agents, executor

    def _run_until_terminal(self, supervisor, agents, max_iterations=100):
        iteration = 0
        while supervisor.status not in ("completed", "error") and iteration < max_iterations:
            supervisor.step()
            for agent in agents:
                agent.step()
            iteration += 1

    def _get_sent_messages_by_receiver(self, receiver):
        return [m for m in self.channel.sent_messages if m.receiver == receiver]

    def _get_messages_by_predicate(self, predicate):
        return [m for m in self.channel.sent_messages if predicate(m)]

    def _run_acceptance_flow_and_assert(self, executor_results):
        supervisor, agents, _ = self._setup_components(executor_results)
        supervisor.set_idea("test")
        self._run_until_terminal(supervisor, agents)

        tester_messages = self._get_sent_messages_by_receiver("tester")
        module_commands = [m for m in tester_messages if "filepath" in m.payload]
        acceptance_commands = [m for m in tester_messages if "acceptance_tests" in m.payload]
        engineer_repair_commands = self._get_messages_by_predicate(
            lambda m: m.receiver == "engineer" and m.payload.get("action") == "generate_single_prompt" and m.payload.get("is_fix") is True
        )
        coder_repair_commands = self._get_messages_by_predicate(
            lambda m: m.receiver == "coder" and m.payload.get("action") == "code" and m.payload.get("is_fix") is True
        )

        # فقط پیام‌های Supervisor
        supervisor_messages = [m for m in self.channel.sent_messages if m.sender == "supervisor"]

        self.assertEqual(len(module_commands), 2, "Expected exactly 2 module test commands")
        self.assertEqual(len(acceptance_commands), 2, "Expected exactly 2 acceptance commands")
        self.assertTrue(engineer_repair_commands, "Expected an Engineer repair command")
        self.assertTrue(coder_repair_commands, "Expected a Coder repair command")

        self.assertEqual(acceptance_commands[0].payload["acceptance_tests"], self.structure["acceptance_tests"])
        self.assertEqual(acceptance_commands[1].payload["acceptance_tests"], self.structure["acceptance_tests"])

        # Use identity-based lookup because Message is a frozen dataclass with value equality
        first_acceptance_idx = next(
            i for i, m in enumerate(supervisor_messages)
            if m is acceptance_commands[0]
        )
        last_module_idx = max(supervisor_messages.index(m) for m in module_commands)
        self.assertLess(last_module_idx, first_acceptance_idx,
                        "All module tests must occur before final acceptance tests")

        second_acceptance_idx = next(
            i for i, m in enumerate(supervisor_messages)
            if m is acceptance_commands[1]
        )
        eng_repair_idx = supervisor_messages.index(engineer_repair_commands[0])
        coder_repair_idx = supervisor_messages.index(coder_repair_commands[0])

        self.assertGreater(eng_repair_idx, first_acceptance_idx,
                           "Engineer repair should occur after first acceptance failure")
        self.assertGreater(coder_repair_idx, eng_repair_idx,
                           "Coder repair should occur after Engineer repair")
        self.assertLess(coder_repair_idx, second_acceptance_idx,
                        "Coder repair should occur before second acceptance")

        expected_module_index = len(self.structure["phases"][0]["modules"])
        self.assertEqual(supervisor.current_module_index, expected_module_index,
                         "current_module_index should remain at the module count during acceptance")

        self.assertEqual(supervisor.status, "completed", "Supervisor should finish as completed")

        tester_to_supervisor = [m for m in self.channel.sent_messages
                                if m.sender == "tester" and m.receiver == "supervisor"]
        self.assertGreater(len(tester_to_supervisor), 0, "No Tester result messages found")
        final_tester_result = tester_to_supervisor[-1]
        self.assertEqual(final_tester_result.payload.get("status"), "passed",
                         "Final acceptance result should be passed")

    def test_acceptance_failure_repairs_and_completes(self):
        executor_results = [
            {"status": "passed", "return_code": 0, "stdout": "", "stderr": "", "execution_time": 0.0},
            {"status": "passed", "return_code": 0, "stdout": "", "stderr": "", "execution_time": 0.0},
            {"status": "failed", "return_code": 1, "stdout": "", "stderr": "error", "execution_time": 0.0},
            {"status": "passed", "return_code": 0, "stdout": "usage: test", "stderr": "", "execution_time": 0.0}
        ]
        self._run_acceptance_flow_and_assert(executor_results)

    def test_acceptance_timeout_repairs_and_completes(self):
        executor_results = [
            {"status": "passed", "return_code": 0, "stdout": "", "stderr": "", "execution_time": 0.0},
            {"status": "passed", "return_code": 0, "stdout": "", "stderr": "", "execution_time": 0.0},
            {"status": "timeout", "return_code": -1, "stdout": "", "stderr": "timeout", "execution_time": 10.0},
            {"status": "passed", "return_code": 0, "stdout": "usage: test", "stderr": "", "execution_time": 0.0}
        ]
        self._run_acceptance_flow_and_assert(executor_results)

    def test_acceptance_runtime_failure_repairs_and_completes(self):
        executor_results = [
            {"status": "passed", "return_code": 0, "stdout": "", "stderr": "", "execution_time": 0.0},
            {"status": "passed", "return_code": 0, "stdout": "", "stderr": "", "execution_time": 0.0},
            {"status": "runtime_failure", "return_code": 1, "stdout": "some output", "stderr": "runtime error", "execution_time": 0.0},
            {"status": "passed", "return_code": 0, "stdout": "usage: test", "stderr": "", "execution_time": 0.0}
        ]
        self._run_acceptance_flow_and_assert(executor_results)


if __name__ == "__main__":
    unittest.main()