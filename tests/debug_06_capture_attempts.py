import os
import sys
import json
import time
import tempfile
import hashlib
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

def build_dependencies():
    provider = LLMProvider()
    designer = StructureDesignerLLM(provider)
    generator = CodeGeneratorLLM(provider)
    executor = CodeExecutor()
    ctx = ContextManager(config.OUTPUT_DIR)
    kb = KnowledgeBase()
    debugger = Debugger(knowledge_base=kb)
    return designer, generator, executor, ctx, kb, debugger

loop_error = None

class GenerationTracker:
    def __init__(self):
        self._hashes = {}
        self._counters = {}
        self.records = []

    def scan_and_save(self, output_dir, debug_dir):
        if not os.path.isdir(output_dir):
            return
        for fname in sorted(os.listdir(output_dir)):
            fpath = os.path.join(output_dir, fname)
            if not os.path.isfile(fpath):
                continue
            with open(fpath, "rb") as f:
                content = f.read()
            digest = hashlib.sha256(content).hexdigest()
            if self._hashes.get(fname) == digest:
                continue
            self._counters[fname] = self._counters.get(fname, 0) + 1
            count = self._counters[fname]
            dst = os.path.join(debug_dir, f"generation_{count}_{fname}")
            with open(dst, "wb") as f:
                f.write(content)
            self._hashes[fname] = digest
            self.records.append({
                "filename": fname,
                "generation": count,
                "sha256": digest,
                "size": len(content)
            })

with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")
    os.makedirs(config.WORKSPACE_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

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

    debug_dir = "debug_output"
    os.makedirs(debug_dir, exist_ok=True)
    tracker = GenerationTracker()

    iterations = 0
    try:
        while supervisor.status not in ("completed", "error") and iterations < MAX_ITERATIONS:
            supervisor.step()
            for agent in agents:
                agent.step()
                tracker.scan_and_save(config.OUTPUT_DIR, debug_dir)
            if supervisor.status in ("completed", "error"):
                break
            iterations += 1
            time.sleep(LOOP_DELAY)
    except Exception as e:
        loop_error = traceback.format_exc()

    final_status = supervisor.status
    fix_attempts = supervisor.fix_attempts

    with open(os.path.join(debug_dir, "debug_06_hashes.json"), "w") as f:
        json.dump(tracker.records, f, indent=2)

    print(f"Final supervisor status: {final_status}")
    print(f"Fix attempts per module: {fix_attempts}")
    print("Captured files:")
    for rec in tracker.records:
        print(f"  generation_{rec['generation']}_{rec['filename']} ({rec['size']} bytes, sha256={rec['sha256'][:16]}...)")
    if loop_error:
        print("Exception occurred:")
        print(loop_error)