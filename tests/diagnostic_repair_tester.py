# === CONSOLE OUTPUT (expected) ===
# Initial todo_manager.py contains 'self.todos.append(description)' (no dict)
# After Coder repair: todo_manager.py contains 'id': todo_id' and 'description': description'
# === TESTER COMMAND ===
# filepath: /tmp/.../output/cli.py
# action: test
# phase: 1
# === TESTER RESULT ===
# status: passed
# return_code: 0
# stdout: (empty or help text)
# stderr: (empty)
# full payload: {'filepath': ..., 'status': 'passed', 'execution_status': 'cli_acceptance_passed'}
# === SUPERVISOR ===
# status before: waiting_for_tester
# status after: completed
# Supervisor did NOT trigger another repair
# ROOT CAUSE IDENTIFIED: NONE - Tester passed, Supervisor completed

import os
import sys
import json
import tempfile
import importlib
import shutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from communication.message import Message
from communication.message_channel import MessageChannel
from workspace.workspace_manager import WorkspaceManager
from agents.tester import Tester
from agents.coder import Coder
from agents.supervisor import Supervisor
from project_design.code_generator_llm import CodeGeneratorLLM

# ----------------------------------------------------------------------
# Mock LLM Provider – returns corrected multi-file JSON
# ----------------------------------------------------------------------
class MockLLMProvider:
    def __init__(self, cli_code, corrected_todo):
        self.cli_code = cli_code
        self.corrected_todo = corrected_todo
        self.call_count = 0

    def generate(self, messages, model, max_tokens, temperature):
        self.call_count += 1
        return json.dumps({
            "cli.py": self.cli_code,
            "todo_manager.py": self.corrected_todo
        })

# ----------------------------------------------------------------------
# Dynamic Mock Executor – runs actual code from disk, no subprocess
# ----------------------------------------------------------------------
class DynamicAcceptanceExecutor:
    def __init__(self, output_dir):
        self.output_dir = output_dir

    def execute(self, filepath, working_directory=None, timeout_seconds=10, args=None):
        basename = os.path.basename(filepath)
        if basename != 'cli.py':
            return {"status": "passed", "return_code": 0, "stdout": "", "stderr": "", "execution_time": 0.0}

        if self.output_dir not in sys.path:
            sys.path.insert(0, self.output_dir)

        importlib.invalidate_caches()
        for name in ("storage", "todo_manager", "cli"):
            sys.modules.pop(name, None)
        try:
            storage = importlib.import_module("storage")
            todo_manager = importlib.import_module("todo_manager")
            cli = importlib.import_module("cli")
        except Exception as e:
            return {"status": "error", "return_code": -1, "stdout": "", "stderr": str(e), "execution_time": 0.0}

        old_cwd = os.getcwd()
        old_argv = sys.argv
        old_stdout = sys.stdout
        import io
        try:
            os.chdir(self.output_dir)
            todos_path = os.path.join(self.output_dir, "todos.json")
            if os.path.exists(todos_path):
                os.remove(todos_path)
            sys.stdout = io.StringIO()
            sys.argv = ['cli.py'] + (args or [])
            cli.main()
            output = sys.stdout.getvalue()
            return {"status": "passed", "return_code": 0, "stdout": output, "stderr": "", "execution_time": 0.0}
        except SystemExit as e:
            output = sys.stdout.getvalue()
            return {"status": "passed" if e.code == 0 else "failed", "return_code": e.code or 0, "stdout": output, "stderr": "", "execution_time": 0.0}
        except Exception as e:
            output = sys.stdout.getvalue()
            return {"status": "failed", "return_code": 1, "stdout": output, "stderr": str(e), "execution_time": 0.0}
        finally:
            sys.stdout = old_stdout
            sys.argv = old_argv
            os.chdir(old_cwd)

    def classify_error(self, stderr):
        return "unknown"

# ----------------------------------------------------------------------
# Dummy designer for Engineer (not used in this test)
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

CLI_CODE = """import argparse
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

# ----------------------------------------------------------------------
# Main diagnostic
# ----------------------------------------------------------------------
tmpdir = tempfile.mkdtemp()
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
    with open(os.path.join(out, 'cli.py'), 'w') as f: f.write(CLI_CODE)

    print("Initial todo_manager.py contains 'self.todos.append(description)' (no dict)")

    # Contracts
    contracts = {
        "storage.py": {"module": "storage.py", "exports": [], "dependencies": [], "generated": True, "validated": True},
        "todo_manager.py": {"module": "todo_manager.py", "exports": [], "dependencies": ["storage.py"], "generated": True, "validated": True},
        "cli.py": {"module": "cli.py", "exports": [], "dependencies": ["todo_manager.py"], "generated": True, "validated": False}
    }
    with open(os.path.join(ws, 'contracts.json'), 'w') as f: json.dump(contracts, f, indent=2)

    # Instantiate Coder with mock LLM to repair
    mock_provider = MockLLMProvider(CLI_CODE, CORRECTED_TODO)
    generator = CodeGeneratorLLM(mock_provider)
    wm = WorkspaceManager()
    ch = MessageChannel()
    coder = Coder(ch, wm, generator, context_manager=None, knowledge_base=None)

    # Build repair command for Coder (as Supervisor would)
    repair_ctx = {
        "module_name": "cli.py",
        "filepath": os.path.join(out, "cli.py"),
        "all_modules": [
            {"module_name": "storage.py", "source_code": STORAGE_CODE, "contract": {}},
            {"module_name": "todo_manager.py", "source_code": FAULTY_TODO, "contract": {}},
            {"module_name": "cli.py", "source_code": CLI_CODE, "contract": {}},
        ],
        "current_code": CLI_CODE,
        "contract": {"exports": []},
        "api_errors": [],
        "semantic_errors": [],
        "runtime_error": "list did not contain 'Test todo'",
        "debugger_analysis": None,
        "previous_attempts": 1,
    }
    coder_cmd = Message(
        sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=1,
        payload={
            "action": "code",
            "filename": "cli.py",
            "description": "CLI module",
            "dependencies": ["todo_manager.py"],
            "purpose": "entry",
            "code": "DUMMY_REPAIR_PROMPT",
            "is_fix": True,
            "repair_context": repair_ctx,
        }
    )
    coder.process_command(coder_cmd)

    # Verify repair
    with open(os.path.join(out, 'todo_manager.py'), 'r') as f:
        repaired_content = f.read()
    if "'id':" in repaired_content:
        print("After Coder repair: todo_manager.py contains 'id': todo_id' and 'description': description'")
    else:
        print("Repair did not apply correctly")

    # Now set up real Tester with DynamicAcceptanceExecutor
    executor = DynamicAcceptanceExecutor(out)
    tester = Tester(ch, wm, executor)

    # Build Tester command
    cli_path = os.path.join(out, 'cli.py')
    tester_cmd = Message(
        sender="supervisor", receiver="tester", msg_type="CommandMsg", phase=1,
        payload={"action": "test", "filepath": cli_path}
    )
    print("\n=== TESTER COMMAND ===")
    print(f"filepath: {cli_path}")
    print("action: test")
    print("phase: 1")

    result = tester.process_command(tester_cmd)
    print("\n=== TESTER RESULT ===")
    print(f"status: {result.payload.get('status')}")
    print(f"return_code: {result.payload.get('return_code')}")
    print(f"stdout: {result.payload.get('stdout', '')}")
    print(f"stderr: {result.payload.get('stderr', '')}")
    print(f"full payload: {result.payload}")

    # Supervisor check
    supervisor = Supervisor(ch, wm, debugger=None, api_inspector=None, semantic_analyzer=None)
    supervisor.status = "waiting_for_tester"
    supervisor.modules = [
        {"filename": "storage.py", "dependencies": []},
        {"filename": "todo_manager.py", "dependencies": ["storage.py"]},
        {"filename": "cli.py", "dependencies": ["todo_manager.py"]}
    ]
    supervisor.current_module_index = 2
    supervisor.fix_attempts = {}

    print(f"\n=== SUPERVISOR ===")
    print(f"status before: {supervisor.status}")
    ch.send(result)
    supervisor.step()
    print(f"status after: {supervisor.status}")

    if supervisor.status == "completed" or supervisor.status != "waiting_for_engineer":
        print("Supervisor did NOT trigger another repair")
        if result.payload.get("status") == "passed":
            print("ROOT CAUSE IDENTIFIED: NONE - Tester passed, Supervisor completed")
        else:
            print("ROOT CAUSE IDENTIFIED: ACCEPTANCE_TEST_PROBLEM")
            print("EVIDENCE: Tester returned non-passed status on repaired code")
    else:
        print("Supervisor triggered another repair")
        eng_cmd = ch.receive("engineer", timeout=0.1)
        if eng_cmd:
            print("Engineer repair command present - repairing again")
            print("ROOT CAUSE IDENTIFIED: SUPERVISOR_INTERPRETATION_PROBLEM or ACCEPTANCE_TEST_FAILURE")
        else:
            print("No Engineer command - unexpected state")

except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)