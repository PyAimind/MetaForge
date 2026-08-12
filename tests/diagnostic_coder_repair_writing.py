# === CONSOLE OUTPUT ===
# Temp output dir: /tmp/.../output
# Files found: ['cli.py', 'todo_manager.py']
# cli.py content: fixed cli code
# todo_manager.py content: fixed manager code
# PASS: CODER_WROTE_EXPECTED_FILES

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
from agents.coder import Coder

# ----------------------------------------------------------------------
# Spy Generator that returns valid multi-module JSON
# ----------------------------------------------------------------------
class SpyGenerator:
    def __init__(self):
        self.last_module_info = None
        self.call_count = 0

    def generate(self, module_info):
        self.last_module_info = module_info
        self.call_count += 1
        return json.dumps({
            "cli.py": "fixed cli code",
            "todo_manager.py": "fixed manager code"
        })

# ----------------------------------------------------------------------
# Temporary workspace
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

    # Create contracts.json so Coder's validation expects these modules
    contracts = {
        "cli.py": {
            "module": "cli.py",
            "exports": [],
            "dependencies": ["todo_manager.py"],
            "generated": True,
            "validated": False
        },
        "todo_manager.py": {
            "module": "todo_manager.py",
            "exports": [],
            "dependencies": [],
            "generated": True,
            "validated": False
        }
    }
    with open(os.path.join(config.WORKSPACE_DIR, 'contracts.json'), 'w', encoding='utf-8') as f:
        json.dump(contracts, f, indent=2)

    workspace = WorkspaceManager()
    channel = MessageChannel()
    spy_generator = SpyGenerator()

    coder = Coder(channel, workspace, spy_generator,
                  context_manager=None, knowledge_base=None)

    # ------------------------------------------------------------------
    # Build repair message
    # ------------------------------------------------------------------
    repair_context = {
        "module_name": "cli.py",
        "filepath": os.path.join(config.OUTPUT_DIR, "cli.py"),
        "all_modules": [
            {"module_name": "cli.py", "source_code": "original cli code", "contract": {}},
            {"module_name": "todo_manager.py", "source_code": "original manager code", "contract": {}},
        ],
        "current_code": "original cli code",
        "contract": {"exports": []},
        "api_errors": ["some error"],
        "semantic_errors": [],
        "runtime_error": "list did not contain 'Test todo'",
        "debugger_analysis": None,
        "previous_attempts": 1,
    }

    msg = Message(
        sender="supervisor",
        receiver="coder",
        msg_type="CommandMsg",
        phase=1,
        payload={
            "action": "code",
            "filename": "cli.py",
            "description": "CLI module",
            "dependencies": ["todo_manager.py"],
            "purpose": "entry",
            "code": "DUMMY_REPAIR_PROMPT",
            "is_fix": True,
            "repair_context": repair_context,
        },
    )

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------
    try:
        response = coder.process_command(msg)
    except Exception as e:
        print(f"Exception: {type(e).__name__}: {e}")
        response = None

    # ------------------------------------------------------------------
    # Inspect output directory
    # ------------------------------------------------------------------
    files_found = sorted(os.listdir(config.OUTPUT_DIR)) if os.path.isdir(config.OUTPUT_DIR) else []
    file_contents = {}
    for fname in files_found:
        fpath = os.path.join(config.OUTPUT_DIR, fname)
        if os.path.isfile(fpath):
            with open(fpath, 'r', encoding='utf-8') as f:
                file_contents[fname] = f.read()

    expected = {"cli.py": "fixed cli code", "todo_manager.py": "fixed manager code"}

    print("Temp output dir:", config.OUTPUT_DIR)
    print("Files found:", files_found)
    for fname in sorted(file_contents):
        print(f"{fname} content: {file_contents[fname]}")

    all_ok = (
        set(file_contents.keys()) == set(expected.keys())
        and all(file_contents.get(k) == v for k, v in expected.items())
    )

    if all_ok:
        print("PASS: CODER_WROTE_EXPECTED_FILES")
    else:
        print("FAIL: CODER_WROTE_UNEXPECTED_FILES")
        if not files_found:
            print("No files were written.")
        else:
            for k, v in expected.items():
                actual = file_contents.get(k)
                if actual is None:
                    print(f"Missing file: {k}")
                elif actual != v:
                    print(f"Content mismatch in {k}: expected {v!r}, got {actual!r}")
        if response is not None:
            print("Response status:", response.payload.get("status"))
            print("Response reason:", response.payload.get("reason", ""))

finally:
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)