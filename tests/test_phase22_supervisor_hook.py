import os
import sys
import json
import tempfile
import queue
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from workspace.workspace_manager import WorkspaceManager
from communication.message import Message
from communication.message_channel import MessageChannel
from agents.supervisor import Supervisor

class MockAnalyzer:
    def analyze(self, filepath, dep_contracts):
        return {"valid": False, "errors": [{"type": "missing_method", "class": "Storage", "function": "wrong_save", "line": 1}]}

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
        "storage.py": {
            "module": "storage.py",
            "dependencies": [],
            "exports": [
                {
                    "name": "Storage",
                    "kind": "class",
                    "constructor": {"parameters": [{"name": "path", "type": "str"}]},
                    "methods": [
                        {"name": "save", "kind": "function", "parameters": [{"name": "todos", "type": "list"}], "returns": "bool"}
                    ]
                }
            ],
            "required_imports": [],
            "generated": True,
            "validated": True
        },
        "cli.py": {
            "module": "cli.py",
            "dependencies": ["storage.py"],
            "exports": [],
            "required_imports": [],
            "generated": False,
            "validated": False
        }
    }
    with open(os.path.join(config.WORKSPACE_DIR, "contracts.json"), "w") as f:
        json.dump(contracts, f)

    with open(os.path.join(config.OUTPUT_DIR, "cli.py"), "w") as f:
        f.write("print('hello')")

    channel = MessageChannel()
    supervisor = Supervisor(channel, wm, semantic_analyzer=MockAnalyzer())
    supervisor.status = "waiting_for_coder"
    supervisor.modules = [{"filename": "storage.py"}, {"filename": "cli.py", "dependencies": ["storage.py"]}]
    supervisor.current_module_index = 1

    msg = Message(
        sender="coder",
        receiver="supervisor",
        msg_type="ResultMsg",
        phase=1,
        payload={
            "status": "success",
            "filepath": os.path.join(config.OUTPUT_DIR, "cli.py")
        }
    )
    channel.send(msg)
    supervisor.step()

    assert supervisor.status == "waiting_for_engineer"
    try:
        channel.receive("tester", timeout=0.1)
        assert False, "Tester message was sent but should have been blocked"
    except queue.Empty:
        pass
    assert supervisor.fix_attempts["cli.py"] == 1

    print("PHASE 22 SUPERVISOR HOOK PASSED")