import sys
import os
import tempfile
import queue
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from workspace.workspace_manager import WorkspaceManager
from communication.message import Message
from communication.message_channel import MessageChannel
from agents.tester import Tester

class MockExecutor:
    def __init__(self, status="passed", return_code=0, stdout="", stderr="", execution_time=0.1):
        self.status = status
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr
        self.execution_time = execution_time
        self.call_count = 0
        self.last_filepath = None
    def execute(self, filepath, working_directory=None, timeout_seconds=10):
        self.call_count += 1
        self.last_filepath = filepath
        return {
            "status": self.status,
            "return_code": self.return_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "execution_time": self.execution_time
        }

class ErrorExecutor:
    def execute(self, filepath, working_directory=None, timeout_seconds=10):
        raise RuntimeError("boom")

with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    try:
        Tester(None, None, None)
        assert False
    except TypeError:
        pass
    ch = MessageChannel()
    try:
        Tester(ch, None, MockExecutor())
        assert False
    except TypeError:
        pass
    wm = WorkspaceManager()
    try:
        Tester(ch, wm, "not_an_executor")
        assert False
    except TypeError:
        pass
    Tester(ch, wm, MockExecutor())

    wm2 = WorkspaceManager()
    ch2 = MessageChannel()
    mock_exec = MockExecutor(status="passed", return_code=0, stdout="hello")
    tester = Tester(ch2, wm2, mock_exec)
    test_file = os.path.join(config.OUTPUT_DIR, "test.py")
    with open(test_file, 'w') as f:
        f.write("print('hello')")
    msg = Message(sender="supervisor", receiver="tester", msg_type="CommandMsg", phase=1,
                  payload={"filepath": test_file})
    ch2.send(msg)
    assert tester.step()
    resp = ch2.receive("supervisor", timeout=0.5)
    assert resp.payload["status"] == "passed"
    assert resp.payload["stdout"] == "hello"
    assert resp.payload["filepath"] == test_file
    assert mock_exec.call_count == 1

    wm3 = WorkspaceManager()
    ch3 = MessageChannel()
    mock_exec2 = MockExecutor(status="failed", return_code=1, stderr="Error")
    tester2 = Tester(ch3, wm3, mock_exec2)
    ch3.send(Message(sender="supervisor", receiver="tester", msg_type="CommandMsg", phase=1,
                     payload={"filepath": test_file}))
    assert tester2.step()
    resp2 = ch3.receive("supervisor", timeout=0.5)
    assert resp2.payload["status"] == "failed"
    assert resp2.payload["stderr"] == "Error"

    wm4 = WorkspaceManager()
    ch4 = MessageChannel()
    mock_exec3 = MockExecutor(status="timeout", return_code=-1)
    tester3 = Tester(ch4, wm4, mock_exec3)
    ch4.send(Message(sender="supervisor", receiver="tester", msg_type="CommandMsg", phase=1,
                     payload={"filepath": test_file}))
    assert tester3.step()
    resp3 = ch4.receive("supervisor", timeout=0.5)
    assert resp3.payload["status"] == "timeout"

    wm5 = WorkspaceManager()
    ch5 = MessageChannel()
    tester4 = Tester(ch5, wm5, MockExecutor())
    res_invalid = tester4.process_command(Message(sender="s", receiver="t", msg_type="ResultMsg", phase=1, payload={}))
    assert res_invalid.payload["status"] == "error"
    assert "Invalid message type" in res_invalid.payload["reason"]

    wm6 = WorkspaceManager()
    ch6 = MessageChannel()
    tester5 = Tester(ch6, wm6, MockExecutor())
    res_missing = tester5.process_command(Message(sender="s", receiver="t", msg_type="CommandMsg", phase=1, payload={}))
    assert res_missing.payload["status"] == "error"
    assert "Missing or invalid filepath" in res_missing.payload["reason"]

    wm7 = WorkspaceManager()
    ch7 = MessageChannel()
    tester6 = Tester(ch7, wm7, MockExecutor())
    outside_file = os.path.join(tmp, "outside.txt")
    with open(outside_file, 'w') as f:
        f.write("outside")
    res_out = tester6.process_command(Message(sender="s", receiver="t", msg_type="CommandMsg", phase=1,
                                              payload={"filepath": outside_file}))
    assert res_out.payload["status"] == "error"
    assert "Access denied" in res_out.payload["reason"]

    wm8 = WorkspaceManager()
    ch8 = MessageChannel()
    tester7 = Tester(ch8, wm8, ErrorExecutor())
    res_err = tester7.process_command(Message(sender="s", receiver="t", msg_type="CommandMsg", phase=1,
                                              payload={"filepath": test_file}))
    assert res_err.payload["status"] == "error"
    assert "Executor failed" in res_err.payload["reason"]

    wm9 = WorkspaceManager()
    ch9 = MessageChannel()
    tester8 = Tester(ch9, wm9, MockExecutor())
    assert not tester8.step()

    print("PHASE 11.4 PASSED")