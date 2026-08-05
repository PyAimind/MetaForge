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

class FlightRecorder:
    def __init__(self, log_dir):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.log_file = os.path.join(log_dir, "full_trace.log")
        self.buffer = []
        self.messages = []

    def log(self, message):
        print(message)
        self.buffer.append(message)

    def log_message(self, msg):
        try:
            self.messages.append({
                "sender": getattr(msg, "sender", None),
                "receiver": getattr(msg, "receiver", None),
                "type": getattr(msg, "msg_type", None),
                "payload": getattr(msg, "payload", None)
            })
        except Exception as e:
            self.log(f"[MESSAGE_LOG_ERROR] {e}")

    def save(self):
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write("\n".join(self.buffer))
        with open(os.path.join(self.log_dir, "messages_trace.json"), "w", encoding="utf-8") as f:
            json.dump(self.messages, f, indent=2)

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

llm_call_id = [0]
generation_id = [0]

file_hashes = {}
file_counters = {}
file_snap_dir = None

def init_file_observer(snap_dir):
    global file_snap_dir
    file_snap_dir = snap_dir
    os.makedirs(snap_dir, exist_ok=True)

def observe_files(output_dir):
    global file_hashes, file_counters, file_snap_dir
    if not os.path.isdir(output_dir):
        return
    for fname in sorted(os.listdir(output_dir)):
        fpath = os.path.join(output_dir, fname)
        if not os.path.isfile(fpath):
            continue
        with open(fpath, "rb") as f:
            content = f.read()
        digest = hashlib.sha256(content).hexdigest()
        if file_hashes.get(fname) == digest:
            continue
        file_counters[fname] = file_counters.get(fname, 0) + 1
        count = file_counters[fname]
        save_path = os.path.join(file_snap_dir, f"snapshot_{count}_{fname}")
        with open(save_path, "wb") as f:
            f.write(content)
        file_hashes[fname] = digest

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

    debug_dir = "debug_output"
    os.makedirs(debug_dir, exist_ok=True)
    recorder = FlightRecorder(debug_dir)
    prompt_dir = os.path.join(debug_dir, "prompts")
    raw_dir = os.path.join(debug_dir, "responses")
    snapshot_dir = os.path.join(debug_dir, "file_snapshots")
    os.makedirs(prompt_dir, exist_ok=True)
    os.makedirs(raw_dir, exist_ok=True)
    init_file_observer(snapshot_dir)

    provider = LLMProvider()
    original_llm_generate = provider.generate
    def llm_wrapper(*args, **kwargs):
        idx = llm_call_id[0] + 1
        llm_call_id[0] = idx
        messages = args[0] if args else kwargs.get("messages", [])
        prefix = "coder"
        for msg in messages:
            if isinstance(msg, dict) and "project_name" in msg.get("content", ""):
                prefix = "engineer"
                break
        prompt_path = os.path.join(prompt_dir, f"{prefix}_prompt_{idx}.txt")
        with open(prompt_path, "w", encoding="utf-8") as f:
            for i, msg in enumerate(messages):
                f.write(f"--- message {i} ({msg.get('role','?')}) ---\n")
                f.write(msg.get('content','') + "\n\n")
        result = original_llm_generate(*args, **kwargs)
        raw_path = os.path.join(raw_dir, f"llm_raw_{idx}.txt")
        with open(raw_path, "w", encoding="utf-8") as f:
            f.write(result)
        recorder.log(f"[LLM_CALL] id={idx} type={prefix}")
        return result
    provider.generate = llm_wrapper

    wm = WorkspaceManager()
    channel = MessageChannel()

    original_channel_send = channel.send
    def channel_send_wrapper(message):
        try:
            recorder.log_message(message)
        except Exception as e:
            recorder.log(f"[MESSAGE_LOG_ERROR] {e}")
        return original_channel_send(message)
    channel.send = channel_send_wrapper

    designer, generator, executor, ctx, kb, debugger = build_dependencies(provider)

    original_cg_generate = generator.generate
    def cg_wrapper(*args, **kwargs):
        gen_id = generation_id[0] + 1
        generation_id[0] = gen_id
        module_info = args[0] if args else kwargs.get("module_info", {})
        module_info_path = os.path.join(debug_dir, f"module_info_{gen_id}.json")
        with open(module_info_path, "w", encoding="utf-8") as f:
            json.dump(module_info, f, indent=2)
        result = original_cg_generate(*args, **kwargs)
        processed_path = os.path.join(raw_dir, f"llm_processed_{gen_id}.py")
        with open(processed_path, "w", encoding="utf-8") as f:
            f.write(result)
        recorder.log(f"[CG_GEN] id={gen_id} module={module_info.get('filename','?')}")
        return result
    generator.generate = cg_wrapper

    engineer = Engineer(channel, wm, designer, knowledge_base=kb)
    coder = Coder(channel, wm, generator, ctx, knowledge_base=kb)
    tester = Tester(channel, wm, executor)

    original_tester_process = tester.process_command
    def tester_wrapper(*args, **kwargs):
        result = original_tester_process(*args, **kwargs)
        recorder.log(f"[TESTER] status={result.payload.get('status')} file={result.payload.get('filepath','')}")
        return result
    tester.process_command = tester_wrapper

    original_debugger_analyze = debugger.analyze_error
    def debugger_wrapper(*args, **kwargs):
        diagnosis = original_debugger_analyze(*args, **kwargs)
        recorder.log(f"[DEBUGGER] diagnosis={diagnosis.get('diagnosis','?')} confidence={diagnosis.get('confidence',0)}")
        return diagnosis
    debugger.analyze_error = debugger_wrapper

    api_inspector = None
    try:
        from agents.api_inspector import APIInspector
        api_inspector = APIInspector()
    except Exception:
        recorder.log("WARNING: APIInspector not available. API checks disabled.")

    semantic_analyzer = None
    try:
        from agents.semantic_analyzer import SemanticAnalyzer
        semantic_analyzer = SemanticAnalyzer()
    except Exception:
        recorder.log("WARNING: SemanticAnalyzer not available. Cross-module checks disabled.")

    supervisor = Supervisor(channel, wm, debugger,
                            api_inspector=api_inspector,
                            semantic_analyzer=semantic_analyzer)

    original_supervisor_step = supervisor.step
    def supervisor_step_wrapper(*args, **kwargs):
        result = original_supervisor_step(*args, **kwargs)
        recorder.log(f"[SUPERVISOR] status={supervisor.status} module_index={supervisor.current_module_index} fix_attempts={supervisor.fix_attempts}")
        return result
    supervisor.step = supervisor_step_wrapper

    agents = [engineer, coder, tester]

    supervisor.set_idea("A simple greeting app")
    recorder.log("[PIPELINE] Starting pipeline")

    iterations = 0
    try:
        while supervisor.status not in ("completed", "error") and iterations < MAX_ITERATIONS:
            supervisor.step()
            for agent in agents:
                agent.step()
                observe_files(config.OUTPUT_DIR)
            if supervisor.status in ("completed", "error"):
                break
            iterations += 1
            time.sleep(LOOP_DELAY)
    except Exception as e:
        loop_error = traceback.format_exc()
        recorder.log(f"[PIPELINE] Exception: {loop_error}")

    final_status = supervisor.status
    fix_attempts = supervisor.fix_attempts

    recorder.log(f"Final supervisor status: {final_status}")
    recorder.log(f"Fix attempts: {fix_attempts}")
    recorder.log(f"Total LLM calls: {llm_call_id[0]}")
    recorder.log(f"Total CodeGenerator calls: {generation_id[0]}")
    recorder.log(f"Total file snapshots: {sum(file_counters.values())}")
    recorder.log(f"Generated files: {list(file_counters.keys())}")
    recorder.save()
    print("Flight recorder saved to", os.path.abspath(debug_dir))