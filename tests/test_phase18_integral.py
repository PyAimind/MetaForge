import os
import sys
import json
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from workspace.workspace_manager import WorkspaceManager
from communication.message import Message
from communication.message_channel import MessageChannel
from agents.supervisor import Supervisor

with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    os.makedirs(config.WORKSPACE_DIR, exist_ok=True)

    structure = {
        "project_name": "Test",
        "description": "A test project",
        "phases": [
            {
                "phase_number": 1,
                "name": "Core",
                "modules": [
                    {
                        "filename": "greeter.py",
                        "description": "Greeting module",
                        "dependencies": [],
                        "purpose": "greet",
                        "exports": [
                            {
                                "name": "greet",
                                "kind": "function",
                                "parameters": [{"name": "name", "type": "str"}],
                                "returns": "str"
                            }
                        ],
                        "required_imports": []
                    }
                ]
            }
        ]
    }

    wm = WorkspaceManager()
    wm.write_structure(structure)
    channel = MessageChannel()
    supervisor = Supervisor(channel, wm)
    supervisor.status = "waiting_for_engineer"
    supervisor.modules = []
    msg = Message(
        sender="engineer",
        receiver="supervisor",
        msg_type="ResultMsg",
        phase=1,
        payload={"status": "success", "structure": structure}
    )
    channel.send(msg)
    supervisor.step()
    contract_path = os.path.join(config.WORKSPACE_DIR, "contracts.json")
    assert os.path.isfile(contract_path)
    with open(contract_path, 'r', encoding='utf-8') as f:
        contracts = json.load(f)
    assert "greeter.py" in contracts
    assert contracts["greeter.py"]["generated"] == False
    assert contracts["greeter.py"]["validated"] == False
    print("PHASE 18.4.1 PASSED")