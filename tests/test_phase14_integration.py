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

class SpyGenerator:
    def __init__(self):
        self.last_module_info = None
    def generate(self, module_info):
        self.last_module_info = module_info
        if "project_context" in module_info and "utils.py" in module_info["project_context"]["generated_modules"]:
            return "from utils import calculate_sum\n\ndef main():\n    return calculate_sum(2, 3)\n"
        return "def calculate_sum(a, b):\n    return a + b\n\ndef main():\n    return calculate_sum(2, 3)\n"

with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")

    wm = WorkspaceManager()
    channel = MessageChannel()
    ctx = ContextManager(config.OUTPUT_DIR)
    ctx.add_module("utils.py", "def calculate_sum(a, b):\n    return a + b\n")
    spy = SpyGenerator()
    coder = Coder(channel, wm, spy, ctx)

    msg = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=1,
                  payload={"filename": "main.py", "description": "Main entry", "dependencies": ["utils.py"], "purpose": "main"})
    channel.send(msg)
    assert coder.step()
    resp = channel.receive("supervisor", timeout=0.5)
    assert resp.payload["status"] == "success"
    filepath = resp.payload["filepath"]

    assert spy.last_module_info is not None
    assert "project_context" in spy.last_module_info
    gen_modules = spy.last_module_info["project_context"]["generated_modules"]
    assert "utils.py" in gen_modules
    assert "main.py" not in gen_modules

    with open(filepath, encoding='utf-8') as f:
        content = f.read()
    assert "from utils import calculate_sum" in content
    assert "def calculate_sum" not in content

    assert "main.py" in ctx.modules
    assert "utils" in ctx.modules["main.py"]["imports"]

    print("PHASE 14.4 PASSED")