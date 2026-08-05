import os
import sys
import time
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
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
try:
    from agents.semantic_analyzer import SemanticAnalyzer
    _HAS_SEMANTIC = True
except Exception:
    _HAS_SEMANTIC = False
    print("WARNING: SemanticAnalyzer not available. Cross-module checks disabled.")
import config

LOOP_DELAY = 0.01

def build_dependencies():
    provider = LLMProvider()
    designer = StructureDesignerLLM(provider)
    generator = CodeGeneratorLLM(provider)
    executor = CodeExecutor()
    ctx = ContextManager(config.OUTPUT_DIR)
    kb = KnowledgeBase()
    debugger = Debugger(knowledge_base=kb)
    return designer, generator, executor, ctx, kb, debugger

os.makedirs(config.WORKSPACE_DIR, exist_ok=True)
os.makedirs(config.OUTPUT_DIR, exist_ok=True)

try:
    wm = WorkspaceManager()
    channel = MessageChannel()
    designer, generator, executor, ctx, kb, debugger = build_dependencies()
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
    if _HAS_SEMANTIC:
        try:
            semantic_analyzer = SemanticAnalyzer()
        except Exception as e:
            print(f"WARNING: Could not instantiate SemanticAnalyzer: {e}")

    supervisor = Supervisor(channel, wm, debugger,
                            api_inspector=api_inspector,
                            semantic_analyzer=semantic_analyzer)

    agents = [engineer, coder, tester]

    project_idea = input("Enter your project idea: ").strip()
    if not project_idea:
        print("Project idea cannot be empty.")
        sys.exit(1)

    try:
        supervisor.set_idea(project_idea)
        while True:
            keep_going = supervisor.step()
            for agent in agents:
                agent.step()
            if not keep_going and supervisor.status in ("completed", "error"):
                break
            time.sleep(LOOP_DELAY)
    except KeyboardInterrupt:
        print("Interrupted by user.")
        sys.exit(0)

    if supervisor.status == "completed":
        print("MetaForge project completed.")
    else:
        print("MetaForge project failed with error.")
    print(f"Output: {config.OUTPUT_DIR}")

except Exception as e:
    print(f"Startup error: {e}")
    sys.exit(1)