import sys
import os
import json
import tempfile
import queue
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.tester import Tester
from communication.message import Message
from communication.message_channel import MessageChannel
from workspace.workspace_manager import WorkspaceManager
import config

try:
    Tester(None, None)
    assert False
except TypeError as e:
    assert "channel must be a MessageChannel instance" in str(e)

channel = MessageChannel()
try:
    Tester(channel, None)
    assert False
except TypeError as e:
    assert "workspace must be a WorkspaceManager instance" in str(e)

with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")
    wm = WorkspaceManager()
    tester = Tester(channel, wm)

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    success_file = os.path.join(config.OUTPUT_DIR, "success.py")
    with open(success_file, 'w') as f:
        f.write("print('hello')")
    fail_file = os.path.join(config.OUTPUT_DIR, "fail.py")
    with open(fail_file, 'w') as f:
        f.write("import sys; sys.exit(1)")
    slow_file = os.path.join(config.OUTPUT_DIR, "slow.py")
    with open(slow_file, 'w') as f:
        f.write("import time; time.sleep(10)")

    msg = Message(sender="supervisor", receiver="tester", msg_type="CommandMsg", phase=1, payload={"filepath": success_file})
    result = tester.process_command(msg)
    assert result.payload["status"] == "passed"
    assert result.payload["returncode"] == 0
    assert "hello" in result.payload["stdout"]

    msg = Message(sender="supervisor", receiver="tester", msg_type="CommandMsg", phase=1, payload={"filepath": fail_file})
    result = tester.process_command(msg)
    assert result.payload["status"] == "failed"
    assert result.payload["returncode"] == 1

    msg = Message(sender="supervisor", receiver="tester", msg_type="CommandMsg", phase=1, payload={"filepath": slow_file})
    result = tester.process_command(msg)
    assert result.payload["status"] == "timeout"

    outside_file = os.path.join(tmp, "outside.txt")
    with open(outside_file, 'w') as f:
        f.write("outside")
    msg = Message(sender="supervisor", receiver="tester", msg_type="CommandMsg", phase=1, payload={"filepath": outside_file})
    result = tester.process_command(msg)
    assert result.payload["status"] == "error"
    assert "outside output directory" in result.payload["reason"]

    msg = Message(sender="supervisor", receiver="tester", msg_type="CommandMsg", phase=1, payload={})
    result = tester.process_command(msg)
    assert result.payload["status"] == "error"
    assert "Missing or invalid filepath" in result.payload["reason"]

    msg = Message(sender="supervisor", receiver="tester", msg_type="ResultMsg", phase=1, payload={"filepath": success_file})
    result = tester.process_command(msg)
    assert result.payload["status"] == "error"
    assert "Invalid message type" in result.payload["reason"]

    msg = Message(sender="supervisor", receiver="tester", msg_type="CommandMsg", phase=1, payload=None)
    result = tester.process_command(msg)
    assert result.payload["status"] == "error"

    with open(config.TEST_RESULTS_FILE) as f:
        test_results_text = f.read()
    assert "passed" in test_results_text
    with open(config.LOG_FILE) as f:
        log_text = f.read()
    assert "Tester passed:" in log_text

    msg_step = Message(sender="supervisor", receiver="tester", msg_type="CommandMsg", phase=2, payload={"filepath": success_file})
    channel.send(msg_step)
    assert tester.step() == True
    result_step = channel.receive("supervisor", timeout=0.5)
    assert result_step.msg_type == "ResultMsg"
    assert result_step.payload["status"] == "passed"
    assert result_step.sender == "tester"

    assert tester.step() == False

    print("PHASE 4.1 PASSED")