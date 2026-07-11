import sys
import os
import json
import tempfile
import queue
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from workspace.workspace_manager import WorkspaceManager
from communication.message import Message
from communication.message_channel import MessageChannel
from agents.engineer import Engineer
from llm_provider import LLMProvider
from project_design.structure_designer_llm import StructureDesignerLLM
import requests

if not os.getenv("DEEPSEEK_API_KEY"):
    print("PHASE 9.4 SKIPPED (no API key)")
    sys.exit(0)

with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")
    wm = WorkspaceManager()
    channel = MessageChannel()
    provider = LLMProvider()
    designer = StructureDesignerLLM(provider)
    engineer = Engineer(channel, wm, designer)
    try:
        msg = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=9,
                      payload={"action": "design_structure", "idea": "Simple Calculator"})
        channel.send(msg)
        assert engineer.step()
        try:
            resp = channel.receive("supervisor", timeout=30)
        except queue.Empty:
            raise AssertionError("No response received from Engineer (timeout)")
        assert resp.payload["status"] == "success"
        structure = resp.payload["structure"]
        assert isinstance(structure, dict)
        assert "project_name" in structure and "description" in structure and "phases" in structure
        phases = structure["phases"]
        assert isinstance(phases, list) and len(phases) >= 1
        first_phase = phases[0]
        assert "modules" in first_phase
        modules = first_phase["modules"]
        assert isinstance(modules, list) and len(modules) >= 1
        mod = modules[0]
        for key in ("filename", "description", "dependencies", "purpose"):
            assert key in mod
        assert wm.read_structure() == structure
        assert not engineer.step()
        with open(config.LOG_FILE, encoding='utf-8') as f:
            log_data = json.load(f)
        assert "Engineer designed structure" in json.dumps(log_data)
        msg_invalid = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=9,
                              payload={"action": "nonexistent"})
        channel.send(msg_invalid)
        assert engineer.step()
        resp_err = channel.receive("supervisor", timeout=5)
        assert resp_err.payload["status"] == "error"
        assert "Unknown action" in resp_err.payload["reason"]
        assert resp_err.sender == "engineer"
        assert resp_err.receiver == "supervisor"
        assert resp_err.msg_type == "ResultMsg"
        assert not engineer.step()
        print("PHASE 9.4 PASSED")
    except requests.exceptions.RequestException:
        print("PHASE 9.4 SKIPPED (network error)")
    except Exception as e:
        print(f"PHASE 9.4 FAILED: {e}")