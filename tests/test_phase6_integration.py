import sys
import os
import json
import tempfile
import queue
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
    wm = WorkspaceManager()
    channel = MessageChannel()
    supervisor = Supervisor(channel, wm)

    supervisor.set_idea("Calculator")
    assert supervisor.step()
    msg = channel.receive("engineer", timeout=0.1)
    assert msg.payload["action"] == "design_structure"

    channel.send(Message(sender="engineer", receiver="supervisor", msg_type="ResultMsg", phase=1, payload={
        "status": "success",
        "action": "design_structure",
        "structure": {
            "project_name": "Calc",
            "phases": [{"phase_number": 1, "modules": [{"filename": "main.py", "description": "Main", "dependencies": []}]}]
        }
    }))
    assert supervisor.step()
    msg = channel.receive("engineer", timeout=0.1)
    assert msg.payload["action"] == "generate_prompts"

    channel.send(Message(sender="engineer", receiver="supervisor", msg_type="ResultMsg", phase=1, payload={
        "status": "success",
        "action": "generate_prompts",
        "prompts": {"main.py": "print('hello')"}
    }))
    assert supervisor.step()
    msg = channel.receive("coder", timeout=0.1)
    assert msg.payload["filename"] == "main.py"

    channel.send(Message(sender="coder", receiver="supervisor", msg_type="ResultMsg", phase=1, payload={
        "status": "success",
        "action": "code",
        "filepath": os.path.join(config.OUTPUT_DIR, "main.py")
    }))
    assert supervisor.step()
    msg = channel.receive("tester", timeout=0.1)
    assert msg.payload["action"] == "test"

    channel.send(Message(sender="tester", receiver="supervisor", msg_type="ResultMsg", phase=1, payload={
        "status": "passed",
        "action": "test"
    }))
    assert supervisor.step()
    assert supervisor.status == "completed"
    with open(config.LOG_FILE) as f:
        log_text = f.read()
    assert "project completed" in log_text

    print("PHASE 6 INTEGRATION PASSED")