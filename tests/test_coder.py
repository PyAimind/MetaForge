import sys
import os
import json
import tempfile
import queue
from unittest.mock import patch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from workspace.workspace_manager import WorkspaceManager
from communication.message import Message
from communication.message_channel import MessageChannel
from agents.coder import Coder

try:
    Coder(None, None)
    assert False
except TypeError as e:
    assert "channel must be a MessageChannel instance" in str(e)

channel = MessageChannel()
try:
    Coder(channel, None)
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
    coder = Coder(channel, wm)

    msg = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=3,
                  payload={"filename": "test_output.py", "code": "x = 42"})
    result = coder.process_command(msg)
    assert result.sender == "coder"
    assert result.receiver == "supervisor"
    assert result.msg_type == "ResultMsg"
    assert result.phase == 3
    assert result.payload["status"] == "success"
    filepath = result.payload["filepath"]
    assert os.path.exists(filepath)
    with open(filepath, encoding='utf-8') as f:
        assert f.read() == "x = 42"
    with open(config.LOG_FILE) as f:
        log = json.load(f)
    assert any(("Coder wrote file: " + filepath) in e["event"] for e in log)

    msg_no_code = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=3,
                          payload={"filename": "simulated.py"})
    res_no_code = coder.process_command(msg_no_code)
    assert res_no_code.payload["status"] == "success"
    with open(res_no_code.payload["filepath"], encoding='utf-8') as f:
        assert f.read() == "# simulated code\nprint('Hello from MetaForge')"

    msg_trav = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=3,
                       payload={"filename": "../../etc/passwd", "code": "x"})
    res_trav = coder.process_command(msg_trav)
    assert res_trav.payload["status"] == "success"
    assert os.path.commonpath([config.OUTPUT_DIR, res_trav.payload["filepath"]]) == config.OUTPUT_DIR

    msg_nested = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=3,
                         payload={"filename": "src/core/main.py", "code": "print('nested')"})
    res_nested = coder.process_command(msg_nested)
    assert res_nested.payload["status"] == "success"
    nested_path = res_nested.payload["filepath"]
    assert os.path.dirname(nested_path) == config.OUTPUT_DIR
    assert os.path.basename(nested_path) == "main.py"
    with open(nested_path, encoding='utf-8') as f:
        assert f.read() == "print('nested')"

    msg_empty_fn = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=3,
                           payload={"filename": "", "code": "print(1)"})
    res_empty_fn = coder.process_command(msg_empty_fn)
    assert res_empty_fn.payload["status"] == "success"
    assert res_empty_fn.payload["filepath"].endswith("untitled.py")

    msg_over1 = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=3,
                        payload={"filename": "overwrite.py", "code": "first"})
    msg_over2 = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=3,
                        payload={"filename": "overwrite.py", "code": "second"})
    r1 = coder.process_command(msg_over1)
    r2 = coder.process_command(msg_over2)
    assert r1.payload["filepath"] == r2.payload["filepath"]
    with open(r2.payload["filepath"], encoding='utf-8') as f:
        assert f.read() == "second"

    msg_empty_payload = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=3, payload={})
    res_empty_payload = coder.process_command(msg_empty_payload)
    assert res_empty_payload.payload["status"] == "success"
    assert res_empty_payload.payload["filepath"].endswith("untitled.py")

    msg_uni = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=3,
                      payload={"filename": "farsi.py", "code": "print('سلام دنیا')"})
    res_uni = coder.process_command(msg_uni)
    with open(res_uni.payload["filepath"], encoding='utf-8') as f:
        assert f.read() == "print('سلام دنیا')"

    for i in range(3):
        m = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=3,
                    payload={"filename": f"multi_{i}.py", "code": f"print({i})"})
        channel.send(m)
    assert coder.step() and coder.step() and coder.step()
    files_in_order = []
    for _ in range(3):
        got = channel.receive("supervisor", timeout=0.5)
        assert got.payload["status"] == "success"
        files_in_order.append(os.path.basename(got.payload["filepath"]))
    assert files_in_order == ["multi_0.py", "multi_1.py", "multi_2.py"]

    msg_wrong_type = Message(sender="supervisor", receiver="coder", msg_type="ResultMsg", phase=3,
                             payload={"filename": "dummy.py", "code": "pass"})
    res_wrong = coder.process_command(msg_wrong_type)
    assert res_wrong.payload["status"] == "error"
    assert "reason" in res_wrong.payload

    msg_bad_phase = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=999,
                            payload={"filename": "phase.py", "code": "x=1"})
    res_bad_phase = coder.process_command(msg_bad_phase)
    assert res_bad_phase.phase == 999
    assert res_bad_phase.payload["status"] == "success"

    with patch('os.makedirs', side_effect=OSError("Permission denied")):
        msg_err = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=3,
                          payload={"filename": "fail.py", "code": "x=1"})
        res_err = coder.process_command(msg_err)
        assert res_err.payload["status"] == "error"
        assert "Permission denied" in res_err.payload["reason"]

    assert coder.step() == False

    print("PHASE 3.1 PASSED")