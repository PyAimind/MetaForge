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
from llm_provider import LLMProvider
from project_design.structure_designer_llm import StructureDesignerLLM
from agents.engineer import Engineer
from project_design.code_generator_llm import CodeGeneratorLLM, FALLBACK_CODE
from agents.coder import Coder
import requests

if not os.getenv("DEEPSEEK_API_KEY"):
    print("PHASE 10 INTEGRATION SKIPPED (no API key)")
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
    generator = CodeGeneratorLLM(provider)
    engineer = Engineer(channel, wm, designer)
    coder = Coder(channel, wm, generator)

    try:
        cmd_eng = Message(
            sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=1,
            payload={"action": "design_structure", "idea": "Simple Calculator"}
        )
        channel.send(cmd_eng)
        assert engineer.step()

        try:
            eng_resp = channel.receive("supervisor", timeout=30)
        except queue.Empty:
            raise AssertionError("Timeout waiting for Engineer response")

        assert eng_resp.payload.get("status") == "success"
        structure = eng_resp.payload.get("structure")
        assert isinstance(structure, dict)

        phases = structure.get("phases", [])
        assert isinstance(phases, list) and len(phases) > 0

        modules = phases[0].get("modules", [])
        assert isinstance(modules, list) and len(modules) > 0

        module_info = modules[0]
        assert isinstance(module_info, dict)

        cmd_coder = Message(
            sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=1,
            payload={
                "filename": module_info.get("filename"),
                "description": module_info.get("description", ""),
                "dependencies": module_info.get("dependencies", []),
                "purpose": module_info.get("purpose", "")
            }
        )
        print("MODULE_INFO:", module_info)
        channel.send(cmd_coder)
        assert coder.step()

        try:
            coder_resp = channel.receive("supervisor", timeout=30)
        except queue.Empty:
            raise AssertionError("Timeout waiting for Coder response")

        assert coder_resp.payload.get("status") == "success"
        filepath = coder_resp.payload.get("filepath")
        assert filepath and os.path.exists(filepath)

        with open(filepath, encoding='utf-8') as f:
            code = f.read()

        assert len(code.strip()) > 0
        assert code.strip() != FALLBACK_CODE.strip()
        compile(code, filepath, 'exec')

        with open(config.LOG_FILE, encoding='utf-8') as f:
            log_data = json.load(f)
        log_str = json.dumps(log_data)
        assert "Engineer designed structure" in log_str
        assert "Coder wrote file" in log_str

        print("PHASE 10 INTEGRATION PASSED")

    except requests.exceptions.RequestException:
        print("PHASE 10 INTEGRATION SKIPPED (network error)")
    except Exception as e:
        print(f"PHASE 10 INTEGRATION FAILED: {e}")