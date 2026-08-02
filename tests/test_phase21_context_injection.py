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
from project_design.context_manager import ContextManager

class SpyGenerator:
    def __init__(self):
        self.last_module_info = None
        self.call_count = 0
    def generate(self, module_info):
        self.call_count += 1
        self.last_module_info = module_info
        return "def main():\n    pass\n"

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
    ctx = ContextManager(config.OUTPUT_DIR)

    contracts = {
        "storage.py": {
            "module": "storage.py",
            "dependencies": [],
            "exports": [
                {
                    "name": "save_todos",
                    "kind": "function",
                    "parameters": [{"name": "todos", "type": "list"}],
                    "returns": "bool",
                    "constructor": None,
                    "methods": []
                },
                {
                    "name": "load_todos",
                    "kind": "function",
                    "parameters": [],
                    "returns": "list",
                    "constructor": None,
                    "methods": []
                }
            ],
            "required_imports": [],
            "generated": True,
            "validated": True
        }
    }
    with open(os.path.join(config.WORKSPACE_DIR, "contracts.json"), "w") as f:
        json.dump(contracts, f)

    ctx.add_module("storage.py", "def x(): pass")

    spy = SpyGenerator()
    channel = MessageChannel()
    coder = Coder(channel, wm, spy, ctx, knowledge_base=None)

    msg = Message(
        sender="supervisor",
        receiver="coder",
        msg_type="CommandMsg",
        phase=1,
        payload={
            "filename": "main.py",
            "description": "Main entry point",
            "dependencies": ["storage.py"],
            "purpose": "entry"
        }
    )

    result = coder.process_command(msg)
    assert result.payload["status"] == "success"
    assert spy.call_count == 1
    info = spy.last_module_info
    assert "project_context" in info
    ctx_data = info["project_context"]["generated_modules"]
    assert "storage.py" in ctx_data
    storage_contract = ctx_data["storage.py"]
    assert "exports" in storage_contract
    assert any(exp["name"] == "save_todos" for exp in storage_contract["exports"])
    assert any(exp["name"] == "load_todos" for exp in storage_contract["exports"])

    print("PHASE 21.4 PASSED")