import sys
import os
import tempfile
import queue
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from workspace.workspace_manager import WorkspaceManager
from communication.message import Message
from communication.message_channel import MessageChannel
from agents.supervisor import Supervisor

class SpyDebugger:
    def __init__(self):
        self.calls = []
    def analyze_error(self, filepath, stderr, stdout, return_code):
        self.calls.append((filepath, stderr, stdout, return_code))
        return {
            "diagnosis": "TestDiagnosis",
            "root_cause": "TestRootCause",
            "suggested_fix": "TestFix",
            "confidence": 0.9
        }

with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")

    wm = WorkspaceManager()
    channel = MessageChannel()
    spy_debugger = SpyDebugger()
    supervisor = Supervisor(channel, wm, spy_debugger)

    supervisor.status = "waiting_for_tester"
    supervisor.modules = [{"filename": "test.py", "description": "test", "dependencies": [], "purpose": "test"}]
    supervisor.current_module_index = 0
    supervisor.prompts = {"test.py": "# test"}
    supervisor.fix_attempts = {}

    msg = Message(sender="tester", receiver="supervisor", msg_type="ResultMsg", phase=1,
                  payload={"status": "failed", "filepath": "test.py", "stderr": "Error", "stdout": "", "return_code": 1})
    channel.send(msg)

    assert supervisor.step()

    assert len(spy_debugger.calls) > 0

    eng_msg = channel.receive("engineer", timeout=0.1)
    assert "debugger_diagnosis" in eng_msg.payload
    assert eng_msg.payload["debugger_diagnosis"]["diagnosis"] == "TestDiagnosis"

    print("PHASE 16.3 PASSED")