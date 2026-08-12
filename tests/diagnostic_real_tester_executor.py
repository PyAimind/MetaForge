# === RUN OUTPUT (expected) ===
# Corrected project files written.
# cli.py path: /tmp/.../output/cli.py
# todo_manager.py path: /tmp/.../output/todo_manager.py
# First lines of todo_manager.py:
#   from storage import TodoStorage
#   class TodoManager:
#       def __init__(self, storage_path: str):
#           self.storage = TodoStorage(storage_path)
#           self.todos = self.storage.load_todos()
#       def add_todo(self, description: str) -> bool:
#           todo_id = len(self.todos) + 1
#           self.todos.append({'id': todo_id, 'description': description})
#           return True
#       def remove_todo(self, todo_id: int) -> bool:
#           self.todos = [t for t in self.todos if t.get('id') != todo_id]
#           return True
#       def list_todos(self) -> list:
#           return self.todos
# Contains dict pattern: True
# --- Invoking Tester.process_command() ---
# === REAL TESTER RESULT ===
# status: passed
# return_code: 0
# stdout: ...
# stderr: ...
# reason: None
# execution_status: cli_acceptance_passed
# full payload: {...}
# RESULT: REAL TESTER PASSED ON REPAIRED CODE
# NEXT: The remaining bug is in the repair-loop orchestration/state between Tester executions.

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
from agents.tester import Tester
from project_design.code_executor import CodeExecutor

# ----------------------------------------------------------------------
# Module sources (consistent with Phase 4 – corrected todo_manager)
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
# Main test
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

    # Write corrected modules
    with open(os.path.join(out, 'storage.py'), 'w') as f:
        f.write(STORAGE_CODE)
    with open(os.path.join(out, 'todo_manager.py'), 'w') as f:
        f.write(CORRECTED_TODO)
    with open(os.path.join(out, 'cli.py'), 'w') as f:
        f.write(CLI_CODE)

    print("Corrected project files written.")
    print(f"cli.py path: {os.path.join(out, 'cli.py')}")
    print(f"todo_manager.py path: {os.path.join(out, 'todo_manager.py')}")
    with open(os.path.join(out, 'todo_manager.py'), 'r') as f:
        lines = f.readlines()
    print("First lines of todo_manager.py:")
    for line in lines[:20]:
        print("  " + line.rstrip())
    print("Contains dict pattern:", "'id': todo_id" in ''.join(lines))

    # Contracts (as Phase 4 would have)
    contracts = {
        "storage.py": {"module": "storage.py", "exports": [], "dependencies": [], "generated": True, "validated": True},
        "todo_manager.py": {"module": "todo_manager.py", "exports": [], "dependencies": ["storage.py"], "generated": True, "validated": True},
        "cli.py": {"module": "cli.py", "exports": [], "dependencies": ["todo_manager.py"], "generated": True, "validated": False}
    }
    with open(os.path.join(ws, 'contracts.json'), 'w') as f:
        json.dump(contracts, f, indent=2)

    # Instantiate real Tester with real CodeExecutor
    channel = MessageChannel()
    workspace = WorkspaceManager()
    executor = CodeExecutor()
    tester = Tester(channel, workspace, executor)

    # Build Tester command exactly as Supervisor would
    cli_path = os.path.join(out, 'cli.py')
    cmd = Message(
        sender="supervisor",
        receiver="tester",
        msg_type="CommandMsg",
        phase=1,
        payload={"action": "test", "filepath": cli_path}
    )

    print("\n--- Invoking Tester.process_command() ---")
    result = tester.process_command(cmd)

    print("\n=== REAL TESTER RESULT ===")
    print("status:", result.payload.get('status'))
    print("return_code:", result.payload.get('return_code'))
    print("stdout:", result.payload.get('stdout'))
    print("stderr:", result.payload.get('stderr'))
    print("reason:", result.payload.get('reason'))
    print("execution_status:", result.payload.get('execution_status'))
    print("full payload:", result.payload)

    # Determine final conclusion
    if result.payload.get('status') == 'passed':
        print("\nRESULT: REAL TESTER PASSED ON REPAIRED CODE")
        print("NEXT: The remaining bug is in the repair-loop orchestration/state between Tester executions.")
    elif result.payload.get('status') == 'runtime_failure':
        print("\nRESULT: REAL TESTER FAILED ON REPAIRED CODE")
        print("FAILURE REASON:", result.payload.get('reason', result.payload.get('stderr', '')))
        print("NEXT: The bug is inside the real Tester/CodeExecutor/acceptance-test execution path.")
    else:
        print("\nRESULT: REAL EXECUTION ERROR")
        print("ERROR:", result.payload.get('reason', ''))
        print("NEXT: Investigate the exception and traceback.")

except Exception as e:
    import traceback
    print("\nRESULT: REAL EXECUTION ERROR")
    print("ERROR:", e)
    traceback.print_exc()
finally:
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)