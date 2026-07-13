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
from project_design.code_executor import CodeExecutor
from agents.tester import Tester
import requests

if not os.getenv("DEEPSEEK_API_KEY"):
    print("PHASE 11 INTEGRATION SKIPPED (no API key)")
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
    executor = CodeExecutor()
    engineer = Engineer(channel, wm, designer)
    coder = Coder(channel, wm, generator)
    tester = Tester(channel, wm, executor)

    try:
        cmd_eng = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=1,
                          payload={"action": "design_structure", "idea": "Simple Calculator"})
        channel.send(cmd_eng)
        assert engineer.step()
        try:
            eng_resp = channel.receive("supervisor", timeout=45)
        except queue.Empty:
            raise AssertionError("Timeout waiting for Engineer response")
        assert eng_resp.payload["status"] == "success"
        structure = eng_resp.payload["structure"]
        assert isinstance(structure, dict)
        phases = structure["phases"]
        assert isinstance(phases, list) and len(phases) > 0
        modules = phases[0].get("modules", [])
        assert isinstance(modules, list) and len(modules) > 0
        mod_info = modules[0]

        cmd_coder = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=1,
                            payload={"filename": mod_info.get("filename"),
                                     "description": mod_info.get("description", ""),
                                     "dependencies": mod_info.get("dependencies", []),
                                     "purpose": mod_info.get("purpose", "")})
        channel.send(cmd_coder)
        assert coder.step()
        try:
            code_resp = channel.receive("supervisor", timeout=45)
        except queue.Empty:
            raise AssertionError("Timeout waiting for Coder response")
        assert code_resp.payload["status"] == "success"
        filepath = code_resp.payload["filepath"]
        assert os.path.exists(filepath)
        with open(filepath, encoding='utf-8') as f:
            code_content = f.read()
        assert len(code_content.strip()) > 0
        compile(code_content, filepath, 'exec')
        assert code_content.strip() != FALLBACK_CODE.strip()

        cmd_tester = Message(sender="supervisor", receiver="tester", msg_type="CommandMsg", phase=1,
                             payload={"filepath": filepath})
        channel.send(cmd_tester)
        assert tester.step()
        try:
            test_resp = channel.receive("supervisor", timeout=45)
        except queue.Empty:
            raise AssertionError("Timeout waiting for Tester response")
        assert test_resp.payload["status"] in ("passed", "failed", "timeout")
        for key in ("return_code", "stdout", "stderr", "execution_time", "filepath"):
            assert key in test_resp.payload

        with open(config.LOG_FILE, encoding='utf-8') as f:
            log_data = json.load(f)
        log_str = json.dumps(log_data)
        assert "Engineer designed structure" in log_str
        assert "Coder wrote file" in log_str
        assert any(x in log_str for x in ["Tester passed", "Tester failed", "Tester timeout"])

        print("PHASE 11 INTEGRATION PASSED")

    except requests.exceptions.RequestException:
        print("PHASE 11 INTEGRATION SKIPPED (network error)")
    except Exception as e:
        print(f"PHASE 11 INTEGRATION FAILED: {e}")