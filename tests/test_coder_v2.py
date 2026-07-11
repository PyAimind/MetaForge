import sys
import os
import tempfile
import queue
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from workspace.workspace_manager import WorkspaceManager
from communication.message import Message
from communication.message_channel import MessageChannel
from agents.coder import Coder
from project_design.code_generator_llm import FALLBACK_CODE

class MockGenerator:
    def __init__(self):
        self.call_count = 0
        self.last_module_info = None
    def generate(self, module_info):
        self.call_count += 1
        self.last_module_info = module_info
        return "# Generated code\nx = 1"

class FailingGenerator:
    def generate(self, module_info):
        raise RuntimeError("boom")

with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")

    try:
        try:
            Coder(None, None, None)
            assert False
        except TypeError:
            pass

        ch = MessageChannel()
        try:
            Coder(ch, None, MockGenerator())
            assert False
        except TypeError:
            pass

        wm = WorkspaceManager()
        try:
            Coder(ch, wm, "not_a_generator")
            assert False
        except TypeError:
            pass

        Coder(ch, wm, MockGenerator())

        wm2 = WorkspaceManager()
        ch2 = MessageChannel()
        gen1 = MockGenerator()
        coder1 = Coder(ch2, wm2, gen1)
        msg = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=1,
                      payload={"filename": "test.py", "description": "A test", "dependencies": [], "purpose": "testing"})
        ch2.send(msg)
        assert coder1.step()
        resp = ch2.receive("supervisor", timeout=0.5)
        assert resp.payload["status"] == "success"
        filepath = resp.payload["filepath"]
        assert os.path.exists(filepath)
        with open(filepath, encoding='utf-8') as f:
            content = f.read()
        compile(content, filepath, 'exec')
        assert gen1.call_count == 1
        assert gen1.last_module_info["filename"] == "test.py"

        wm3 = WorkspaceManager()
        ch3 = MessageChannel()
        gen2 = MockGenerator()
        coder2 = Coder(ch3, wm3, gen2)
        msg2 = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=1,
                       payload={"filename": "direct.py", "code": "print('hello')"})
        ch3.send(msg2)
        prev_count = gen2.call_count
        assert coder2.step()
        resp2 = ch3.receive("supervisor", timeout=0.5)
        assert resp2.payload["status"] == "success"
        with open(resp2.payload["filepath"], encoding='utf-8') as f:
            assert f.read() == "print('hello')"
        assert gen2.call_count == prev_count

        wm4 = WorkspaceManager()
        ch4 = MessageChannel()
        gen3 = MockGenerator()
        coder3 = Coder(ch4, wm4, gen3)
        msg3 = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=1,
                       payload={"filename": "bad.py", "code": "def : invalid"})
        ch4.send(msg3)
        assert coder3.step()
        resp3 = ch4.receive("supervisor", timeout=0.5)
        assert resp3.payload["status"] == "success"
        with open(resp3.payload["filepath"], encoding='utf-8') as f:
            content3 = f.read()
        assert content3 == "# Generated code\nx = 1"
        assert gen3.call_count == 1

        wm5 = WorkspaceManager()
        ch5 = MessageChannel()
        coder4 = Coder(ch5, wm5, FailingGenerator())
        msg4 = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=1,
                       payload={"filename": "fallback.py", "description": "test", "dependencies": [], "purpose": "test"})
        ch5.send(msg4)
        assert coder4.step()
        resp4 = ch5.receive("supervisor", timeout=0.5)
        assert resp4.payload["status"] == "success"
        with open(resp4.payload["filepath"], encoding='utf-8') as f:
            assert f.read() == FALLBACK_CODE

        wm6 = WorkspaceManager()
        ch6 = MessageChannel()
        coder5 = Coder(ch6, wm6, MockGenerator())
        msg_err = Message(sender="supervisor", receiver="coder", msg_type="ResultMsg", phase=1, payload={})
        result_err = coder5.process_command(msg_err)
        assert result_err.payload["status"] == "error"
        assert "Invalid message type" in result_err.payload["reason"]

        wm7 = WorkspaceManager()
        ch7 = MessageChannel()
        coder6 = Coder(ch7, wm7, MockGenerator())
        assert not coder6.step()

        print("PHASE 10.4 PASSED")
    except AssertionError as e:
        print(f"PHASE 10.4 FAILED: {e}")
    except Exception as e:
        print(f"PHASE 10.4 FAILED: {e}")