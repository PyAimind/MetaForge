import os, sys, time, tempfile
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from workspace.workspace_manager import WorkspaceManager
from communication.message_channel import MessageChannel
from llm_provider import LLMProvider
from project_design.structure_designer_llm import StructureDesignerLLM
from project_design.code_generator_llm import CodeGeneratorLLM
from project_design.code_executor import CodeExecutor
from project_design.context_manager import ContextManager
from memory.knowledge_base import KnowledgeBase
from agents.supervisor import Supervisor
from agents.engineer import Engineer
from agents.coder import Coder
from agents.tester import Tester
from agents.debugger import Debugger

with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")

    print("[SMOKE TEST] Initializing v3.0 system...")
    wm = WorkspaceManager()
    channel = MessageChannel()
    provider = LLMProvider()
    designer = StructureDesignerLLM(provider)
    generator = CodeGeneratorLLM(provider)
    executor = CodeExecutor()
    ctx = ContextManager(config.OUTPUT_DIR)
    kb = KnowledgeBase(os.path.join(tmp, "kb.json"))
    debugger = Debugger(knowledge_base=kb)

    supervisor = Supervisor(channel, wm, debugger=debugger)
    engineer = Engineer(channel, wm, designer, knowledge_base=kb)
    coder = Coder(channel, wm, generator, ctx, knowledge_base=kb)
    tester = Tester(channel, wm, executor)
    agents = [engineer, coder, tester]

    print("[SMOKE TEST] Building project: Simple Calculator...")
    supervisor.set_idea("Simple Calculator")
    
    step_count = 0
    while supervisor.status not in ("completed", "error") and step_count < 50:
        supervisor.step()
        for agent in agents:
            agent.step()
        step_count += 1
        time.sleep(0.1)

    print(f"\n[SMOKE TEST] Final Status: {supervisor.status}")
    print(f"[SMOKE TEST] LLM Requests Used: {provider.get_usage()['total_requests']}")
    print(f"[SMOKE TEST] Output files in {config.OUTPUT_DIR}:")
    if os.path.exists(config.OUTPUT_DIR):
        for f in os.listdir(config.OUTPUT_DIR):
            print(f"  - {f}")
    
    if supervisor.status == "completed":
        print("\n[SMOKE TEST] ✅ MetaForge v3.0 is healthy and ready for release!")
    else:
        print(f"\n[SMOKE TEST] ❌ Project failed with status: {supervisor.status}")