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
from agents.engineer import Engineer
from agents.coder import Coder
from project_design.code_generator_llm import CodeGeneratorLLM

class MockAPIInspector:
    def __init__(self):
        self.last_filepath = None
        self.last_exports = None
    def inspect(self, filepath, exports):
        self.last_filepath = filepath
        self.last_exports = exports
        return {"valid": False, "errors": ["Missing return type annotation"]}

class MockLLMProvider:
    def __init__(self):
        self.calls = []
    def generate(self, messages, model, max_tokens, temperature):
        self.calls.append(messages)
        user_msg = messages[1]["content"]
        assert "REPAIR TASK" in user_msg
        assert "CURRENT CODE" in user_msg
        return "def greet(name: str) -> str:\n    return f\"Hello, {name}!\"\n"

class DummyDesigner:
    def design(self, idea):
        return {}

with tempfile.TemporaryDirectory() as tmp:
    old_config = {
        "WORKSPACE_DIR": config.WORKSPACE_DIR,
        "OUTPUT_DIR": config.OUTPUT_DIR,
        "PHASE_FILE": config.PHASE_FILE,
        "LOG_FILE": config.LOG_FILE,
        "STRUCTURE_FILE": config.STRUCTURE_FILE,
        "TEST_RESULTS_FILE": config.TEST_RESULTS_FILE,
    }
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")
    os.makedirs(config.WORKSPACE_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    broken_code = "def greet(name):\n    return f\"Hello, {name}!\"\n"
    broken_file = os.path.join(config.OUTPUT_DIR, "greeter.py")
    with open(broken_file, "w", encoding="utf-8") as f:
        f.write(broken_code)

    contracts = {
        "greeter.py": {
            "module": "greeter.py",
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
    mock_inspector = MockAPIInspector()
    mock_provider = MockLLMProvider()
    generator = CodeGeneratorLLM(mock_provider)
    supervisor = Supervisor(channel, wm, api_inspector=mock_inspector, semantic_analyzer=None, debugger=None)
    engineer = Engineer(channel, wm, DummyDesigner(), knowledge_base=None)
    coder = Coder(channel, wm, generator, context_manager=None, knowledge_base=None)

    supervisor.status = "waiting_for_coder"
    supervisor.modules = [{"filename": "greeter.py"}]
    supervisor.current_module_index = 0

    msg = Message(sender="coder", receiver="supervisor", msg_type="ResultMsg", phase=1,
                  payload={"status": "success", "filepath": broken_file})
    channel.send(msg)

    # Step 1 – Supervisor detects API failure and sends repair command to Engineer
    supervisor.step()

    # Capture the repair command sent to Engineer
    engineer_cmd = channel.receive("engineer", timeout=0.1)
    assert engineer_cmd is not None, "Supervisor did not send repair command to Engineer"
    assert "repair_context" in engineer_cmd.payload
    repair_ctx = engineer_cmd.payload["repair_context"]
    assert "Missing return type annotation" in repair_ctx.get("api_errors", [])
    # Re‑send the message so Engineer can process it
    channel.send(engineer_cmd)

    print("\nRepairContext sent to Engineer:")
    print(json.dumps(repair_ctx, indent=2))

    # Step 2 – Engineer receives the repair command, builds the repair prompt,
    #          and sends the result back to Supervisor.
    engineer.step()

    # DEBUG: Capture the Engineer's response
    engineer_response = channel.receive("supervisor", timeout=0.1)
    if engineer_response:
        print("ENGINEER RESPONSE:")
        print(json.dumps(engineer_response.payload, indent=2))
        # Re-send it so Supervisor can process it
        channel.send(engineer_response)

    # Step 3 – Supervisor receives Engineer's response and dispatches the
    #          repair command to Coder.
    supervisor.step()

    # Verify that Supervisor actually forwarded the repair command to Coder
    coder_cmd = channel.receive("coder", timeout=0.1)
    assert coder_cmd is not None, "Supervisor did not send repair command to Coder"
    assert coder_cmd.payload.get("is_fix") is True, "Message sent to Coder is not a repair command"
    assert "repair_context" in coder_cmd.payload, "Repair context missing in Coder command"

    # Re-send the message so Coder can process it normally
    channel.send(coder_cmd)

    # Step 4 – Coder enters repair mode.
    #          This will call the mock LLM provider and write the fixed code.
    coder.step()

    with open(broken_file, "r", encoding="utf-8") as f:
        fixed_code = f.read()
    assert len(mock_provider.calls) == 1, f"Expected 1 LLM call, got {len(mock_provider.calls)}"
    assert "def greet(name: str) -> str:" in fixed_code

    print("=== REPAIR LOOP TRACE ===")
    print("Broken code:\n" + broken_code)
    print("\nRepair prompt sent to LLM:")
    print(mock_provider.calls[0][1]["content"])
    print("\nFixed code:\n" + fixed_code)
    print("=== END TRACE ===")

    for key, value in old_config.items():
        setattr(config, key, value)

    print("PHASE 4 E2E REPAIR LOOP PASSED")