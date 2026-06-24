import sys
import os
import json
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from workspace.workspace_manager import WorkspaceManager
from communication.message import Message
from communication.message_channel import MessageChannel
from agents.engineer import Engineer
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
    engineer = Engineer(channel, wm)
    coder = Coder(channel, wm)
    tester = Tester(channel, wm)
    try:
        msg = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=5, payload={"action": "design_structure", "idea": "Simple Calculator"})
        channel.send(msg)
        assert engineer.step()
        res = channel.receive("supervisor", timeout=0.5)
        assert res.payload["status"] == "success"
        assert res.payload["structure"]["project_name"] == "Simple Calculator"
        msg = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=5, payload={"action": "generate_prompts"})
        channel.send(msg)
        assert engineer.step()
        res = channel.receive("supervisor", timeout=0.5)
        assert res.payload["status"] == "success"
        assert len(res.payload["prompts"]) >= 1
        msg = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=5, payload={"filename": "generated_module.py", "code": "print('engineer says hi')"})
        channel.send(msg)
        assert coder.step()
        res = channel.receive("supervisor", timeout=0.5)
        assert res.payload["status"] == "success"
        filepath = res.payload["filepath"]
        msg = Message(sender="supervisor", receiver="tester", msg_type="CommandMsg", phase=5, payload={"filepath": filepath})
        channel.send(msg)
        assert tester.step()
        res = channel.receive("supervisor", timeout=0.5)
        assert res.payload["status"] == "passed"
        with open(config.LOG_FILE) as f:
            log_text = f.read()
        assert "Engineer designed structure" in log_text
        assert "Engineer generated prompts" in log_text
        assert "Coder wrote file:" in log_text
        assert "Tester passed:" in log_text
        print("PHASE 5 INTEGRATION PASSED")
    except AssertionError:
        print("PHASE 5 INTEGRATION FAILED")