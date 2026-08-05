import os
import sys
import json
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from workspace.workspace_manager import WorkspaceManager
from communication.message_channel import MessageChannel
from agents.engineer import Engineer

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

    resp_structure = engineer._handle_design_structure({"idea": "A simple greeting app"}, phase=1)
    structure = resp_structure.payload["structure"]
    wm.write_structure(structure)

    resp_prompts = engineer._handle_generate_prompts({}, phase=1)
    prompts = resp_prompts.payload["prompts"]
    prompt_greeter = prompts.get("greeter.py", "")

    os.makedirs("debug_output", exist_ok=True)
    with open("debug_output/structure.json", "w", encoding="utf-8") as f:
        json.dump(structure, f, indent=2)
    with open("debug_output/engineer_response.json", "w", encoding="utf-8") as f:
        json.dump(resp_prompts.payload, f, indent=2)
    with open("debug_output/prompt_greeter.txt", "w", encoding="utf-8") as f:
        f.write(prompt_greeter)

    contract_section_found = "### Exports" in prompt_greeter or "Contract for" in prompt_greeter
    expected_signature = "greet(name: str) -> str"
    actual_contains_signature = expected_signature in prompt_greeter

    print("✓ Structure generated")
    print("✓ Prompt generated")
    print(f"Prompt length: {len(prompt_greeter)}")
    print(f"Contract section found: {'YES' if contract_section_found else 'NO'}")
    print(f"Expected export signature: {expected_signature}")
    print(f"Actual prompt contains signature: {'YES' if actual_contains_signature else 'NO'}")