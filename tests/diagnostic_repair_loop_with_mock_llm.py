import os
import sys
import json
import tempfile
import traceback
from collections import deque

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

# ----------------------------------------------------------------------
# Trace helper
# ----------------------------------------------------------------------
trace = deque()

def log(msg):
    trace.append(msg)

# ----------------------------------------------------------------------
# Mock Executor – deterministic, no subprocess
# ----------------------------------------------------------------------
class MockExecutor:
    def __init__(self):
        self.call_counts = {}

    def execute(self, filepath, working_directory=None, timeout_seconds=10, args=None):
        base = os.path.basename(filepath)
        count = self.call_counts.get(base, 0)
        self.call_counts[base] = count + 1
        if base == "cli.py" and count == 0:
            return {
                "status": "failed",
                "return_code": 1,
                "stdout": "",
                "stderr": "list did not contain 'Test todo'",
                "execution_time": 0.0
            }
        return {
            "status": "passed",
            "return_code": 0,
            "stdout": "OK",
            "stderr": "",
            "execution_time": 0.0
        }

    def classify_error(self, stderr):
        return "unknown"

# ----------------------------------------------------------------------
# Mock LLM Provider – returns corrected multi-module JSON
# ----------------------------------------------------------------------
class MockLLMProvider:
    def __init__(self, cli_content, corrected_todo):
        self.cli_content = cli_content
        self.corrected_todo = corrected_todo
        self.call_count = 0

    def generate(self, messages, model, max_tokens, temperature):
        self.call_count += 1
        return json.dumps({
            "cli.py": self.cli_content,
            "todo_manager.py": self.corrected_todo
        })

# ----------------------------------------------------------------------
# Dummy designer (Engineer requires one)
# ----------------------------------------------------------------------
class DummyDesigner:
    def design(self, idea):
        return {}

# ----------------------------------------------------------------------
# Module source code
# ----------------------------------------------------------------------
STORAGE_CODE = """class TodoStorage:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.data = []
    def load_todos(self) -> list:
        return self.data.copy()
    def save_todos(self, todos: list) -> bool:
        self.data = todos.copy()
        return True
"""

FAULTY_TODO = """from storage import TodoStorage

class TodoManager:
    def __init__(self, storage_path: str):
        self.storage = TodoStorage(storage_path)
        self.todos = self.storage.load_todos()

    def add_todo(self, description: str) -> bool:
        self.todos.append(description)   # BUG: plain string instead of dict
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
    config.WORKSPACE_DIR = os.path.join(tmpdir, 'workspace')
    config.OUTPUT_DIR   = os.path.join(tmpdir, 'output')
    config.PHASE_FILE   = os.path.join(config.WORKSPACE_DIR, 'current_phase.json')
    config.LOG_FILE     = os.path.join(config.WORKSPACE_DIR, 'build_log.json')
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, 'project_structure.json')
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, 'test_results.json')
    os.makedirs(config.WORKSPACE_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    # Write initial faulty modules
    for fname, content in [
        ("storage.py", STORAGE_CODE),
        ("todo_manager.py", FAULTY_TODO),
        ("cli.py", CLI_CODE)
    ]:
        with open(os.path.join(config.OUTPUT_DIR, fname), 'w', encoding='utf-8') as f:
            f.write(content)

    # Contracts
    contracts = {
        "storage.py": {
            "module": "storage.py",
            "exports": [
                {
                    "name": "TodoStorage",
                    "kind": "class",
                    "constructor": {"parameters": [{"name": "file_path", "type": "str"}]},
                    "methods": [
                        {"name": "load_todos", "kind": "function", "parameters": [], "returns": "list"},
                        {"name": "save_todos", "kind": "function", "parameters": [{"name": "todos", "type": "list"}], "returns": "bool"}
                    ]
                }
            ],
            "dependencies": [],
            "generated": True,
            "validated": True
        },
        "todo_manager.py": {
            "module": "todo_manager.py",
            "exports": [
                {
                    "name": "TodoManager",
                    "kind": "class",
                    "constructor": {"parameters": [{"name": "storage_path", "type": "str"}]},
                    "methods": [
                        {"name": "add_todo", "kind": "function", "parameters": [{"name": "description", "type": "str"}], "returns": "bool"},
                        {"name": "remove_todo", "kind": "function", "parameters": [{"name": "todo_id", "type": "int"}], "returns": "bool"},
                        {"name": "list_todos", "kind": "function", "parameters": [], "returns": "list"}
                    ]
                }
            ],
            "dependencies": ["storage.py"],
            "generated": True,
            "validated": True
        },
        "cli.py": {
            "module": "cli.py",
            "exports": [],
            "dependencies": ["todo_manager.py"],
            "generated": True,
            "validated": False
        }
    }
    with open(os.path.join(config.WORKSPACE_DIR, 'contracts.json'), 'w', encoding='utf-8') as f:
        json.dump(contracts, f, indent=2)

    # Instantiate real agents with mock executor and mock LLM
    workspace = WorkspaceManager()
    channel = MessageChannel()
    mock_executor = MockExecutor()
    mock_provider = MockLLMProvider(CLI_CODE, CORRECTED_TODO)
    generator = CodeGeneratorLLM(mock_provider)

    supervisor = Supervisor(channel, workspace, debugger=None, api_inspector=None, semantic_analyzer=None)
    engineer = Engineer(channel, workspace, DummyDesigner(), knowledge_base=None)
    coder = Coder(channel, workspace, generator, context_manager=None, knowledge_base=None)
    tester = Tester(channel, workspace, mock_executor)

    # Set initial state: Supervisor waiting for coder for cli.py
    supervisor.status = "waiting_for_coder"
    supervisor.modules = [
        {"filename": "storage.py", "dependencies": []},
        {"filename": "todo_manager.py", "dependencies": ["storage.py"]},
        {"filename": "cli.py", "dependencies": ["todo_manager.py"]}
    ]
    supervisor.current_module_index = 2  # cli.py is the current module
    supervisor.fix_attempts = {}

    # Inject a fake Coder success message for cli.py (as if it just built the buggy module)
    coder_success = Message(
        sender="coder",
        receiver="supervisor",
        msg_type="ResultMsg",
        phase=1,
        payload={
            "status": "success",
            "filepath": os.path.join(config.OUTPUT_DIR, "cli.py")
        }
    )
    channel.send(coder_success)

    # Monkey-patch agent process_command for observation only
    orig_super_step = supervisor.step
    orig_engineer_process = engineer.process_command
    orig_coder_process = coder.process_command
    orig_tester_process = tester.process_command

    def wrap_supervisor_step():
        prev_status = supervisor.status
        result = orig_super_step()
        new_status = supervisor.status
        if new_status != prev_status:
            log(f"[supervisor] status {prev_status} → {new_status}")
        return result

    def wrap_engineer(msg):
        result = orig_engineer_process(msg)
        if msg.payload.get("repair_context"):
            log(f"[engineer] repair prompt generated")
        return result

    def wrap_coder(msg):
        result = orig_coder_process(msg)
        if msg.payload.get("is_fix"):
            log(f"[coder] repair processed, status={result.payload.get('status')}")
        return result

    def wrap_tester(msg):
        result = orig_tester_process(msg)
        log(f"[tester] result status={result.payload.get('status')} for {msg.payload.get('filepath','')}")
        return result

    supervisor.step = wrap_supervisor_step
    engineer.process_command = wrap_engineer
    coder.process_command = wrap_coder
    tester.process_command = wrap_tester

    # Step loop
    agents = [engineer, coder, tester]
    max_steps = 50
    step = 0
    while supervisor.status not in ("completed", "error") and step < max_steps:
        supervisor.step()
        for agent in agents:
            agent.step()
        step += 1

    # Final state
    final_status = supervisor.status
    log(f"Final supervisor status: {final_status}")
    log(f"Fix attempts: {supervisor.fix_attempts}")
    log(f"Mock LLM calls: {mock_provider.call_count}")

    # Check output directory
    written = sorted(os.listdir(config.OUTPUT_DIR)) if os.path.isdir(config.OUTPUT_DIR) else []
    log(f"Files in output dir: {written}")
    todo_path = os.path.join(config.OUTPUT_DIR, "todo_manager.py")
    if os.path.exists(todo_path):
        with open(todo_path, 'r', encoding='utf-8') as f:
            content = f.read()
        if "'id':" in content:
            log("todo_manager.py contains correct dict structure")
        else:
            log("todo_manager.py still faulty")
    else:
        log("todo_manager.py missing")

    # Restore original methods
    supervisor.step = orig_super_step
    engineer.process_command = orig_engineer_process
    coder.process_command = orig_coder_process
    tester.process_command = orig_tester_process

    # Print trace
    print("\n=== STEP TRACE ===")
    for line in trace:
        print(line)

    # Verdict
    if final_status == "completed":
        print("\nPASS: REPAIR_LOOP_ORCHESTRATION_VERIFIED")
    else:
        print("\nFAIL: REPAIR_LOOP_ORCHESTRATION_FAILED")
        # Determine first divergence by inspecting trace (simplified)
        # In a full implementation we could check checkpoints; here we just report.
        print("First divergence detected at final status.")
except Exception:
    traceback.print_exc()
finally:
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)