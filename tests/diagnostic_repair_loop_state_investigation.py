# === RUN OUTPUT ===
# (Run the script and paste output here)

import os
import sys
import json
import tempfile
import queue
import hashlib
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


class MockLLMProvider:
    def __init__(self, corrected_json_str):
        self.corrected_json = corrected_json_str
        self.call_count = 0

    def generate(self, messages, model, max_tokens, temperature):
        self.call_count += 1
        return self.corrected_json


class DummyDesigner:
    def design(self, idea):
        return {}


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


def print_file_state(label, path):
    print(f"FILE STATE: {label}")
    if not os.path.exists(path):
        print("  exists: False")
        return None
    with open(path, 'rb') as f:
        raw = f.read()
    sha = hashlib.sha256(raw).hexdigest()
    size = len(raw)
    mtime = os.path.getmtime(path)
    text = raw.decode('utf-8', errors='replace')
    first_lines = text.splitlines()[:5]
    print(f"  exists: True")
    print(f"  sha256: {sha}")
    print(f"  size: {size} bytes")
    print(f"  mtime: {mtime}")
    print("  first_5_lines:")
    for line in first_lines:
        print(f"    {line}")
    return {
        'sha': sha,
        'size': size,
        'mtime': mtime,
        'content': text,
        'first_lines': first_lines
    }


def classify_state(info, kind):
    if info is None:
        return "MISSING"
    content = info['content']
    if kind == 'cli':
        if "{todo['id']}: {todo['description']}" in content:
            return "OLD"
        elif "{todo['id']} {todo['description']}" in content:
            return "NEW"
        else:
            return "DIFFERENT"
    elif kind == 'todo_manager':
        if "'id': todo_id" in content and "'description': description" in content:
            return "NEW"
        elif "self.todos.append(description)" in content:
            return "OLD"
        else:
            return "DIFFERENT"
    else:
        return "UNKNOWN"


def receive_from(channel, name, timeout=0.5):
    try:
        return channel.receive(name, timeout)
    except queue.Empty:
        return None


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

    # Write initial faulty modules
    with open(os.path.join(out, 'storage.py'), 'w', encoding='utf-8') as f:
        f.write(STORAGE_CODE)
    with open(os.path.join(out, 'todo_manager.py'), 'w', encoding='utf-8') as f:
        f.write(FAULTY_TODO)
    with open(os.path.join(out, 'cli.py'), 'w', encoding='utf-8') as f:
        f.write(OLD_CLI_CODE)

    # Contracts
    contracts = {
        "storage.py": {"module": "storage.py", "exports": [], "dependencies": [], "generated": True, "validated": True},
        "todo_manager.py": {"module": "todo_manager.py", "exports": [], "dependencies": ["storage.py"], "generated": True, "validated": True},
        "cli.py": {"module": "cli.py", "exports": [], "dependencies": ["todo_manager.py"], "generated": True, "validated": False}
    }
    with open(os.path.join(ws, 'contracts.json'), 'w', encoding='utf-8') as f:
        json.dump(contracts, f, indent=2)

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

    # ---------- Initial Tester failure ----------
    cli_path = os.path.join(out, 'cli.py')
    init_cmd = Message(
        sender="supervisor", receiver="tester", msg_type="CommandMsg", phase=1,
        payload={"action": "test", "filepath": cli_path}
    )
    init_result = tester.process_command(init_cmd)
    print("=== INITIAL TESTER RESULT ===")
    print(f"status: {init_result.payload.get('status')}")
    print(f"reason: {init_result.payload.get('reason')}")
    print(f"full payload: {init_result.payload}")

    # Prepare Supervisor state
    supervisor.status = "waiting_for_tester"
    supervisor.modules = [
        {"filename": "storage.py", "dependencies": []},
        {"filename": "todo_manager.py", "dependencies": ["storage.py"]},
        {"filename": "cli.py", "dependencies": ["todo_manager.py"]}
    ]
    supervisor.current_module_index = 2
    supervisor.fix_attempts = {}

    # ---------- POINT A: BEFORE REPAIR ----------
    print("\n=== POINT A: BEFORE REPAIR ===")
    cli_a = print_file_state("cli.py", cli_path)
    todo_a = print_file_state("todo_manager.py", os.path.join(out, 'todo_manager.py'))
    todos_path = os.path.join(out, 'todos.json')
    todos_a = print_file_state("todos.json", todos_path)
    state_cli_a = classify_state(cli_a, 'cli')
    state_todo_a = classify_state(todo_a, 'todo_manager')
    print(f"cli.py state: {state_cli_a}")
    print(f"todo_manager.py state: {state_todo_a}")

    # ---------- Supervisor repair trigger ----------
    channel.send(init_result)
    supervisor.step()
    eng_cmd = receive_from(channel, "engineer")
    if not eng_cmd or "repair_context" not in eng_cmd.payload:
        log("FIRST DIVERGENCE: Supervisor did not send repair command to Engineer")
        sys.exit(1)
    repair_ctx = eng_cmd.payload["repair_context"]
    all_mods = repair_ctx.get("all_modules", [])
    mod_names = [m.get("module_name") for m in all_mods]
    print(f"\nRepairContext all_modules: {mod_names}")

    # Forward to Engineer
    channel.send(eng_cmd)
    engineer.step()
    eng_resp = receive_from(channel, "supervisor")
    if not eng_resp or "prompts" not in eng_resp.payload:
        log("FIRST DIVERGENCE: Engineer did not return prompts")
        sys.exit(1)

    # Forward to Supervisor -> Coder
    channel.send(eng_resp)
    supervisor.step()
    coder_cmd = receive_from(channel, "coder")
    if not coder_cmd or not coder_cmd.payload.get("is_fix"):
        log("FIRST DIVERGENCE: Supervisor did not send repair command to Coder")
        sys.exit(1)

    # Forward to Coder
    channel.send(coder_cmd)
    coder.step()

    # ---------- POINT B: AFTER CODER REPAIR WRITE ----------
    print("\n=== POINT B: AFTER CODER REPAIR WRITE ===")
    cli_b = print_file_state("cli.py", cli_path)
    todo_b = print_file_state("todo_manager.py", os.path.join(out, 'todo_manager.py'))
    todos_b = print_file_state("todos.json", todos_path)
    state_cli_b = classify_state(cli_b, 'cli')
    state_todo_b = classify_state(todo_b, 'todo_manager')
    print(f"cli.py corrected: {state_cli_b == 'NEW'}")
    print(f"todo_manager.py corrected: {state_todo_b == 'NEW'}")

    # Coder response -> Supervisor -> Tester command
    coder_resp = receive_from(channel, "supervisor")
    if not coder_resp:
        log("FIRST DIVERGENCE: Coder did not send response to Supervisor")
        sys.exit(1)
    channel.send(coder_resp)
    supervisor.step()
    tester_cmd = receive_from(channel, "tester")
    if not tester_cmd or tester_cmd.payload.get("action") != "test":
        log("FIRST DIVERGENCE: Supervisor did not send test command to Tester")
        sys.exit(1)

    # ---------- POINT C: BEFORE POST-REPAIR TESTER ----------
    print("\n=== POINT C: BEFORE POST-REPAIR TESTER ===")
    cli_c = print_file_state("cli.py", cli_path)
    todo_c = print_file_state("todo_manager.py", os.path.join(out, 'todo_manager.py'))
    todos_c = print_file_state("todos.json", todos_path)
    state_cli_c = classify_state(cli_c, 'cli')
    state_todo_c = classify_state(todo_c, 'todo_manager')
    print(f"cli.py state: {state_cli_c}")
    print(f"todo_manager.py state: {state_todo_c}")

    # ---------- Post-repair Tester ----------
    channel.send(tester_cmd)
    tester.step()
    tester_result = receive_from(channel, "supervisor")
    if tester_result is None:
        log("FIRST DIVERGENCE: Tester ResultMsg was not captured.")
        sys.exit(1)

    print("\n=== POST-REPAIR TESTER RESULT ===")
    print(f"status: {tester_result.payload.get('status')}")
    print(f"reason: {tester_result.payload.get('reason')}")
    print(f"stdout: {tester_result.payload.get('stdout')}")
    print(f"stderr: {tester_result.payload.get('stderr')}")
    print(f"return_code: {tester_result.payload.get('return_code')}")
    print(f"full payload: {tester_result.payload}")

    # Supervisor reaction
    pre_super_status = supervisor.status
    channel.send(tester_result)
    supervisor.step()
    post_super_status = supervisor.status
    print(f"\nSupervisor status before Tester result: {pre_super_status}")
    print(f"Supervisor status after Tester result: {post_super_status}")
    if post_super_status == "waiting_for_engineer":
        print("Supervisor triggered another repair.")
    else:
        print("Supervisor did NOT trigger another repair.")

    # ---------- Hash transition analysis ----------
    print("\n=== FILE TRANSITION ANALYSIS ===")
    def transition(old_state, new_state):
        if old_state == new_state:
            return f"{old_state} → {new_state}"
        else:
            return f"{old_state} → {new_state}"

    print(f"cli.py:\n  A → B: {state_cli_a} → {state_cli_b}\n  B → C: {state_cli_b} → {state_cli_c}")
    print(f"todo_manager.py:\n  A → B: {state_todo_a} → {state_todo_b}\n  B → C: {state_todo_b} → {state_todo_c}")

    # ---------- Root cause classification ----------
    print("\n=== ROOT-CAUSE CLASSIFICATION ===")
    if state_cli_a == "OLD" and state_cli_b == "OLD":
        print("ROOT CAUSE:\nCoder did not write the corrected files during this execution.")
        print("Evidence:\ncli.py A/B state: OLD/OLD\ncli.py hashes: A={}, B={}".format(cli_a['sha'] if cli_a else 'none', cli_b['sha'] if cli_b else 'none'))
    elif state_cli_a == "OLD" and state_cli_b == "NEW" and state_cli_c == "OLD":
        print("ROOT CAUSE:\nCorrected files were written by Coder but reverted/overwritten before Tester.")
        print("Evidence:\ncli.py A/B/C hashes:\n A: {}\n B: {}\n C: {}".format(cli_a['sha'] if cli_a else 'none', cli_b['sha'] if cli_b else 'none', cli_c['sha'] if cli_c else 'none'))
    elif state_cli_a == "OLD" and state_cli_b == "NEW" and state_cli_c == "NEW":
        if tester_result.payload.get('status') != 'passed':
            print("ROOT CAUSE:\nCoder write persisted until Tester; failure is NOT caused by code reversion.")
            print(f"Tester reason: {tester_result.payload.get('reason')}")
            print(f"Tester stdout: {tester_result.payload.get('stdout')}")
            print(f"Tester stderr: {tester_result.payload.get('stderr')}")
            print(f"todos.json content: {todos_c['content'][:200] if todos_c else 'missing'}")
        else:
            print("UNEXPECTED:\nTester passed after repair; state investigation does not reproduce the previous failure.")
    else:
        print("INCONCLUSIVE:\nUnexpected state transitions.")
        print(f"cli.py: {state_cli_a} -> {state_cli_b} -> {state_cli_c}")
        print(f"todo_manager.py: {state_todo_a} -> {state_todo_b} -> {state_todo_c}")

except Exception:
    traceback.print_exc()
finally:
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)
    print("\n".join(trace))