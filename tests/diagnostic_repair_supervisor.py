# === RUN OUTPUT (expected) ===
# [STEP 1] Tester initial → runtime_failure
# [STEP 2] Supervisor triggered repair
# [STEP 3] RepairContext all_modules: ['storage.py', 'todo_manager.py', 'cli.py']
# [STEP 4] Engineer built multi-module repair prompt
# [STEP 5] Coder called generator (1 time)
# [STEP 6] Coder wrote files: cli.py, todo_manager.py
# [STEP 7] Tester after repair → passed
# [STEP 8] Supervisor final status: completed
# Verification:
#   - fix_attempts['cli.py'] == 1
#   - cli.py output format corrected
#   - todo_manager.py contains dict pattern
#   - Mock LLM called exactly once
#   - Engineer prompt contains CLI contract instruction
# PASS: REPAIR_LOOP_ORCHESTRATION_VERIFIED

import os
import sys
import json
import tempfile
import traceback

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from communication.message import Message
from communication.message_channel import MessageChannel
from workspace.workspace_manager import WorkspaceManager
from agents.supervisor import Supervisor
from agents.engineer import Engineer
from agents.coder import Coder
from agents.tester import Tester
from project_design.code_generator_llm import CodeGeneratorLLM
from project_design.code_executor import CodeExecutor

# ----------------------------------------------------------------------
# Mock LLM Provider
# ----------------------------------------------------------------------
class MockLLMProvider:
    def __init__(self, corrected_json_str):
        self.corrected_json = corrected_json_str
        self.call_count = 0
        self.last_messages = None

    def generate(self, messages, model, max_tokens, temperature):
        self.call_count += 1
        self.last_messages = messages
        return self.corrected_json

# ----------------------------------------------------------------------
# Dummy designer for Engineer
# ----------------------------------------------------------------------
class DummyDesigner:
    def design(self, idea):
        return {}

# ----------------------------------------------------------------------
# Module sources
# ----------------------------------------------------------------------
STORAGE_CODE = """import json

class TodoStorage:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def load_todos(self) -> list:
        try:
            with open(self.file_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_todos(self, todos: list) -> bool:
        with open(self.file_path, 'w') as f:
            json.dump(todos, f)
        return True
"""

# Buggy: stores plain strings
FAULTY_TODO = """from storage import TodoStorage

class TodoManager:
    def __init__(self, storage_path: str):
        self.storage = TodoStorage(storage_path)
        self.todos = self.storage.load_todos()

    def add_todo(self, description: str) -> bool:
        self.todos.append(description)
        return True

    def remove_todo(self, todo_id: int) -> bool:
        self.todos = [t for t in self.todos if not isinstance(t, str) or str(todo_id) in t]
        return True

    def list_todos(self) -> list:
        return self.todos
"""

# Old CLI with colon
OLD_CLI_CODE = """import argparse
from todo_manager import TodoManager

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['add', 'remove', 'list'])
    parser.add_argument('args', nargs='*')
    args = parser.parse_args()
    mgr = TodoManager('todos.json')
    if args.command == 'add':
        desc = ' '.join(args.args)
        mgr.add_todo(desc)
        mgr.storage.save_todos(mgr.todos)
    elif args.command == 'list':
        for todo in mgr.list_todos():
            print(f"{todo['id']}: {todo['description']}")
    elif args.command == 'remove':
        if args.args:
            tid = int(args.args[0])
            mgr.remove_todo(tid)
            mgr.storage.save_todos(mgr.todos)

if __name__ == '__main__':
    main()
"""

# Corrected code for both modules
CORRECTED_TODO = """from storage import TodoStorage

class TodoManager:
    def __init__(self, storage_path: str):
        self.storage = TodoStorage(storage_path)
        self.todos = self.storage.load_todos()

    def add_todo(self, description: str) -> bool:
        todo_id = len(self.todos) + 1
        self.todos.append({'id': todo_id, 'description': description})
        return True

    def remove_todo(self, todo_id: int) -> bool:
        self.todos = [t for t in self.todos if t.get('id') != todo_id]
        return True

    def list_todos(self) -> list:
        return self.todos
"""

NEW_CLI_CODE = """import argparse
from todo_manager import TodoManager

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['add', 'remove', 'list'])
    parser.add_argument('args', nargs='*')
    args = parser.parse_args()
    mgr = TodoManager('todos.json')
    if args.command == 'add':
        desc = ' '.join(args.args)
        mgr.add_todo(desc)
        mgr.storage.save_todos(mgr.todos)
    elif args.command == 'list':
        for todo in mgr.list_todos():
            print(f"{todo['id']} {todo['description']}")
    elif args.command == 'remove':
        if args.args:
            tid = int(args.args[0])
            mgr.remove_todo(tid)
            mgr.storage.save_todos(mgr.todos)

if __name__ == '__main__':
    main()
"""

# ----------------------------------------------------------------------
# Main diagnostic
# ----------------------------------------------------------------------
tmpdir = tempfile.mkdtemp()
trace = []

def log(msg):
    trace.append(msg)
    print(msg)

try:
    import config
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

    # Write initial buggy modules
    with open(os.path.join(out, 'storage.py'), 'w') as f: f.write(STORAGE_CODE)
    with open(os.path.join(out, 'todo_manager.py'), 'w') as f: f.write(FAULTY_TODO)
    with open(os.path.join(out, 'cli.py'), 'w') as f: f.write(OLD_CLI_CODE)

    # Contracts
    contracts = {
        "storage.py": {"module": "storage.py", "exports": [], "dependencies": [], "generated": True, "validated": True},
        "todo_manager.py": {"module": "todo_manager.py", "exports": [], "dependencies": ["storage.py"], "generated": True, "validated": True},
        "cli.py": {"module": "cli.py", "exports": [], "dependencies": ["todo_manager.py"], "generated": True, "validated": False}
    }
    with open(os.path.join(ws, 'contracts.json'), 'w') as f: json.dump(contracts, f, indent=2)

    # Mock LLM and real agents
    corrected_json = json.dumps({"cli.py": NEW_CLI_CODE, "todo_manager.py": CORRECTED_TODO})
    mock_provider = MockLLMProvider(corrected_json)
    generator = CodeGeneratorLLM(mock_provider)

    wm = WorkspaceManager()
    channel = MessageChannel()
    executor = CodeExecutor()

    supervisor = Supervisor(channel, wm, debugger=None, api_inspector=None, semantic_analyzer=None)
    engineer = Engineer(channel, wm, DummyDesigner(), knowledge_base=None)
    coder = Coder(channel, wm, generator, context_manager=None, knowledge_base=None)
    tester = Tester(channel, wm, executor)

    # ---- Step 1: Initial Tester execution ----
    cli_path = os.path.join(out, 'cli.py')
    init_tester_msg = Message(
        sender="supervisor", receiver="tester", msg_type="CommandMsg", phase=1,
        payload={"action": "test", "filepath": cli_path}
    )
    init_result = tester.process_command(init_tester_msg)
    init_status = init_result.payload.get('status')
    log(f"[STEP 1] Tester initial → {init_status}")
    if init_status != 'runtime_failure':
        log(f"UNEXPECTED INITIAL TESTER RESULT: {init_result.payload}")
        sys.exit(1)

    # ---- Feed the failure to Supervisor ----
    supervisor.status = "waiting_for_tester"
    supervisor.modules = [
        {"filename": "storage.py", "dependencies": []},
        {"filename": "todo_manager.py", "dependencies": ["storage.py"]},
        {"filename": "cli.py", "dependencies": ["todo_manager.py"]}
    ]
    supervisor.current_module_index = 2   # cli.py
    supervisor.fix_attempts = {}
    channel.send(init_result)

    # ---- Step loop ----
    agents = [engineer, coder, tester]
    max_steps = 50
    step = 0
    while supervisor.status not in ("completed", "error") and step < max_steps:
        supervisor.step()
        for agent in agents:
            agent.step()
        step += 1
        if step == 1:
            log("[STEP 2] Supervisor triggered repair")
            # Capture repair context (observation only)
            try:
                eng_cmd = channel.receive("engineer", timeout=0.1)
                if eng_cmd:
                    all_mods = eng_cmd.payload.get("repair_context", {}).get("all_modules", [])
                    mod_names = [m.get("module_name") for m in all_mods]
                    log(f"[STEP 3] RepairContext all_modules: {mod_names}")
                    # re-inject so Engineer can process
                    channel.send(eng_cmd)
            except Exception:
                pass

    # ---- After loop ----
    final_status = supervisor.status
    fix_attempts = supervisor.fix_attempts
    log(f"[STEP 8] Supervisor final status: {final_status}")

    # ---- Verification ----
    # 1. fix_attempts
    attempts_ok = fix_attempts.get("cli.py", -1) == 1
    log(f"fix_attempts['cli.py'] == 1: {attempts_ok}")

    # 2. File content checks
    cli_final_path = os.path.join(out, 'cli.py')
    todo_final_path = os.path.join(out, 'todo_manager.py')
    with open(cli_final_path, 'r') as f:
        new_cli = f.read()
    with open(todo_final_path, 'r') as f:
        new_todo = f.read()

    cli_format_ok = "'id']} {todo['description']}" in new_cli or "{todo['id']} {todo['description']}" in new_cli
    todo_dict_ok = "'id': todo_id" in new_todo and "'description': description" in new_todo
    log(f"cli.py output format corrected: {cli_format_ok}")
    log(f"todo_manager.py contains dict pattern: {todo_dict_ok}")

    # 3. Mock LLM call count
    llm_calls_ok = mock_provider.call_count == 1
    log(f"Mock LLM called exactly once: {llm_calls_ok}")

    # 4. Engineer prompt contains contract instruction (inspect last mock prompt)
    eng_prompt_ok = False
    if mock_provider.last_messages:
        user_msg = mock_provider.last_messages[-1] if isinstance(mock_provider.last_messages, list) else ""
        eng_prompt_ok = "2.5. If `cli.py` is among the modified files" in str(user_msg)
    log(f"Engineer prompt contains CLI contract instruction: {eng_prompt_ok}")

    # Final verdict
    all_ok = (
        final_status == "completed"
        and attempts_ok
        and cli_format_ok
        and todo_dict_ok
        and llm_calls_ok
        and eng_prompt_ok
        and init_status == 'runtime_failure'
    )
    if all_ok:
        log("\nPASS: REPAIR_LOOP_ORCHESTRATION_VERIFIED")
    else:
        log("\nFAIL: REPAIR_LOOP_ORCHESTRATION_FAILED")
        # detailed divergence
        if not attempts_ok:
            log(f"FIRST DIVERGENCE: fix_attempts expected 1, got {fix_attempts.get('cli.py')}")
        if not cli_format_ok:
            log(f"FIRST DIVERGENCE: cli.py still contains old format (colon)")
        if not todo_dict_ok:
            log(f"FIRST DIVERGENCE: todo_manager.py not repaired")
        if not llm_calls_ok:
            log(f"FIRST DIVERGENCE: Mock LLM called {mock_provider.call_count} times")
        if not eng_prompt_ok:
            log(f"FIRST DIVERGENCE: Engineer prompt missing CLI contract instruction")

except Exception:
    traceback.print_exc()
finally:
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)
    print("\n".join(trace))