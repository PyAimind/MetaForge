import os
import sys
import json
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from workspace.workspace_manager import WorkspaceManager
from communication.message import Message
from communication.message_channel import MessageChannel
from agents.coder import Coder

class MockGenerator:
    def generate(self, module_info):
        return 'def greet(name: str) -> str:\n    return f"Hello {name}"\n'

with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")
    os.makedirs(config.WORKSPACE_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    wm = WorkspaceManager()
    contracts = {
        "greeter.py": {
            "module": "greeter.py",
            "dependencies": [],
            "exports": [],
            "required_imports": [],
            "generated": False,
            "validated": False
        }
    }
    with open(os.path.join(config.WORKSPACE_DIR, "contracts.json"), "w") as f:
        json.dump(contracts, f)

    mock_gen = MockGenerator()
    channel = MessageChannel()
    coder = Coder(channel, wm, mock_gen, context_manager=None, knowledge_base=None)

    msg = Message(
        sender="supervisor",
        receiver="coder",
        msg_type="CommandMsg",
        phase=1,
        payload={
            "filename": "greeter.py",
            "description": "test module",
            "dependencies": [],
            "purpose": "greet",
            "code": ""
        }
    )

    result = coder.process_command(msg)
    assert result.payload["status"] == "success"

    with open(os.path.join(config.WORKSPACE_DIR, "contracts.json"), "r") as f:
        updated = json.load(f)
    assert updated["greeter.py"]["generated"] == True
    assert updated["greeter.py"]["validated"] == False

    print("PHASE 18.4.2 PASSED")