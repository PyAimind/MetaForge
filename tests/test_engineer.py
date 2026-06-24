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
from agents.engineer import Engineer

try:
    Engineer(None, None)
    assert False
except TypeError as e:
    assert "channel must be a MessageChannel instance" in str(e)

channel = MessageChannel()
try:
    Engineer(channel, None)
    assert False
except TypeError as e:
    assert "workspace must be a WorkspaceManager instance" in str(e)

with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")
    wm = WorkspaceManager()
    engineer = Engineer(channel, wm)

    msg = Message(sender="supervisor", receiver="engineer", msg_type="ResultMsg", phase=1, payload={})
    result = engineer.process_command(msg)
    assert result.payload["status"] == "error"
    assert "Invalid message type" in result.payload["reason"]

    msg = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=1,
                  payload={"action": "design_structure", "idea": "Simple Calculator"})
    result = engineer.process_command(msg)
    assert result.payload["status"] == "success"
    assert result.payload["structure"]["project_name"] == "Simple Calculator"
    stored = wm.read_structure()
    assert stored == result.payload["structure"]
    with open(config.LOG_FILE) as f:
        log_data = json.load(f)
    assert any("Engineer designed structure for: Simple Calculator" in e["event"] for e in log_data)

    msg = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=1,
                  payload={"action": "design_structure"})
    result = engineer.process_command(msg)
    assert result.payload["status"] == "error"
    assert "Missing or invalid 'idea'" in result.payload["reason"]

    msg = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=1,
                  payload={"action": "generate_prompts"})
    result = engineer.process_command(msg)
    assert result.payload["status"] == "success"
    prompts = result.payload["prompts"]
    assert isinstance(prompts, dict)
    assert len(prompts) >= 3
    first_prompt = list(prompts.values())[0]
    assert "Write a Python file named" in first_prompt
    assert "### Strict Constraints" in first_prompt
    with open(config.LOG_FILE) as f:
        log_data = json.load(f)
    assert any("Engineer generated prompts for" in e["event"] for e in log_data)

    wm.write_structure({"project_name": "Empty", "phases": []})
    msg = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=1,
                  payload={"action": "generate_prompts"})
    result = engineer.process_command(msg)
    assert result.payload["status"] == "success"
    assert len(result.payload["prompts"]) == 0

    msg = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=1,
                  payload={"action": "generate_single_prompt", "module_info": {"filename": "test.py", "description": "test", "dependencies": []}})
    result = engineer.process_command(msg)
    assert result.payload["status"] == "success"
    assert "Write a Python file named `test.py`." in result.payload["prompt"]

    msg = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=1,
                  payload={"action": "generate_single_prompt"})
    result = engineer.process_command(msg)
    assert result.payload["status"] == "error"
    assert "Missing or invalid 'module_info'" in result.payload["reason"]

    msg = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=1,
                  payload={"action": "nonexistent"})
    result = engineer.process_command(msg)
    assert result.payload["status"] == "error"
    assert "Unknown action" in result.payload["reason"]

    msg_step = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=2,
                       payload={"action": "design_structure", "idea": "Test"})
    channel.send(msg_step)
    assert engineer.step() == True
    result_step = channel.receive("supervisor", timeout=0.5)
    assert result_step.payload["status"] == "success"

    assert engineer.step() == False

    print("PHASE 5.3 PASSED")