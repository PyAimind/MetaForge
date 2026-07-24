import sys
import os
import tempfile
import queue
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from workspace.workspace_manager import WorkspaceManager
from communication.message import Message
from communication.message_channel import MessageChannel
from agents.engineer import Engineer
from agents.coder import Coder
from memory.knowledge_base import KnowledgeBase
from project_design.context_manager import ContextManager

class MockDesigner:
    def design(self, idea):
        return {
            "project_name": "Test",
            "description": "",
            "phases": [{"phase_number": 1, "name": "Core", "modules": [
                {"filename": "main.py", "description": "Main", "dependencies": [], "purpose": "main"}
            ]}]
        }

class LearningMockGenerator:
    def generate(self, module_info):
        self.last_module_info = module_info
        if "avoid_global_vars" in module_info.get("knowledge_base", ""):
            self.last_code = "def main():\n    result = 42\n    return result"
        else:
            self.last_code = "x = 42\n\ndef main():\n    return x"
        return self.last_code

with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")

    wm = WorkspaceManager()
    channel = MessageChannel()
    kb_path = os.path.join(tmp, "kb.json")
    kb = KnowledgeBase(kb_path)
    ctx = ContextManager(config.OUTPUT_DIR)

    designer1 = MockDesigner()
    gen1 = LearningMockGenerator()
    engineer1 = Engineer(channel, wm, designer1, knowledge_base=kb)
    coder1 = Coder(channel, wm, gen1, ctx, knowledge_base=kb)

    cmd_eng = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=1,
                      payload={"action": "design_structure", "idea": "Test Project"})
    channel.send(cmd_eng)
    assert engineer1.step()
    eng_resp = channel.receive("supervisor", timeout=1)
    mod = eng_resp.payload["structure"]["phases"][0]["modules"][0]

    cmd_coder = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=1,
                        payload={"filename": mod["filename"], "description": mod["description"],
                                 "dependencies": mod["dependencies"], "purpose": mod["purpose"]})
    channel.send(cmd_coder)
    assert coder1.step()
    resp1 = channel.receive("supervisor", timeout=1)
    assert resp1.payload["status"] == "success"
    assert "x = 42" in gen1.last_code
    assert "def main()" in gen1.last_code

    kb.add_lesson("Avoid global variables in main module",
                  "avoid_global_vars: Use local variables inside functions instead of global ones",
                  ["code", "global"])

    designer2 = MockDesigner()
    gen2 = LearningMockGenerator()
    engineer2 = Engineer(channel, wm, designer2, knowledge_base=kb)
    coder2 = Coder(channel, wm, gen2, ctx, knowledge_base=kb)

    cmd_eng2 = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=2,
                       payload={"action": "design_structure", "idea": "Another Test Project"})
    channel.send(cmd_eng2)
    assert engineer2.step()
    eng_resp2 = channel.receive("supervisor", timeout=1)
    mod2 = eng_resp2.payload["structure"]["phases"][0]["modules"][0]

    cmd_coder2 = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=2,
                         payload={"filename": mod2["filename"], "description": mod2["description"],
                                  "dependencies": mod2["dependencies"], "purpose": mod2["purpose"]})
    channel.send(cmd_coder2)
    assert coder2.step()
    resp2 = channel.receive("supervisor", timeout=1)
    assert resp2.payload["status"] == "success"
    assert "avoid_global_vars" in gen2.last_module_info["knowledge_base"]
    assert "x = 42" not in gen2.last_code
    assert "result = 42" in gen2.last_code
    assert "def main()" in gen2.last_code

    print("PHASE 15 CUMULATIVE PASSED")