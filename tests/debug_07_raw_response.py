import os
import sys
import json
import time
import tempfile
import traceback
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT_DIR, '.env'))

sys.path.insert(0, ROOT_DIR)
import config
from workspace.workspace_manager import WorkspaceManager
from communication.message_channel import MessageChannel
from llm_provider import LLMProvider
from project_design.structure_designer_llm import StructureDesignerLLM
from project_design.code_generator_llm import CodeGeneratorLLM
from project_design.code_executor import CodeExecutor
from project_design.context_manager import ContextManager
from memory.knowledge_base import KnowledgeBase
from agents.debugger import Debugger
from agents.supervisor import Supervisor
from agents.engineer import Engineer
from agents.coder import Coder
from agents.tester import Tester

LOOP_DELAY = 0.01
MAX_ITERATIONS = 200

def build_dependencies(provider=None):
    if provider is None:
        provider = LLMProvider()
    designer = StructureDesignerLLM(provider)
    generator = CodeGeneratorLLM(provider)
    executor = CodeExecutor()
    ctx = ContextManager(config.OUTPUT_DIR)
    kb = KnowledgeBase()
    debugger = Debugger(knowledge_base=kb)
    return designer, generator, executor, ctx, kb, debugger

raw_attempt_counters = {}
raw_files = []

def make_raw_capture_wrapper(original_generate):
    def wrapper(messages, model=None, max_tokens=2000, temperature=0.7):
        result = original_generate(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature
        )
        for msg in messages:
            if isinstance(msg, dict) and "greeter.py" in msg.get("content", ""):
                basename = "greeter.py"
                if basename not in raw_attempt_counters:
                    raw_attempt_counters[basename] = 0
                raw_attempt_counters[basename] += 1
                attempt = raw_attempt_counters[basename]
                os.makedirs("debug_output", exist_ok=True)
                save_path = os.path.join("debug_output", f"raw_attempt_{attempt}_{basename}.txt")
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(result)
                raw_files.append(save_path)
                break
        return result
    return wrapper

loop_error = None

with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")
    os.makedirs(config.WORKSPACE_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    provider = LLMProvider()
    provider.generate = make_raw_capture_wrapper(provider.generate)

    wm = WorkspaceManager()
    channel = MessageChannel()
    designer, generator, executor, ctx, kb, debugger = build_dependencies(provider)
    engineer = Engineer(channel, wm, designer, knowledge_base=kb)
    coder = Coder(channel, wm, generator, ctx, knowledge_base=kb)
    tester = Tester(channel, wm, executor)

    api_inspector = None
    try:
        from agents.api_inspector import APIInspector
        api_inspector = APIInspector()
    except Exception:
        print("WARNING: APIInspector not available. API checks disabled.")

    semantic_analyzer = None
    try:
        from agents.semantic_analyzer import SemanticAnalyzer
        semantic_analyzer = SemanticAnalyzer()
    except Exception:
        print("WARNING: SemanticAnalyzer not available. Cross-module checks disabled.")

    supervisor = Supervisor(channel, wm, debugger,
                            api_inspector=api_inspector,
                            semantic_analyzer=semantic_analyzer)

    agents = [engineer, coder, tester]

    supervisor.set_idea("A simple greeting app")

    iterations = 0
    try:
        while supervisor.status not in ("completed", "error") and iterations < MAX_ITERATIONS:
            supervisor.step()
            for agent in agents:
                agent.step()
            if supervisor.status in ("completed", "error"):
                break
            iterations += 1
            time.sleep(LOOP_DELAY)
    except Exception as e:
        loop_error = traceback.format_exc()

    final_status = supervisor.status
    fix_attempts = supervisor.fix_attempts

    print(f"Final supervisor status: {final_status}")
    print(f"Fix attempts per module: {fix_attempts}")
    print("Captured raw LLM responses:")
    for f in raw_files:
        print(f"  {f}")
    if loop_error:
        print("Exception occurred:")
        print(loop_error)