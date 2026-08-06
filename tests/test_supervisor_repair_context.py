import os
import sys
import json
import tempfile
import queue
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from workspace.workspace_manager import WorkspaceManager
from communication.message import Message
from communication.message_channel import MessageChannel
from agents.supervisor import Supervisor

original_work = config.WORKSPACE_DIR
original_output = config.OUTPUT_DIR

class MockAPIInspector:
    def inspect(self, filepath, exports):
        return {"valid": False, "errors": ["Missing return type annotation"]}

class MockSemanticAnalyzer:
    def analyze(self, filepath, dep_contracts):
        return {"valid": False, "errors": ["Method 'save' not found"]}

class MockDebugger:
    def analyze_error(self, filepath, stderr, stdout, return_code):
        return {
            "diagnosis": "null pointer",
            "root_cause": "uninitialized variable",
            "suggested_fix": "initialize before use",
            "confidence": 0.9
        }

with tempfile.TemporaryDirectory() as tmp:
    try:
        config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
        config.OUTPUT_DIR = os.path.join(tmp, "output")
        os.makedirs(config.WORKSPACE_DIR, exist_ok=True)
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)

        bad_code = "def greet(name):\n    return f\"Hello, {name}!\"\n"
        bad_file = os.path.join(config.OUTPUT_DIR, "bad_module.py")
        with open(bad_file, "w", encoding="utf-8") as f:
            f.write(bad_code)

        contracts = {
            "bad_module.py": {
                "module": "bad_module.py",
                "exports": [
                    {
                        "name": "greet",
                        "kind": "function",
                        "parameters": [{"name": "name", "type": "str"}],
                        "returns": "str",
                        "constructor": None,
                        "methods": []
                    }
                ],
                "required_imports": [],
                "generated": True,
                "validated": False
            }
        }
        with open(os.path.join(config.WORKSPACE_DIR, "contracts.json"), "w") as f:
            json.dump(contracts, f)

        wm = WorkspaceManager()
        channel = MessageChannel()
        supervisor = Supervisor(channel, wm, api_inspector=MockAPIInspector(), semantic_analyzer=None, debugger=None)
        supervisor.status = "waiting_for_coder"
        supervisor.modules = [{"filename": "bad_module.py"}]
        supervisor.current_module_index = 0

        msg = Message(sender="coder", receiver="supervisor", msg_type="ResultMsg", phase=1,
                      payload={"status": "success", "filepath": bad_file})
        channel.send(msg)
        supervisor.step()

        eng_msg = channel.receive("engineer", timeout=0.1)
        assert eng_msg is not None
        payload = eng_msg.payload
        assert "repair_context" in payload
        ctx = payload["repair_context"]
        assert ctx["module_name"] == "bad_module.py"
        assert "Missing return type annotation" in ctx["api_errors"]
        assert "current_code" in ctx and "def greet(name)" in ctx["current_code"]
        assert "contract" in ctx and ctx["contract"]["exports"][0]["name"] == "greet"
    finally:
        config.WORKSPACE_DIR = original_work
        config.OUTPUT_DIR = original_output

with tempfile.TemporaryDirectory() as tmp:
    try:
        config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
        config.OUTPUT_DIR = os.path.join(tmp, "output")
        os.makedirs(config.WORKSPACE_DIR, exist_ok=True)
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)

        bad_code = "def greet(name):\n    return f\"Hello, {name}!\"\n"
        bad_file = os.path.join(config.OUTPUT_DIR, "bad_module.py")
        with open(bad_file, "w", encoding="utf-8") as f:
            f.write(bad_code)

        contracts = {
            "bad_module.py": {
                "module": "bad_module.py",
                "exports": [
                    {"name": "greet", "kind": "function", "parameters": [{"name": "name", "type": "str"}], "returns": "str", "constructor": None, "methods": []}
                ],
                "required_imports": [],
                "generated": True,
                "validated": False
            },
            "storage.py": {
                "module": "storage.py",
                "exports": [{"name": "save", "kind": "function", "parameters": [], "returns": "None", "constructor": None, "methods": []}],
                "required_imports": [],
                "generated": True,
                "validated": True
            }
        }
        with open(os.path.join(config.WORKSPACE_DIR, "contracts.json"), "w") as f:
            json.dump(contracts, f)

        wm = WorkspaceManager()
        channel = MessageChannel()
        supervisor = Supervisor(channel, wm, api_inspector=None, semantic_analyzer=MockSemanticAnalyzer(), debugger=None)
        supervisor.status = "waiting_for_coder"
        supervisor.modules = [{"filename": "bad_module.py", "dependencies": ["storage.py"]}]
        supervisor.current_module_index = 0

        msg = Message(sender="coder", receiver="supervisor", msg_type="ResultMsg", phase=1,
                      payload={"status": "success", "filepath": bad_file})
        channel.send(msg)
        supervisor.step()

        eng_msg = channel.receive("engineer", timeout=0.1)
        assert eng_msg is not None
        payload = eng_msg.payload
        assert "repair_context" in payload
        ctx = payload["repair_context"]
        assert ctx["module_name"] == "bad_module.py"
        assert any("Method 'save' not found" in e for e in ctx["semantic_errors"])
    finally:
        config.WORKSPACE_DIR = original_work
        config.OUTPUT_DIR = original_output

with tempfile.TemporaryDirectory() as tmp:
    try:
        config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
        config.OUTPUT_DIR = os.path.join(tmp, "output")
        os.makedirs(config.WORKSPACE_DIR, exist_ok=True)
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)

        bad_code = "def greet(name):\n    return f\"Hello, {name}!\"\n"
        bad_file = os.path.join(config.OUTPUT_DIR, "bad_module.py")
        with open(bad_file, "w", encoding="utf-8") as f:
            f.write(bad_code)

        contracts = {
            "bad_module.py": {
                "module": "bad_module.py",
                "exports": [{"name": "greet", "kind": "function", "parameters": [{"name": "name", "type": "str"}], "returns": "str", "constructor": None, "methods": []}],
                "required_imports": [],
                "generated": True,
                "validated": False
            }
        }
        with open(os.path.join(config.WORKSPACE_DIR, "contracts.json"), "w") as f:
            json.dump(contracts, f)

        wm = WorkspaceManager()
        channel = MessageChannel()
        supervisor = Supervisor(channel, wm, api_inspector=None, semantic_analyzer=None, debugger=MockDebugger())
        supervisor.status = "waiting_for_tester"
        supervisor.modules = [{"filename": "bad_module.py"}]
        supervisor.current_module_index = 0

        msg = Message(sender="tester", receiver="supervisor", msg_type="ResultMsg", phase=1,
                      payload={"status": "failed", "filepath": bad_file, "stderr": "AttributeError: ...", "stdout": "", "return_code": 1})
        channel.send(msg)
        supervisor.step()

        eng_msg = channel.receive("engineer", timeout=0.1)
        assert eng_msg is not None
        payload = eng_msg.payload
        assert "repair_context" in payload
        ctx = payload["repair_context"]
        assert ctx["module_name"] == "bad_module.py"
        assert "runtime_error" in ctx and "AttributeError" in ctx["runtime_error"]
        assert "debugger_analysis" in ctx
        assert ctx["debugger_analysis"]["root_cause"] == "uninitialized variable"
    finally:
        config.WORKSPACE_DIR = original_work
        config.OUTPUT_DIR = original_output

print("PHASE 2 SUPERVISOR REPAIR CONTEXT PASSED")