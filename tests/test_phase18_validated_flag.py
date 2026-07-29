import os
import sys
import json
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from workspace.workspace_manager import WorkspaceManager
from communication.message import Message
from communication.message_channel import MessageChannel
from agents.supervisor import Supervisor

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
            "generated": True,
            "validated": False
        }
    }
    with open(os.path.join(config.WORKSPACE_DIR, "contracts.json"), "w") as f:
        json.dump(contracts, f)

    channel = MessageChannel()
    supervisor = Supervisor(channel, wm)
    supervisor.status = "waiting_for_tester"
    supervisor.modules = [{"filename": "greeter.py"}]
    supervisor.current_module_index = 0

    msg = Message(
        sender="tester",
        receiver="supervisor",
        msg_type="ResultMsg",
        phase=1,
        payload={
            "status": "passed",
            "filepath": os.path.join(config.OUTPUT_DIR, "greeter.py"),
            "return_code": 0,
            "stdout": "",
            "stderr": "",
            "execution_time": 0.1
        }
    )
    channel.send(msg)
    supervisor.step()

    with open(os.path.join(config.WORKSPACE_DIR, "contracts.json"), "r") as f:
        updated = json.load(f)
    assert updated["greeter.py"]["validated"] == True
    assert updated["greeter.py"]["generated"] == True
    assert supervisor.status == "completed"

    print("PHASE 18.4.3 PASSED")