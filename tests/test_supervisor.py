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

def make_response(sender, status, **extra):
    payload = {"status": status}
    payload.update(extra)
    return Message(sender=sender, receiver="supervisor", msg_type="ResultMsg", phase=1, payload=payload)

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

    supervisor.set_idea("Simple Calculator")
    assert supervisor.step()
    msg = channel.receive("engineer", timeout=0.1)
    assert msg.payload["action"] == "design_structure"

    structure = {"project_name": "Simple Calculator", "phases": [{"phase_number": 1, "modules": [{"filename": "main.py", "description": "Main", "dependencies": []}]}]}
    channel.send(make_response("engineer", "success", structure=structure))
    assert supervisor.step()
    msg = channel.receive("engineer", timeout=0.1)
    assert msg.payload["action"] == "generate_prompts"

    prompts = {"main.py": "Write a Python file named `main.py`."}
    channel.send(make_response("engineer", "success", prompts=prompts))
    assert supervisor.step()
    msg = channel.receive("coder", timeout=0.1)
    assert msg.payload["action"] == "code"

    channel.send(make_response("coder", "success", filepath="/fake/main.py"))
    assert supervisor.step()
    msg = channel.receive("tester", timeout=0.1)
    assert msg.payload["action"] == "test"

    channel.send(make_response("tester", "passed"))
    assert supervisor.step()
    assert supervisor.status == "completed"
    with open(config.LOG_FILE) as f:
        log_data = json.load(f)
    assert any("project completed" in e["event"] for e in log_data)

    sup2 = Supervisor(channel, wm)
    sup2.set_idea("Simple Calculator")
    assert sup2.step()
    channel.receive("engineer", timeout=0.1)
    channel.send(make_response("engineer", "success", structure=structure))
    assert sup2.step()
    channel.receive("engineer", timeout=0.1)
    channel.send(make_response("engineer", "success", prompts=prompts))
    assert sup2.step()
    channel.receive("coder", timeout=0.1)
    channel.send(make_response("coder", "error", reason="syntax error"))
    assert sup2.step()
    msg = channel.receive("engineer", timeout=0.1)
    assert msg.payload["action"] == "generate_single_prompt"
    assert msg.payload["is_fix"] == True
    with open(config.LOG_FILE) as f:
        log_data = json.load(f)
    assert any("Coder error" in e["event"] for e in log_data)

    sup3 = Supervisor(channel, wm)
    sup3.set_idea("Simple Calculator")
    assert sup3.step()
    channel.receive("engineer", timeout=0.1)
    channel.send(make_response("engineer", "success", structure=structure))
    assert sup3.step()
    channel.receive("engineer", timeout=0.1)
    channel.send(make_response("engineer", "success", prompts=prompts))
    assert sup3.step()
    channel.receive("coder", timeout=0.1)
    channel.send(make_response("coder", "success", filepath="/fake/main.py"))
    assert sup3.step()
    channel.receive("tester", timeout=0.1)
    channel.send(make_response("tester", "failed"))
    assert sup3.step()
    msg = channel.receive("engineer", timeout=0.1)
    assert msg.payload["action"] == "generate_single_prompt"
    assert msg.payload["is_fix"] == True

    sup4 = Supervisor(channel, wm)
    sup4.set_idea("Test")
    assert sup4.step()
    channel.receive("engineer", timeout=0.1)
    assert not sup4.step()

    sup5 = Supervisor(channel, wm)
    sup5.set_idea("Test")
    assert sup5.step()
    channel.receive("engineer", timeout=0.1)
    channel.send(make_response("engineer", "success", structure=structure))
    assert sup5.step()
    channel.receive("engineer", timeout=0.1)
    channel.send(make_response("engineer", "success", prompts=prompts))
    assert sup5.step()
    channel.receive("coder", timeout=0.1)
    assert not sup5.step()

    print("PHASE 6.1 PASSED")