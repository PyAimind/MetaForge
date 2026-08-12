# === RUN OUTPUT ===
# First 100 chars of prompt: MULTI‑MODULE RUNTIME FAILURE REPAIR\n\nThe product acceptance test failed. The root cause may invo...
# Target string found: True
# PASS: Engineer multi-module prompt includes CLI output contract instruction

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
from agents.engineer import Engineer

# ----------------------------------------------------------------------
# Dummy designer with a minimal 'design' callable
# ----------------------------------------------------------------------
class DummyDesigner:
    def design(self, idea):
        return {}

# ----------------------------------------------------------------------
# Temporary workspace (needed only for Engineer constructor dependencies)
# ----------------------------------------------------------------------
tmpdir = tempfile.mkdtemp()
try:
    import config
    ws = os.path.join(tmpdir, 'workspace')
    out = os.path.join(tmpdir, 'output')
    config.WORKSPACE_DIR = ws
    config.OUTPUT_DIR = out
    os.makedirs(ws, exist_ok=True)
    os.makedirs(out, exist_ok=True)

    # Instantiate real WorkspaceManager and MessageChannel (required by Engineer)
    wm = WorkspaceManager()
    channel = MessageChannel()
    engineer = Engineer(channel, wm, DummyDesigner(), knowledge_base=None)

    # Build a minimal multi-module repair message
    repair_context = {
        "module_name": "cli.py",
        "filepath": os.path.join(out, "cli.py"),
        "all_modules": [
            {"module_name": "cli.py", "source_code": "print('cli')", "contract": {}},
            {"module_name": "todo_manager.py", "source_code": "print('todo')", "contract": {}},
        ],
        "current_code": "print('cli')",
        "contract": {"exports": []},
        "api_errors": [],
        "semantic_errors": [],
        "runtime_error": "list did not contain 'Test todo'",
        "debugger_analysis": None,
        "previous_attempts": 1,
    }

    msg = Message(
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

    response = engineer.process_command(msg)
    prompt = response.payload.get("prompts", {}).get("cli.py", "")

    print(f"First 100 chars of prompt: {prompt[:100]}")
    target = "2.5. If `cli.py` is among the modified files"
    found = target in prompt
    print(f"Target string found: {found}")

    if found:
        print("PASS: Engineer multi-module prompt includes CLI output contract instruction")
    else:
        print("FAIL: Required instruction not found in multi-module repair prompt")

finally:
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)