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
MAX_ITERATIONS = 500  # افزایش برای اطمینان از کامل شدن حلقه

loop_error = None

with tempfile.TemporaryDirectory() as tmp:
    # تنظیم مسیرهای موقت
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")
    os.makedirs(config.WORKSPACE_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    # کپی دقیق از main.py برای ساخت عامل‌ها
    def build_dependencies():
        provider = LLMProvider()
        designer = StructureDesignerLLM(provider)
        generator = CodeGeneratorLLM(provider)
        executor = CodeExecutor()
        ctx = ContextManager(config.OUTPUT_DIR)
        kb = KnowledgeBase()
        debugger = Debugger(knowledge_base=kb)
        return designer, generator, executor, ctx, kb, debugger

    wm = WorkspaceManager()
    channel = MessageChannel()
    designer, generator, executor, ctx, kb, debugger = build_dependencies()
    engineer = Engineer(channel, wm, designer, knowledge_base=kb)
    coder = Coder(channel, wm, generator, ctx, knowledge_base=kb)
    tester = Tester(channel, wm, executor)

    # اضافه کردن بازرس‌ها، فقط اگر در خود main.py وجود داشته باشند
    api_inspector = None
    try:
        from agents.api_inspector import APIInspector
        api_inspector = APIInspector()
        print("DEBUG: APIInspector activated for this test.")
    except Exception:
        print("WARNING: APIInspector not available. API checks disabled.")

    semantic_analyzer = None
    try:
        from agents.semantic_analyzer import SemanticAnalyzer
        semantic_analyzer = SemanticAnalyzer()
        print("DEBUG: SemanticAnalyzer activated for this test.")
    except Exception:
        print("WARNING: SemanticAnalyzer not available. Cross-module checks disabled.")

    supervisor = Supervisor(channel, wm, debugger,
                            api_inspector=api_inspector,
                            semantic_analyzer=semantic_analyzer)

    agents = [engineer, coder, tester]

    supervisor.set_idea("A simple greeting app")

    iterations = 0
    try:
        # حلقه اصلی که دقیقاً باید مثل main.py باشد
        while supervisor.status not in ("completed", "error") and iterations < MAX_ITERATIONS:
            supervisor.step()
            for agent in agents:
                agent.step()
            iterations += 1
            time.sleep(LOOP_DELAY)
    except Exception as e:
        loop_error = traceback.format_exc()

    final_status = supervisor.status
    fix_attempts = supervisor.fix_attempts

    os.makedirs("debug_output", exist_ok=True)

    # --- ذخیره سازی کامل داده‌ها ---

    # 1. کپی فایل‌های اصلی workspace
    workspace_files = {
        "project_structure.json": "debug_05_structure.json",
        "contracts.json": "debug_05_contracts.json",
        "build_log.json": "debug_05_build_log.json",
        "test_results.json": "debug_05_test_results.json"
    }
    for fname, dst in workspace_files.items():
        src = os.path.join(config.WORKSPACE_DIR, fname)
        if os.path.isfile(src):
            with open(src, "r", encoding="utf-8") as f:
                data = f.read()
            with open(os.path.join("debug_output", dst), "w", encoding="utf-8") as f:
                f.write(data)
        else:
            with open(os.path.join("debug_output", dst), "w", encoding="utf-8") as f:
                f.write("not found")

    # 2. لیست فایل‌های تولید شده
    generated = os.listdir(config.OUTPUT_DIR) if os.path.isdir(config.OUTPUT_DIR) else []
    with open(os.path.join("debug_output", "debug_05_generated_files.json"), "w") as f:
        json.dump(generated, f)

    # 3. وضعیت صف‌های پیام (رفع مشکل عدم وجود config.AGENT_NAMES)
    queue_info = {}
    agent_names = getattr(config, "AGENT_NAMES", ["supervisor", "engineer", "coder", "tester"])
    for agent_name in agent_names:
        try:
            queue_info[agent_name] = channel.queue_size(agent_name)
        except Exception:
            queue_info[agent_name] = 1 if channel.has_messages(agent_name) else 0
    with open(os.path.join("debug_output", "debug_05_message_queues.json"), "w") as f:
        json.dump(queue_info, f, indent=2)

    # 4. ذخیره محتوای واقعی صف‌های پیام (ایده شما برای شفافیت کامل)
    messages_dump = {}
    for agent_name in agent_names:
        agent_messages = []
        try:
            while channel.has_messages(agent_name):
                msg = channel.receive(agent_name, timeout=0.05)
                # تبدیل پیام به دیکشنری برای ذخیره
                agent_messages.append({
                    "sender": msg.sender,
                    "receiver": msg.receiver,
                    "msg_type": msg.msg_type,
                    "phase": msg.phase,
                    "payload": msg.payload
                })
        except Exception:
            pass
        messages_dump[agent_name] = agent_messages
    with open(os.path.join("debug_output", "debug_05_messages.json"), "w") as f:
        json.dump(messages_dump, f, indent=2)

    # 5. خواندن لاگ رویدادها
    log_entries = []
    log_path = config.LOG_FILE
    if os.path.isfile(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                log_entries = json.load(f)
        except Exception:
            pass

    # 6. نوشتن گزارش نهایی
    with open(os.path.join("debug_output", "debug_05_pipeline_log.txt"), "w", encoding="utf-8") as f:
        f.write(f"Final supervisor status: {final_status}\n")
        f.write(f"Fix attempts: {fix_attempts}\n")
        f.write(f"Iterations run: {iterations}\n\n")
        f.write("Last 40 build log events:\n")
        for entry in log_entries[-40:]:
            f.write(f"  [{entry.get('timestamp', '')}] {entry.get('event', '')}\n")
        if loop_error:
            f.write("\nException during loop:\n")
            f.write(loop_error)

    # --- خروجی کنسول ---
    print(f"Final supervisor status: {final_status}")
    print(f"Fix attempts: {fix_attempts}")
    print(f"Message queue states: {queue_info}")
    if loop_error:
        print("Exception occurred (see debug_05_pipeline_log.txt):")
        print(loop_error)
    print(f"Debug output saved to: {os.path.abspath('debug_output')}")