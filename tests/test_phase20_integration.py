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
from agents.api_inspector import APIInspector

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
                {"name": "save_todos", "kind": "function", "parameters": [{"name": "todos", "type": "list"}], "returns": "bool"},
                {"name": "load_todos", "kind": "function", "parameters": [], "returns": "list"}
            ],
            "required_imports": [],
            "generated": True,
            "validated": False
        }
    }
    with open(os.path.join(config.WORKSPACE_DIR, "contracts.json"), "w") as f:
        json.dump(contracts, f)

    code = "def save_todos(todos: list) -> bool:\n    return True\n\ndef load_todos() -> list:\n    return []\n"
    with open(os.path.join(config.OUTPUT_DIR, "storage.py"), "w") as f:
        f.write(code)

    channel = MessageChannel()
    supervisor = Supervisor(channel, wm, debugger=None, api_inspector=APIInspector())
    supervisor.status = "waiting_for_coder"
    supervisor.modules = [{"filename": "storage.py"}]
    supervisor.current_module_index = 0

    msg = Message(
        sender="coder",
        receiver="supervisor",
        msg_type="ResultMsg",
        phase=1,
        payload={
            "status": "success",
            "filepath": os.path.join(config.OUTPUT_DIR, "storage.py")
        }
    )
    channel.send(msg)
    supervisor.step()

    assert supervisor.status == "waiting_for_tester"
    with open(os.path.join(config.WORKSPACE_DIR, "contracts.json"), "r") as f:
        contracts_after = json.load(f)
    assert contracts_after == contracts

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
                {"name": "save_todos", "kind": "function", "parameters": [{"name": "todos", "type": "list"}], "returns": "bool"},
                {"name": "load_todos", "kind": "function", "parameters": [], "returns": "list"}
            ],
            "required_imports": [],
            "generated": True,
            "validated": False
        }
    }
    with open(os.path.join(config.WORKSPACE_DIR, "contracts.json"), "w") as f:
        json.dump(contracts, f)

    code_missing = "def save_todos(todos: list) -> bool:\n    return True\n"
    with open(os.path.join(config.OUTPUT_DIR, "storage.py"), "w") as f:
        f.write(code_missing)

    channel = MessageChannel()
    supervisor = Supervisor(channel, wm, debugger=None, api_inspector=APIInspector())
    supervisor.status = "waiting_for_coder"
    supervisor.modules = [{"filename": "storage.py"}]
    supervisor.current_module_index = 0

    msg = Message(
        sender="coder",
        receiver="supervisor",
        msg_type="ResultMsg",
        phase=1,
        payload={
            "status": "success",
            "filepath": os.path.join(config.OUTPUT_DIR, "storage.py")
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

print("PHASE 20.4 PASSED")