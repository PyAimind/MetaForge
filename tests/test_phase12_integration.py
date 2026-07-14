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
from project_design.code_generator_llm import CodeGeneratorLLM, FALLBACK_CODE
from project_design.code_executor import CodeExecutor
from agents.supervisor import Supervisor
from agents.engineer import Engineer
from agents.coder import Coder
from agents.tester import Tester
from diagnostics.diagnose import run_diagnostics
import requests

def check(step, description, condition, fail_reason):
    if condition:
        print(f"[STEP {step}] {description} ✅")
        return True
    else:
        print(f"[STEP {step}] {description} ❌ REASON: {fail_reason}")
        report = run_diagnostics(step, channel, wm, supervisor, agents)
        report.print_report()
        sys.exit(1)

if not os.getenv("DEEPSEEK_API_KEY"):
    print("PHASE 12 INTEGRATION SKIPPED (no API key)")
    sys.exit(0)

with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")

    try:
        wm = WorkspaceManager()
        channel = MessageChannel()
        provider = LLMProvider()
        designer = StructureDesignerLLM(provider)
        generator = CodeGeneratorLLM(provider)
        executor = CodeExecutor()
        supervisor = Supervisor(channel, wm)
        engineer = Engineer(channel, wm, designer)
        coder = Coder(channel, wm, generator)
        tester = Tester(channel, wm, executor)
        agents = [engineer, coder, tester]

        print("[SYSTEM] All components initialized.")

        supervisor.set_idea("Simple Calculator")
        supervisor.step()
        check(2, "Supervisor sends design_structure to Engineer",
              supervisor.status == "waiting_for_engineer",
              f"Expected waiting_for_engineer but got {supervisor.status}")

        engineer.step()
        supervisor.step()
        supervisor.step()
        engineer.step()
        supervisor.step()
        check(3, "Engineer returns structure and prompts, Supervisor sends first module to Coder",
              supervisor.status == "waiting_for_coder",
              f"Expected waiting_for_coder but got {supervisor.status}")

        coder.step()
        supervisor.step()

        structure = wm.read_structure()
        first_module_filename = structure["phases"][0]["modules"][0]["filename"]
        filepath = os.path.join(config.OUTPUT_DIR, first_module_filename)

        file_ok = os.path.exists(filepath)
        content = ""
        if file_ok:
            with open(filepath, encoding='utf-8') as f:
                content = f.read()
        valid_python = False
        if file_ok and content.strip():
            try:
                compile(content, filepath, 'exec')
                valid_python = True
            except Exception:
                pass
        check(4, "Coder creates valid Python file (no fallback)",
              file_ok and valid_python and content.strip() != FALLBACK_CODE.strip(),
              "File missing, invalid Python, or fallback code")

        tester.step()
        test_results = []
        try:
            with open(config.TEST_RESULTS_FILE, encoding='utf-8') as f:
                test_results = json.load(f)
        except Exception:
            pass
        tester_passed = any(
            obj.get("status") == "passed"
            for obj in test_results
        )
        check(5, "Tester passes the generated code",
              tester_passed,
              "No passed test result found")

        iterations = 0
        while supervisor.status not in ("completed", "error") and iterations < 50:
            supervisor.step()
            for agent in agents:
                agent.step()
            iterations += 1

        all_files_ok = os.path.exists(filepath) and os.path.getsize(filepath) > 0
        check(6, "Project completed successfully",
              supervisor.status == "completed" and all_files_ok,
              f"Project did not reach completed state (current status: {supervisor.status})")

        with open(config.LOG_FILE, encoding='utf-8') as f:
            log_text = f.read()
        check(7, "Workspace logs are valid and contain expected entries",
              "Engineer designed structure" in log_text and "Coder wrote file" in log_text and "Tester passed" in log_text,
              "Workspace validation failed")

        print("PHASE 12 INTEGRATION PASSED")

    except requests.exceptions.RequestException:
        print("PHASE 12 INTEGRATION SKIPPED (network error)")
    except Exception as e:
        print(f"PHASE 12 INTEGRATION FAILED: {e}")