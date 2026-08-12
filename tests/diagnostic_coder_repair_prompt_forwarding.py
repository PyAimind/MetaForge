import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import tempfile
from communication.message import Message
from communication.message_channel import MessageChannel
from workspace.workspace_manager import WorkspaceManager
from agents.coder import Coder

# ----------------------------------------------------------------------
# 1.  Temporary workspace that satisfies isinstance checks
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

    workspace = WorkspaceManager()          # real instance, passes isinstance
    channel   = MessageChannel()            # real instance, passes isinstance

    # ------------------------------------------------------------------
    # 2.  Spy generator that records the module_info it receives
    # ------------------------------------------------------------------
    class SpyGenerator:
        def __init__(self):
            self.last_module_info = None
            self.call_count = 0
        def generate(self, module_info):
            self.last_module_info = module_info
            self.call_count += 1
            return "# generated code"

    spy_generator = SpyGenerator()

    # ------------------------------------------------------------------
    # 3.  Instantiate the REAL Coder with the spy
    # ------------------------------------------------------------------
    coder = Coder(channel, workspace, spy_generator,
                  context_manager=None, knowledge_base=None)

    # ------------------------------------------------------------------
    # 4.  Build the exact repair message the Supervisor would send
    # ------------------------------------------------------------------
    SENTINEL = "FAKE_MULTI_MODULE_PROMPT_FROM_ENGINEER"

    repair_context = {
        "module_name": "cli.py",
        "all_modules": [
            {"module_name": "storage.py", "source_code": "class A: pass", "contract": {}},
            {"module_name": "todo_manager.py", "source_code": "class B: pass", "contract": {}},
            {"module_name": "cli.py", "source_code": "def main(): pass", "contract": {}},
        ],
        "current_code": "def main(): pass",
        "contract": {"exports": []},
        "api_errors": ["some error"],
        "semantic_errors": [],
        "runtime_error": None,
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
            "code": SENTINEL,
            "is_fix": True,
            "repair_context": repair_context,
        },
    )

    # ------------------------------------------------------------------
    # 5.  Execute the real processing path (guarded for exceptions)
    # ------------------------------------------------------------------
    try:
        response = coder.process_command(msg)
    except Exception as exc:
        print(f"process_command raised: {type(exc).__name__}: {exc}")

    # ------------------------------------------------------------------
    # 6.  Diagnostic output
    # ------------------------------------------------------------------
    print("=== Diagnostic Output ===")
    print("Generator called:", spy_generator.call_count > 0)
    print("Call count:", spy_generator.call_count)

    if spy_generator.last_module_info is None:
        print("Generator NOT called – BLOCKED")
    else:
        mi = spy_generator.last_module_info
        print("Keys in module_info:", list(mi.keys()))

        # The exact key the real Coder uses for the repair prompt
        captured = mi.get("repair_prompt", None)

        if captured is None:
            print("Key 'repair_prompt' not found in module_info – BLOCKED")
        else:
            print(f"Captured 'repair_prompt' (first 200 chars):")
            print(captured[:200])

            if captured == SENTINEL:
                print("PASS")
            else:
                print("FAIL")
                print("Expected:", SENTINEL)
                print("Got (first 200):", captured[:200])

finally:
    # clean up temporary workspace
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)