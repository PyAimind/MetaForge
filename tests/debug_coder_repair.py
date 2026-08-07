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
from agents.coder import Coder
from project_design.code_generator_llm import CodeGeneratorLLM

class MockProvider:
    def __init__(self):
        self.last_prompt = None
        self.calls = 0
    def generate(self, messages, model, max_tokens, temperature):
        self.calls += 1
        self.last_prompt = messages[1]["content"]
        return "def greet(name: str) -> str:\n    return f\"Hello, {name}!\"\n"

with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")
    os.makedirs(config.WORKSPACE_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    mock_provider = MockProvider()
    generator = CodeGeneratorLLM(mock_provider)
    wm = WorkspaceManager()
    channel = MessageChannel()
    coder = Coder(channel, wm, generator, context_manager=None, knowledge_base=None)

    filepath = os.path.join(config.OUTPUT_DIR, "greeter.py")
    msg = Message(
        sender="supervisor",
        receiver="coder",
        msg_type="CommandMsg",
        phase=1,
        payload={
            "action": "code",
            "filename": "greeter.py",
            "description": "",
            "dependencies": [],
            "purpose": "",
            "code": "...",
            "is_fix": True,
            "repair_context": {
                "module_name": "greeter.py",
                "filepath": filepath,
                "current_code": "def greet(name):\n    return f\"Hello, {name}!\"\n",
                "contract": {"exports": [{"name": "greet", "kind": "function", "parameters": [{"name": "name", "type": "str"}], "returns": "str"}]},
                "api_errors": ["Missing return type annotation"],
                "semantic_errors": [],
                "runtime_error": None,
                "debugger_analysis": None,
                "previous_attempts": 1
            }
        }
    )

    print("=== Incoming Coder Command ===")
    print(json.dumps(msg.payload, indent=2))

    channel.send(msg)
    coder.step()

    try:
        response = channel.receive("supervisor", timeout=1)
        print("\n=== Coder Response ===")
        print(json.dumps(response.payload, indent=2))
    except queue.Empty:
        print("No response from Coder within 1 second")

    print("\n=== Output File ===")
    if os.path.isfile(filepath):
        with open(filepath, "r") as f:
            print(f.read())
    else:
        print("File not found")

    print("\n=== Mock Provider Stats ===")
    print(f"LLM calls: {mock_provider.calls}")
    if mock_provider.last_prompt:
        print(f"Prompt (first 1000 chars):\n{mock_provider.last_prompt[:1000]}")
        print(f"Prompt contains 'CURRENT CODE': {'CURRENT CODE' in mock_provider.last_prompt}")
        print(f"Prompt contains 'ERRORS TO FIX': {'ERRORS TO FIX' in mock_provider.last_prompt}")
    else:
        print("LLM was not called")