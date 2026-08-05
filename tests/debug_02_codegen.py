import os
import sys
import json
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from workspace.workspace_manager import WorkspaceManager
from communication.message_channel import MessageChannel
from agents.engineer import Engineer
from project_design.code_generator_llm import CodeGeneratorLLM

class MockDesigner:
    def design(self, idea):
        return {
            "project_name": "GreetingApp",
            "description": "A simple greeting app",
            "phases": [
                {
                    "phase_number": 1,
                    "name": "Core",
                    "modules": [
                        {
                            "filename": "greeter.py",
                            "description": "Generates greeting messages",
                            "dependencies": [],
                            "purpose": "greeting",
                            "exports": [
                                {
                                    "name": "greet",
                                    "kind": "function",
                                    "parameters": [{"name": "name", "type": "str"}],
                                    "returns": "str"
                                }
                            ],
                            "required_imports": []
                        }
                    ]
                }
            ]
        }

class SpyProvider:
    def __init__(self):
        self.last_messages = None
        self.last_model = None
        self.last_temperature = None

    def generate(self, messages, model, temperature):
        self.last_messages = messages
        self.last_model = model
        self.last_temperature = temperature
        return "def greet(name):\n    return f'Hello, {name}!'\n"

with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")
    os.makedirs(config.WORKSPACE_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    wm = WorkspaceManager()
    channel = MessageChannel()
    mock_designer = MockDesigner()
    engineer = Engineer(channel, wm, mock_designer, knowledge_base=None)
    resp = engineer._handle_design_structure({"idea": "A simple greeting app"}, phase=1)
    structure = resp.payload["structure"]
    wm.write_structure(structure)

    module_exports = structure["phases"][0]["modules"][0]["exports"]
    module_info = {
        "filename": "greeter.py",
        "description": "Generates greeting messages",
        "dependencies": [],
        "purpose": "greeting",
        "exports": module_exports,
        "required_imports": [],
        "debugger_diagnosis": {},
        "project_context": {}
    }

    spy = SpyProvider()
    cg = CodeGeneratorLLM(spy)
    cg.generate(module_info)

    os.makedirs("debug_output", exist_ok=True)
    system_prompt = spy.last_messages[0]["content"]
    user_message = spy.last_messages[1]["content"]
    with open("debug_output/codegen_system_prompt.txt", "w", encoding="utf-8") as f:
        f.write(system_prompt)
    with open("debug_output/codegen_user_message.txt", "w", encoding="utf-8") as f:
        f.write(user_message)
    with open("debug_output/codegen_module_info.json", "w", encoding="utf-8") as f:
        json.dump(module_info, f, indent=2)

    contains_greet = "greet" in user_message
    contains_name = "name" in user_message
    contains_str = "str" in user_message
    contains_returns = "returns" in user_message
    has_contract = "Exports" in user_message or "Contract for" in user_message
    has_forbidden = "FORBIDDEN PATTERNS" in user_message

    print("User message analysis:")
    print(f"  Contains 'greet': {'YES' if contains_greet else 'NO'}")
    print(f"  Contains 'name': {'YES' if contains_name else 'NO'}")
    print(f"  Contains 'str': {'YES' if contains_str else 'NO'}")
    print(f"  Contains 'returns': {'YES' if contains_returns else 'NO'}")
    print(f"  Has contract section: {'YES' if has_contract else 'NO'}")
    print(f"  Has FORBIDDEN PATTERNS: {'YES' if has_forbidden else 'NO'}")
    print(f"  System prompt length: {len(system_prompt)}")
    print(f"  User message length: {len(user_message)}")