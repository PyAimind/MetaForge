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

class MockInspectorValid:
    def inspect(self, filepath, exports):
        return {"valid": True, "errors": []}

class MockInspectorInvalid:
    def inspect(self, filepath, exports):
        return {"valid": False, "errors": ["Missing export: greet"]}

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
            "exports": [{"name": "greet", "kind": "function"}],
            "required_imports": [],
            "generated": True,
            "validated": False
        }
    }
    with open(os.path.join(config.WORKSPACE_DIR, "contracts.json"), "w") as f:
        json.dump(contracts, f)

    dummy_code = "def greet(name: str) -> str:\n    return f\"Hello {name}\"\n"
    with open(os.path.join(config.OUTPUT_DIR, "greeter.py"), "w") as f:
        f.write(dummy_code)

    channel = MessageChannel()
    supervisor = Supervisor(channel, wm, api_inspector=MockInspectorValid())
    supervisor.status = "waiting_for_coder"
    supervisor.modules = [{"filename": "greeter.py"}]
    supervisor.current_module_index = 0

    msg = Message(
        sender="coder",
        receiver="supervisor",
        msg_type="ResultMsg",
        phase=1,
        payload={
            "status": "success",
            "filepath": os.path.join(config.OUTPUT_DIR, "greeter.py")
        }
    )
    channel.send(msg)
    supervisor.step()
    with open(os.path.join(config.WORKSPACE_DIR, "contracts.json"), "r") as f:
        contracts_after = json.load(f)
    assert contracts_after["greeter.py"]["generated"] == True
    assert contracts_after["greeter.py"]["validated"] == False
    assert supervisor.status == "waiting_for_tester"
    try:
        tester_msg = channel.receive("tester", timeout=0.1)
        assert tester_msg.payload["filepath"] == os.path.join(config.OUTPUT_DIR, "greeter.py")
    except queue.Empty:
        assert False, "Expected Tester message but queue was empty"

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
            "exports": [{"name": "greet", "kind": "function"}],
            "required_imports": [],
            "generated": True,
            "validated": False
        }
    }
    with open(os.path.join(config.WORKSPACE_DIR, "contracts.json"), "w") as f:
        json.dump(contracts, f)

    with open(os.path.join(config.OUTPUT_DIR, "greeter.py"), "w") as f:
        f.write(dummy_code)

    channel = MessageChannel()
    supervisor = Supervisor(channel, wm, api_inspector=MockInspectorInvalid())
    supervisor.status = "waiting_for_coder"
    supervisor.modules = [{"filename": "greeter.py"}]
    supervisor.current_module_index = 0

    msg2 = Message(
        sender="coder",
        receiver="supervisor",
        msg_type="ResultMsg",
        phase=1,
        payload={
            "status": "success",
            "filepath": os.path.join(config.OUTPUT_DIR, "greeter.py")
        }
    )
    channel.send(msg2)
    supervisor.step()
    assert supervisor.fix_attempts["greeter.py"] == 1
    assert supervisor.status == "waiting_for_engineer"
    try:
        engineer_msg = channel.receive("engineer", timeout=0.1)
        assert engineer_msg.payload["is_fix"] == True
    except queue.Empty:
        assert False, "Expected Engineer message but queue was empty"
    try:
        channel.receive("tester", timeout=0.1)
        assert False, "Tester message was sent but should have been blocked"
    except queue.Empty:
        pass

print("PHASE 19.3 PASSED")