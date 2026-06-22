import sys
import os
import json
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from workspace.workspace_manager import WorkspaceManager
from communication.message import Message
from communication.message_channel import MessageChannel

with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    wm = WorkspaceManager()
    assert os.path.isdir(config.WORKSPACE_DIR)
    assert os.path.exists(config.PHASE_FILE)
    assert os.path.exists(config.LOG_FILE)
    assert os.path.exists(config.STRUCTURE_FILE)
    assert os.path.exists(config.TEST_RESULTS_FILE)
    channel = MessageChannel()
    cmd = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=2, payload={"task": "design"})
    res = Message(sender="engineer", receiver="supervisor", msg_type="ResultMsg", phase=2, payload={"status": "ok"})
    channel.send(cmd)
    got_cmd = channel.receive("engineer")
    assert got_cmd == cmd
    assert got_cmd.payload["task"] == "design"
    channel.send(res)
    got_res = channel.receive("supervisor")
    assert got_res == res
    assert got_res.payload["status"] == "ok"
    wm.log_event("Supervisor-Engineer message exchange successful", phase=2)
    wm.update_phase(2, "message_system", "tested")
    with open(config.LOG_FILE) as f:
        log = json.load(f)
    assert any("Supervisor-Engineer message exchange successful" in e["event"] for e in log)
    phase_data = wm.read_phase()
    assert phase_data["current_phase"] == 2
    assert phase_data["status"] == "tested"
    print("PHASE 2 INTEGRATION PASSED")