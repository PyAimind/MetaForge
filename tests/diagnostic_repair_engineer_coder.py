# === CONSOLE OUTPUT (expected) ===
# [1] Engineer command created with action=generate_single_prompt
# [2] Engineer generated repair prompt (length=...)
# [3] Engineer response status=success
# [4] Supervisor forwarding logic executed
# [5] Coder command constructed
# [6] Prompt equality check: payload["code"] equals Engineer prompt? True
# [7] RepairContext preservation: is_fix=True, repair_context present, all_modules=['storage.py', 'todo_manager.py', 'cli.py']
# [8] Coder received repair command (Mock LLM called 1 time)
# PASS: ENGINEER_CODER_REPAIR_FORWARDING_VERIFIED

import os
import sys
import json
import tempfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from communication.message import Message
from communication.message_channel import MessageChannel
from workspace.workspace_manager import WorkspaceManager
from agents.supervisor import Supervisor
from agents.engineer import Engineer
from agents.coder import Coder
from project_design.code_generator_llm import CodeGeneratorLLM
import config

# ----------------------------------------------------------------------
# Mock LLM Provider – returns dummy valid JSON so Coder doesn't crash
# ----------------------------------------------------------------------
class MockLLMProvider:
    def __init__(self):
        self.call_count = 0

    def generate(self, messages, model, max_tokens, temperature):
        self.call_count += 1
        return '{"cli.py": "dummy cli code", "todo_manager.py": "dummy todo code"}'

# ----------------------------------------------------------------------
# Dummy designer for Engineer constructor
# ----------------------------------------------------------------------
class DummyDesigner:
    def design(self, idea):
        return {}

# ----------------------------------------------------------------------
# Module sources (minimal)
# ----------------------------------------------------------------------
CLI_CODE = "def main(): pass"
TODO_CODE = "def run(): pass"
STORAGE_CODE = "def store(): pass"

# ----------------------------------------------------------------------
# Main diagnostic
# ----------------------------------------------------------------------
tmpdir = tempfile.mkdtemp()
try:
    ws = os.path.join(tmpdir, 'workspace')
    out = os.path.join(tmpdir, 'output')
    config.WORKSPACE_DIR = ws
    config.OUTPUT_DIR = out
    config.PHASE_FILE = os.path.join(ws, 'current_phase.json')
    config.LOG_FILE = os.path.join(ws, 'build_log.json')
    config.STRUCTURE_FILE = os.path.join(ws, 'project_structure.json')
    config.TEST_RESULTS_FILE = os.path.join(ws, 'test_results.json')
    os.makedirs(ws, exist_ok=True)
    os.makedirs(out, exist_ok=True)

    # Write minimal module files
    with open(os.path.join(out, 'cli.py'), 'w') as f: f.write(CLI_CODE)
    with open(os.path.join(out, 'todo_manager.py'), 'w') as f: f.write(TODO_CODE)
    with open(os.path.join(out, 'storage.py'), 'w') as f: f.write(STORAGE_CODE)

    # Contracts
    contracts = {
        "storage.py": {"module": "storage.py", "exports": [], "dependencies": [], "generated": True, "validated": True},
        "todo_manager.py": {"module": "todo_manager.py", "exports": [], "dependencies": ["storage.py"], "generated": True, "validated": True},
        "cli.py": {"module": "cli.py", "exports": [], "dependencies": ["todo_manager.py"], "generated": True, "validated": False},
    }
    with open(os.path.join(ws, 'contracts.json'), 'w') as f: json.dump(contracts, f, indent=2)

    channel = MessageChannel()
    workspace = WorkspaceManager()

    # Instantiate agents
    mock_provider = MockLLMProvider()
    generator = CodeGeneratorLLM(mock_provider)
    supervisor = Supervisor(channel, workspace, debugger=None, api_inspector=None, semantic_analyzer=None)
    engineer = Engineer(channel, workspace, DummyDesigner(), knowledge_base=None)
    coder = Coder(channel, workspace, generator, context_manager=None, knowledge_base=None)

    # --- Step 1: Build Engineer repair command (as Supervisor would) ---
    repair_context = {
        "module_name": "cli.py",
        "filepath": os.path.join(out, "cli.py"),
        "all_modules": [
            {"module_name": "storage.py", "source_code": STORAGE_CODE, "contract": {}},
            {"module_name": "todo_manager.py", "source_code": TODO_CODE, "contract": {}},
            {"module_name": "cli.py", "source_code": CLI_CODE, "contract": {}},
        ],
        "current_code": CLI_CODE,
        "contract": {"exports": []},
        "api_errors": ["missing return annotation"],
        "semantic_errors": [],
        "runtime_error": "list did not contain 'Test todo'",
        "debugger_analysis": None,
        "previous_attempts": 1,
    }

    eng_cmd = Message(
        sender="supervisor",
        receiver="engineer",
        msg_type="CommandMsg",
        phase=1,
        payload={
            "action": "generate_single_prompt",
            "module_info": {
                "filename": "cli.py",
                "description": "CLI module",
                "dependencies": ["todo_manager.py"],
                "purpose": "entry",
                "exports": [],
                "required_imports": [],
            },
            "is_fix": True,
            "repair_context": repair_context,
        }
    )
    print("[1] Engineer command created with action=generate_single_prompt")

    # --- Step 2: Run Engineer ---
    eng_resp = engineer.process_command(eng_cmd)
    print(f"[2] Engineer generated repair prompt (length={len(eng_resp.payload.get('prompts', {}).get('cli.py', ''))})")
    print(f"[3] Engineer response status={eng_resp.payload.get('status')}")

    if eng_resp.payload.get("status") != "success":
        print("FAIL: Engineer did not return success")
        sys.exit(1)

    engineer_prompt = eng_resp.payload.get("prompts", {}).get("cli.py", "")
    if not engineer_prompt:
        print("FAIL: Engineer prompt for cli.py is empty")
        sys.exit(1)

    # --- Step 3: Forward through Supervisor (reproduce real logic) ---
    supervisor.status = "waiting_for_engineer"
    supervisor.modules = [
        {"filename": "storage.py", "dependencies": []},
        {"filename": "todo_manager.py", "dependencies": ["storage.py"]},
        {"filename": "cli.py", "dependencies": ["todo_manager.py"]}
    ]
    supervisor.current_module_index = 2   # cli.py
    supervisor.fix_attempts = {}

    # Inject Engineer response into supervisor queue
    channel.send(eng_resp)
    supervisor.step()
    print("[4] Supervisor forwarding logic executed")

    # Retrieve Coder command
    coder_cmd = channel.receive("coder", timeout=0.1)
    if not coder_cmd:
        print("FAIL: Supervisor did not send command to Coder")
        sys.exit(1)

    print("[5] Coder command constructed")
    coder_payload = coder_cmd.payload

    # --- Step 4: Verify fields ---
    prompt_match = coder_payload.get("code") == engineer_prompt
    print(f"[6] Prompt equality check: payload['code'] equals Engineer prompt? {prompt_match}")

    is_fix_ok = coder_payload.get("is_fix") == True
    ctx_ok = coder_payload.get("repair_context") is not None
    all_mods = coder_payload.get("repair_context", {}).get("all_modules", [])
    mod_names = [m.get("module_name") for m in all_mods]
    print(f"[7] RepairContext preservation: is_fix={is_fix_ok}, repair_context present={ctx_ok}, all_modules={mod_names}")

    # --- Step 5: Run Coder (just to verify it receives the command) ---
    channel.send(coder_cmd)
    coder.step()
    print(f"[8] Coder received repair command (Mock LLM called {mock_provider.call_count} time)")

    # --- Final verdict ---
    if prompt_match and is_fix_ok and ctx_ok and "cli.py" in mod_names and "todo_manager.py" in mod_names:
        print("PASS: ENGINEER_CODER_REPAIR_FORWARDING_VERIFIED")
    else:
        print("FAIL: Engineer→Coder forwarding incomplete")
        if not prompt_match:
            print("FIRST DIVERGENCE: CODER_RECEIVED_PROMPT")
            print("EXPECTED: Coder payload['code'] equals Engineer prompt")
            print("ACTUAL: mismatch")
            print("EVIDENCE: Engineer prompt (first 100): " + engineer_prompt[:100])
            print("EVIDENCE: Coder code (first 100): " + coder_payload.get("code", "")[:100])
        elif not is_fix_ok or not ctx_ok:
            print("FIRST DIVERGENCE: CODER_REPAIR_CONTEXT")
            print("EXPECTED: is_fix=True, repair_context present")
            print("ACTUAL: is_fix={}, repair_context present={}".format(is_fix_ok, ctx_ok))
        else:
            missing = [m for m in ["cli.py", "todo_manager.py"] if m not in mod_names]
            print("FIRST DIVERGENCE: ALL_MODULES_COLLECTED")
            print("EXPECTED: all_modules contains cli.py and todo_manager.py")
            print("ACTUAL: missing " + str(missing))

finally:
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)