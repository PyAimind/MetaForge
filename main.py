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


class DiagnosticMessageChannel(MessageChannel):
    """MessageChannel wrapper that logs message summaries without altering behavior."""
    def __init__(self):
        super().__init__()
        self.total_sent = 0
        self.total_received = 0

    def send(self, message):
        self.total_sent += 1
        print(f"[MSG] {message.sender} -> {message.receiver} | ", end="")
        payload = message.payload
        if message.msg_type == "CommandMsg":
            action = payload.get("action", "")
            if action == "code" or action == "test":
                fname = payload.get("filename") or payload.get("filepath") or ""
                print(f"action={action} | file={os.path.basename(fname) if fname else '?'}", end="")
            elif action == "design_structure":
                print("action=design_structure", end="")
            elif action == "generate_prompts":
                print("action=generate_prompts", end="")
            elif action == "generate_single_prompt":
                is_fix = payload.get("is_fix", False)
                print(f"action=generate_single_prompt | is_fix={is_fix}", end="")
            else:
                print(f"action={action}", end="")
            if "acceptance_tests" in payload:
                print(f" | acceptance_test | count={len(payload['acceptance_tests'])}", end="")
        else:  # ResultMsg
            status = payload.get("status", "")
            print(f"status={status}", end="")
            if "filepath" in payload:
                print(f" | file={os.path.basename(payload['filepath'])}", end="")
            if "structure" in payload:
                print(" | type=structure", end="")
            if "prompts" in payload:
                print(f" | type=prompts | count={len(payload['prompts'])}", end="")
        print()
        super().send(message)

    def receive(self, agent_name, timeout=None):
        msg = super().receive(agent_name, timeout=timeout)
        if msg is not None:
            self.total_received += 1
            if msg.msg_type == "ResultMsg":
                detail = f"status={msg.payload.get('status','')}"
            else:
                detail = f"action={msg.payload.get('action','')}"
            print(f"[MSG_RECV] {agent_name} received from {msg.sender} | type={msg.msg_type} | {detail}")
        return msg


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

# Diagnostic counters and timers
overall_start = time.monotonic()
loop_iterations = 0
supervisor_steps = 0
engineer_steps = 0
coder_steps = 0
tester_steps = 0
total_supervisor_time = 0.0
total_engineer_time = 0.0
total_coder_time = 0.0
total_tester_time = 0.0


def print_diagnostic_summary(final_status):
    total_runtime = time.monotonic() - overall_start
    print("\n========== METAFORGE DIAGNOSTIC SUMMARY ==========")
    print(f"Total runtime: {total_runtime:.2f}s")
    print(f"Loop iterations: {loop_iterations}")
    print(f"Supervisor steps: {supervisor_steps}")
    print(f"Engineer steps: {engineer_steps}")
    print(f"Coder steps: {coder_steps}")
    print(f"Tester steps: {tester_steps}")
    print(f"Engineer time: {total_engineer_time:.2f}s")
    print(f"Coder time: {total_coder_time:.2f}s")
    print(f"Tester time: {total_tester_time:.2f}s")
    print(f"Supervisor time: {total_supervisor_time:.2f}s")
    print("LLM calls observed: N/A (provider instrumentation required)")
    print(f"Final state: {final_status}")
    print("===================================================")


try:
    wm = WorkspaceManager()
    channel = DiagnosticMessageChannel()
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

    print(f"[TIME] Application started")
    print(f"[TIME] Project idea received: {project_idea}")

    try:
        supervisor.set_idea(project_idea)
        while True:
            loop_iterations += 1
            print(f"\n[LOOP] iteration={loop_iterations}")

            # Supervisor step
            sup_start = time.monotonic()
            prev_status = supervisor.status
            prev_index = supervisor.current_module_index
            keep_going = supervisor.step()
            sup_dur = time.monotonic() - sup_start
            supervisor_steps += 1
            total_supervisor_time += sup_dur
            if supervisor.status != prev_status:
                print(f"[STATE] {prev_status} -> {supervisor.status} | module_index={supervisor.current_module_index}")
            print(f"[TIME] Supervisor.step END | duration={sup_dur:.2f}s")

            # Agent steps
            for agent_name, agent in zip(["Engineer", "Coder", "Tester"], agents):
                step_start = time.monotonic()
                agent.step()
                step_dur = time.monotonic() - step_start
                if agent_name == "Engineer":
                    engineer_steps += 1
                    total_engineer_time += step_dur
                elif agent_name == "Coder":
                    coder_steps += 1
                    total_coder_time += step_dur
                elif agent_name == "Tester":
                    tester_steps += 1
                    total_tester_time += step_dur
                print(f"[TIME] {agent_name}.step END | duration={step_dur:.2f}s")

            if not keep_going and supervisor.status in ("completed", "error"):
                break
            time.sleep(LOOP_DELAY)

    except KeyboardInterrupt:
        print("\n[INTERRUPTED] User interrupted execution.")
        print_diagnostic_summary("interrupted")
        sys.exit(1)

    if supervisor.status == "completed":
        print("MetaForge project completed.")
        print_diagnostic_summary("completed")
    else:
        print("MetaForge project failed with error.")
        print_diagnostic_summary("error")
    print(f"Output: {config.OUTPUT_DIR}")

except Exception as e:
    print(f"Startup error: {e}")
    sys.exit(1)