import os
import sys
import json
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import agents.engineer as engineer_module

from workspace.workspace_manager import WorkspaceManager
from communication.message import Message
from communication.message_channel import MessageChannel
from agents.engineer import Engineer
from project_design.repair_context import RepairContext


def find_none(obj, path=""):
    results = []

    if isinstance(obj, dict):
        for k, v in obj.items():
            current = f"{path}[{k!r}]" if path else repr(k)
            if v is None:
                results.append(current)
            else:
                results.extend(find_none(v, current))

    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            current = f"{path}[{i}]"
            if v is None:
                results.append(current)
            else:
                results.extend(find_none(v, current))

    return results


# Hook generate_prompt
original_generate_prompt = engineer_module.generate_prompt


def debug_generate_prompt(module_info):
    print("\n==============================")
    print("GENERATE_PROMPT INPUT DEBUG")
    print("==============================")

    print(json.dumps(module_info, indent=2, default=str))

    print("\n--- TYPES ---")
    for key, value in module_info.items():
        print(f"{key}: {type(value)}")

    print("\n--- NONE LOCATIONS ---")
    none_locations = find_none(module_info)

    if none_locations:
        for item in none_locations:
            print(item)
    else:
        print("No None values")

    print("==============================\n")

    return original_generate_prompt(module_info)


engineer_module.generate_prompt = debug_generate_prompt


class DummyDesigner:
    def design(self, idea):
        return {}


with tempfile.TemporaryDirectory() as tmp:

    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.OUTPUT_DIR = os.path.join(tmp, "output")

    config.PHASE_FILE = os.path.join(
        config.WORKSPACE_DIR,
        "current_phase.json"
    )
    config.LOG_FILE = os.path.join(
        config.WORKSPACE_DIR,
        "build_log.json"
    )
    config.STRUCTURE_FILE = os.path.join(
        config.WORKSPACE_DIR,
        "project_structure.json"
    )
    config.TEST_RESULTS_FILE = os.path.join(
        config.WORKSPACE_DIR,
        "test_results.json"
    )

    os.makedirs(config.WORKSPACE_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)


    repair_ctx = RepairContext(
        "greeter.py",
        "greeter.py"
    )

    repair_ctx.current_code = (
        "def greet(name):\n"
        "    return f\"Hello, {name}!\"\n"
    )

    repair_ctx.contract = {
        "module": "greeter.py",
        "exports": [
            {
                "name": "greet",
                "kind": "function",
                "parameters": [
                    {
                        "name": "name",
                        "type": "str"
                    }
                ],
                "returns": "str"
            }
        ],
        "required_imports": [],
    }

    repair_ctx.api_errors = [
        "Missing return type annotation"
    ]

    repair_ctx.semantic_errors = []
    repair_ctx.runtime_error = None
    repair_ctx.debugger_analysis = None
    repair_ctx.previous_attempts = 1


    wm = WorkspaceManager()
    channel = MessageChannel()

    engineer = Engineer(
        channel,
        wm,
        DummyDesigner(),
        knowledge_base=None
    )


    # همان چیزی که Supervisor باید به Engineer بدهد
    payload = {
        "action": "generate_single_prompt",
        "is_fix": True,

        "module_info": {
            "filename": "greeter.py",
            "description": "",
            "dependencies": [],
            "purpose": "",
            "exports": repair_ctx.contract["exports"],
            "required_imports": []
        },

        "repair_context": vars(repair_ctx)
    }


    print("Sending real Engineer message...")

    channel.send(
        Message(
            sender="supervisor",
            receiver="engineer",
            msg_type="CommandMsg",
            phase=1,
            payload=payload
        )
    )


    try:
        engineer.step()

        print("\nENGINEER FINISHED WITHOUT CRASH")

        response = channel.receive(
            "supervisor",
            timeout=1
        )

        if response:
            print("\nENGINEER RESPONSE:")
            print(
                json.dumps(
                    response.payload,
                    indent=2,
                    default=str
                )
            )

    except Exception:
        print("\nENGINEER CRASHED:")
        traceback.print_exc()

