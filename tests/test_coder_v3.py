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
from project_design.context_manager import ContextManager
from project_design.code_generator_llm import FALLBACK_CODE

class TestProjectContext(ContextManager):
    def get_context(self):
        return {"generated_modules": self.modules, "module_count": len(self.modules)}
    def get_context_for_module(self, filename):
        other_modules = {k: v for k, v in self.modules.items() if k != filename}
        return {"current_module": filename, "generated_modules": other_modules}

class SpyGenerator:
    def __init__(self, code="def hello():\n    return 'world'"):
        self.code = code
        self.last_module_info = None
    def generate(self, module_info):
        self.last_module_info = module_info
        return self.code

with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")

    wm = WorkspaceManager()
    ch = MessageChannel()
    gen = SpyGenerator()
    ctx = TestProjectContext(config.OUTPUT_DIR)

    Coder(ch, wm, gen, ctx)

    Coder(ch, wm, gen, None)

    try:
        Coder(ch, wm, gen, "invalid")
        assert False
    except TypeError:
        pass

    ch2 = MessageChannel()
    wm2 = WorkspaceManager()
    ctx2 = TestProjectContext(config.OUTPUT_DIR)
    coder2 = Coder(ch2, wm2, SpyGenerator(), ctx2)
    msg = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=1,
                  payload={"filename": "test.py", "description": "A test", "dependencies": [], "purpose": "testing"})
    ch2.send(msg)
    assert coder2.step()
    resp = ch2.receive("supervisor", timeout=0.5)
    assert resp.payload["status"] == "success"
    assert "test.py" in ctx2.get_context()["generated_modules"]

    ch3 = MessageChannel()
    wm3 = WorkspaceManager()
    coder3 = Coder(ch3, wm3, gen, None)
    msg3 = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=1,
                   payload={"filename": "test_none.py", "description": "A test", "dependencies": [], "purpose": "testing"})
    ch3.send(msg3)
    assert coder3.step()
    resp3 = ch3.receive("supervisor", timeout=0.5)
    assert resp3.payload["status"] == "success"

    ch4 = MessageChannel()
    wm4 = WorkspaceManager()
    ctx4 = TestProjectContext(config.OUTPUT_DIR)
    ctx4.add_module("utils.py", "def helper():\n    pass")
    spy4 = SpyGenerator()
    coder4 = Coder(ch4, wm4, spy4, ctx4)
    msg4 = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=1,
                   payload={"filename": "main.py", "description": "Main", "dependencies": ["utils"], "purpose": "entry"})
    ch4.send(msg4)
    assert coder4.step()
    ch4.receive("supervisor", timeout=0.5)
    assert spy4.last_module_info is not None
    assert "project_context" in spy4.last_module_info
    assert "utils.py" in spy4.last_module_info["project_context"]["generated_modules"]

    print("PHASE 14.3 PASSED")