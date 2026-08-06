import os
import sys
import json
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from workspace.workspace_manager import WorkspaceManager
from communication.message import Message
from communication.message_channel import MessageChannel
from agents.engineer import Engineer

class MockDesigner:
    def design(self, idea):
        return {}

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

    structure = {
        "project_name": "GreetingApp",
        "description": "A simple greeting app",
        "phases": [
            {
                "phase_number": 1,
                "name": "Core",
                "modules": [
                    {
                        "filename": "greeter.py",
                        "description": "Greeting module",
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
    wm.write_structure(structure)

    module_exports = structure["phases"][0]["modules"][0]["exports"]

    repair_context = {
        "module_name": "greeter.py",
        "filepath": "output/greeter.py",
        "current_code": "def greet(name):\n    return f\"Hello, {name}!\"\n",
        "contract": {"exports": module_exports},
        "api_errors": ["Missing return type annotation"],
        "semantic_errors": [],
        "runtime_error": "AttributeError: 'NoneType' object has no attribute 'save'",
        "debugger_analysis": {
            "diagnosis": "null pointer",
            "root_cause": "uninitialized variable",
            "suggested_fix": "initialize before use",
            "confidence": 0.9
        },
        "previous_attempts": 2
    }

    payload = {
        "action": "generate_single_prompt",
        "module_info": {
            "filename": "greeter.py",
            "description": "Greeting module",
            "dependencies": [],
            "purpose": "greeting",
            "exports": module_exports,
            "required_imports": []
        },
        "is_fix": True,
        "repair_context": repair_context
    }

    response = engineer._handle_generate_single_prompt(payload, phase=1)
    prompt = response.payload["prompts"]["fixed_module.py"]

    assert "REPAIR TARGET: greeter.py (attempt 3)" in prompt
    assert "CURRENT CODE (must be modified minimally):" in prompt
    assert "def greet(name):" in prompt
    assert "CONTRACT:" in prompt
    assert "API ERRORS:" in prompt
    assert "Missing return type annotation" in prompt
    assert "RUNTIME ERROR:" in prompt
    assert "AttributeError" in prompt
    assert "DEBUGGER ANALYSIS:" in prompt
    assert "null pointer" in prompt
    assert "Do NOT rewrite the whole module." in prompt
    assert "Keep all correct code unchanged." in prompt

    print("PHASE 3 ENGINEER REPAIR PROMPT PASSED")