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
        self.received_idea = idea
        return {"project_name": "Test", "description": "", "phases": [{"phase_number": 1, "name": "Core", "modules": [{"filename": "test.py", "description": "Test", "dependencies": [], "purpose": "test"}]}]}

class MockGenerator:
    def generate(self, module_info):
        self.last_module_info = module_info
        return "def fake(): pass"

class SpyKnowledgeBase(KnowledgeBase):
    def __init__(self, forced_return, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.call_count = 0
        self.forced_return = forced_return
    def get_prompt_context(self, query, role):
        self.call_count += 1
        return self.forced_return

def setup_config(tmp):
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")

def test_engineer_enriches_idea_with_kb():
    with tempfile.TemporaryDirectory() as tmp:
        setup_config(tmp)
        wm = WorkspaceManager()
        ch = MessageChannel()
        kb_path = os.path.join(tmp, "kb.json")
        kb = KnowledgeBase(kb_path)
        kb.add_lesson("Use layered architecture", "desc", ["design"])
        designer = MockDesigner()
        engineer = Engineer(ch, wm, designer, knowledge_base=kb)
        msg = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=1,
                      payload={"action": "design_structure", "idea": "Build a web app"})
        ch.send(msg)
        assert engineer.step()
        assert "### Relevant Knowledge:" in designer.received_idea
        assert "Use layered architecture" in designer.received_idea

def test_engineer_works_without_kb():
    with tempfile.TemporaryDirectory() as tmp:
        setup_config(tmp)
        wm = WorkspaceManager()
        ch = MessageChannel()
        designer = MockDesigner()
        engineer = Engineer(ch, wm, designer, knowledge_base=None)
        msg = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=1,
                      payload={"action": "design_structure", "idea": "Test"})
        ch.send(msg)
        assert engineer.step()
        assert designer.received_idea == "Test"

def test_engineer_kb_called_verification():
    with tempfile.TemporaryDirectory() as tmp:
        setup_config(tmp)
        wm = WorkspaceManager()
        ch = MessageChannel()
        kb_path = os.path.join(tmp, "kb.json")
        spy_kb = SpyKnowledgeBase("Some knowledge", kb_path)
        designer = MockDesigner()
        engineer = Engineer(ch, wm, designer, knowledge_base=spy_kb)
        msg = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=1,
                      payload={"action": "design_structure", "idea": "Any"})
        ch.send(msg)
        assert engineer.step()
        assert spy_kb.call_count == 1

def test_coder_includes_kb_and_context():
    with tempfile.TemporaryDirectory() as tmp:
        setup_config(tmp)
        wm = WorkspaceManager()
        ch = MessageChannel()
        ctx = ContextManager(config.OUTPUT_DIR)
        ctx.add_module("utils.py", "def helper(): pass")
        kb_path = os.path.join(tmp, "kb.json")
        kb = KnowledgeBase(kb_path)
        kb.add_lesson("Import Utils", "desc", ["code", "dependency"])
        gen = MockGenerator()
        coder = Coder(ch, wm, gen, ctx, knowledge_base=kb)
        msg = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=1,
                      payload={"filename": "main.py", "description": "Main entry", "dependencies": ["utils"], "purpose": "entry"})
        ch.send(msg)
        assert coder.step()
        info = gen.last_module_info
        assert "utils.py" in info["project_context"]["generated_modules"]
        assert "Import Utils" in info["knowledge_base"]

def test_coder_handles_empty_kb():
    with tempfile.TemporaryDirectory() as tmp:
        setup_config(tmp)
        wm = WorkspaceManager()
        ch = MessageChannel()
        kb_path = os.path.join(tmp, "kb.json")
        kb = KnowledgeBase(kb_path)
        gen = MockGenerator()
        coder = Coder(ch, wm, gen, None, knowledge_base=kb)
        msg = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=1,
                      payload={"filename": "empty.py", "description": "test", "dependencies": [], "purpose": "test"})
        ch.send(msg)
        assert coder.step()
        assert gen.last_module_info["knowledge_base"] == ""

def test_coder_kb_called_verification():
    with tempfile.TemporaryDirectory() as tmp:
        setup_config(tmp)
        wm = WorkspaceManager()
        ch = MessageChannel()
        kb_path = os.path.join(tmp, "kb.json")
        spy_kb = SpyKnowledgeBase("", kb_path)
        gen = MockGenerator()
        coder = Coder(ch, wm, gen, None, knowledge_base=spy_kb)
        msg = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=1,
                      payload={"filename": "spy.py", "description": "test", "dependencies": [], "purpose": "test"})
        ch.send(msg)
        assert coder.step()
        assert spy_kb.call_count == 1

def test_coder_works_without_kb():
    with tempfile.TemporaryDirectory() as tmp:
        setup_config(tmp)
        wm = WorkspaceManager()
        ch = MessageChannel()
        gen = MockGenerator()
        coder = Coder(ch, wm, gen, None, knowledge_base=None)
        msg = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=1,
                      payload={"filename": "nokb.py", "description": "test", "dependencies": [], "purpose": "test"})
        ch.send(msg)
        assert coder.step()
        assert gen.last_module_info["knowledge_base"] == ""

tests = [
    test_engineer_enriches_idea_with_kb,
    test_engineer_works_without_kb,
    test_engineer_kb_called_verification,
    test_coder_includes_kb_and_context,
    test_coder_handles_empty_kb,
    test_coder_kb_called_verification,
    test_coder_works_without_kb,
]

for test in tests:
    try:
        test()
    except AssertionError as e:
        print(f"PHASE 15.3 FAILED: {e}")
        sys.exit(1)

print("PHASE 15.3 PASSED")