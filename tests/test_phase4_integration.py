import sys
import os
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from workspace.workspace_manager import WorkspaceManager
from communication.message import Message
from communication.message_channel import MessageChannel
from agents.coder import Coder
from agents.tester import Tester

with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")
    wm = WorkspaceManager()
    channel = MessageChannel()
    coder = Coder(channel, wm)
    tester = Tester(channel, wm)
    cmd_coder = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=4,
                        payload={"filename": "math.py", "code": "print(2 + 2)"})
    channel.send(cmd_coder)
    assert coder.step() == True
    coder_result = channel.receive("supervisor", timeout=0.5)
    assert coder_result.payload["status"] == "success"
    filepath = coder_result.payload["filepath"]
    cmd_tester = Message(sender="supervisor", receiver="tester", msg_type="CommandMsg", phase=4,
                         payload={"filepath": filepath})
    channel.send(cmd_tester)
    assert tester.step() == True
    tester_result = channel.receive("supervisor", timeout=0.5)
    assert tester_result.payload["status"] == "passed"
    with open(config.LOG_FILE) as f:
        log_text = f.read()
    assert "Coder wrote file:" in log_text
    assert "Tester passed:" in log_text
    with open(config.TEST_RESULTS_FILE) as f:
        test_results_text = f.read()
    assert "passed" in test_results_text
    print("PHASE 4 INTEGRATION PASSED")