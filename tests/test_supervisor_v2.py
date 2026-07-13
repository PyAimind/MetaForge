import sys
import os
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from workspace.workspace_manager import WorkspaceManager
from communication.message import Message
from communication.message_channel import MessageChannel
from agents.supervisor import Supervisor
from agents.engineer import Engineer
from agents.coder import Coder
from agents.tester import Tester

class MockDesigner:
    def __init__(self):
        self.call_count = 0
    def design(self, idea):
        self.call_count += 1
        return {
            "project_name": "MockProject",
            "description": "A mock project",
            "phases": [
                {
                    "phase_number": 1,
                    "name": "Core",
                    "modules": [
                        {
                            "filename": "main.py",
                            "description": "Main module",
                            "dependencies": [],
                            "purpose": "main"
                        }
                    ]
                }
            ]
        }

class MockGenerator:
    def __init__(self):
        self.call_count = 0
        self.last_module_info = None
    def generate(self, module_info):
        self.call_count += 1
        self.last_module_info = module_info
        return "print('hello')"

class MockExecutor:
    def __init__(self):
        self.call_count = 0
        self.last_filepath = None
    def execute(self, filepath, working_directory=None, timeout_seconds=10):
        self.call_count += 1
        self.last_filepath = filepath
        return {
            "status": "passed",
            "return_code": 0,
            "stdout": "",
            "stderr": "",
            "execution_time": 0.1
        }

with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")

    try:
        wm = WorkspaceManager()
        channel = MessageChannel()
        mock_designer = MockDesigner()
        mock_generator = MockGenerator()
        mock_executor = MockExecutor()
        supervisor = Supervisor(channel, wm)
        engineer = Engineer(channel, wm, mock_designer)
        coder = Coder(channel, wm, mock_generator)
        tester = Tester(channel, wm, mock_executor)
        agents = [engineer, coder, tester]

        supervisor.set_idea("Simple Calculator")
        iterations = 0
        while True:
            keep_going = supervisor.step()
            for agent in agents:
                agent.step()
            if not keep_going and supervisor.status in ("completed", "error"):
                break
            iterations += 1
            assert iterations < 100, "Orchestration loop did not finish within 100 iterations"

        assert supervisor.status == "completed"
        assert mock_designer.call_count >= 1
        assert mock_generator.call_count >= 1
        assert mock_generator.last_module_info["filename"] == "main.py"
        assert mock_executor.call_count >= 1
        assert os.path.basename(mock_executor.last_filepath) == "main.py"
        structure = wm.read_structure()
        assert structure["project_name"] == "MockProject"
        assert len(structure["phases"]) == 1
        assert structure["phases"][0]["modules"][0]["filename"] == "main.py"

        print("PHASE 12.2 PASSED")
    except AssertionError as e:
        print(f"PHASE 12.2 FAILED: {e}")
    except Exception as e:
        print(f"PHASE 12.2 FAILED: {e}")