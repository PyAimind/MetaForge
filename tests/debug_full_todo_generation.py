import os
import sys
import json
import time
import tempfile
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT_DIR, '.env'))

sys.path.insert(0, ROOT_DIR)
import config
from workspace.workspace_manager import WorkspaceManager
from communication.message_channel import MessageChannel
from agents.supervisor import Supervisor
from agents.engineer import Engineer
from agents.coder import Coder
from agents.tester import Tester

LOOP_DELAY = 0.01
MAX_ITERATIONS = 1000

# Use a permanent temp directory so artifacts survive crashes
tmp = tempfile.mkdtemp(prefix="metaforge_todo_demo_")
print(f"Temporary workspace: {tmp}")

try:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")
    os.makedirs(config.WORKSPACE_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    # Safe import of main's factory (main.py must not execute at import time)
    import main as main_module
    designer, generator, executor, ctx, kb, debugger = main_module.build_dependencies()

    wm = WorkspaceManager()
    channel = MessageChannel()

    # Message trace – capture both send and receive
    message_trace = []
    original_send = channel.send
    def traced_send(message):
        message_trace.append({
            "direction": "send",
            "sender": message.sender,
            "receiver": message.receiver,
            "msg_type": message.msg_type,
            "payload": message.payload
        })
        original_send(message)
    channel.send = traced_send

    original_receive = channel.receive
    def traced_receive(receiver, timeout=None):
        msg = original_receive(receiver, timeout)
        if msg:
            message_trace.append({
                "direction": "receive",
                "receiver": receiver,
                "sender": msg.sender,
                "msg_type": msg.msg_type,
                "payload": msg.payload
            })
        return msg
    channel.receive = traced_receive

    engineer = Engineer(channel, wm, designer, knowledge_base=kb)
    coder = Coder(channel, wm, generator, ctx, knowledge_base=kb)
    tester = Tester(channel, wm, executor)

    # Enforce mandatory analyzers for acceptance
    from agents.api_inspector import APIInspector
    api_inspector = APIInspector()
    print("APIInspector activated.")

    from agents.semantic_analyzer import SemanticAnalyzer
    semantic_analyzer = SemanticAnalyzer()
    print("SemanticAnalyzer activated.")

    supervisor = Supervisor(channel, wm, debugger,
                            api_inspector=api_inspector,
                            semantic_analyzer=semantic_analyzer)

    agents = [engineer, coder, tester]
    idea = "A simple CLI Todo app with add, remove, list, and JSON storage"
    supervisor.set_idea(idea)

    iterations = 0
    while supervisor.status not in ("completed", "error") and iterations < MAX_ITERATIONS:
        supervisor.step()
        for agent in agents:
            agent.step()
        iterations += 1
        time.sleep(LOOP_DELAY)

    if iterations >= MAX_ITERATIONS:
        print(f"Reached max iterations ({MAX_ITERATIONS}) without finishing.")

    debug_dir = os.path.join(tmp, "debug_demo")
    os.makedirs(debug_dir, exist_ok=True)

    # --- Save all artifacts ---
    with open(os.path.join(debug_dir, "00_idea.txt"), "w", encoding="utf-8") as f:
        f.write(idea)

    struct_src = config.STRUCTURE_FILE
    if os.path.isfile(struct_src):
        with open(struct_src, "r", encoding="utf-8") as fsrc:
            with open(os.path.join(debug_dir, "01_structure.json"), "w", encoding="utf-8") as fdst:
                fdst.write(fsrc.read())

    contracts_src = os.path.join(config.WORKSPACE_DIR, "contracts.json")
    if os.path.isfile(contracts_src):
        with open(contracts_src, "r", encoding="utf-8") as fsrc:
            with open(os.path.join(debug_dir, "02_contracts.json"), "w", encoding="utf-8") as fdst:
                fdst.write(fsrc.read())

    prompts_dir = os.path.join(debug_dir, "03_prompts")
    os.makedirs(prompts_dir, exist_ok=True)
    for mod_name, prompt_text in supervisor.prompts.items():
        safe_name = mod_name.replace("/", "_").replace("\\", "_")
        with open(os.path.join(prompts_dir, f"{safe_name}.txt"), "w", encoding="utf-8") as f:
            f.write(prompt_text)

    code_dir = os.path.join(debug_dir, "04_generated_code")
    os.makedirs(code_dir, exist_ok=True)
    if os.path.isdir(config.OUTPUT_DIR):
        for fname in os.listdir(config.OUTPUT_DIR):
            src = os.path.join(config.OUTPUT_DIR, fname)
            if os.path.isfile(src):
                with open(src, "r", encoding="utf-8") as fsrc:
                    content = fsrc.read()
                with open(os.path.join(code_dir, fname), "w", encoding="utf-8") as fdst:
                    fdst.write(content)

    log_src = config.LOG_FILE
    if os.path.isfile(log_src):
        with open(log_src, "r", encoding="utf-8") as fsrc:
            with open(os.path.join(debug_dir, "05_build_log.json"), "w", encoding="utf-8") as fdst:
                fdst.write(fsrc.read())

    test_src = config.TEST_RESULTS_FILE
    if os.path.isfile(test_src):
        with open(test_src, "r", encoding="utf-8") as fsrc:
            with open(os.path.join(debug_dir, "06_test_results.json"), "w", encoding="utf-8") as fdst:
                fdst.write(fsrc.read())

    with open(os.path.join(debug_dir, "07_final_status.txt"), "w", encoding="utf-8") as f:
        f.write(f"status={supervisor.status}\nfix_attempts={json.dumps(supervisor.fix_attempts)}\niterations={iterations}")

    with open(os.path.join(debug_dir, "08_message_trace.json"), "w", encoding="utf-8") as f:
        json.dump(message_trace, f, indent=2, default=str)

    # --- Console trace ---
    print("=== IDEA ===")
    print(idea)

    print("\n=== STRUCTURE (filenames) ===")
    structure = None
    if os.path.isfile(struct_src):
        with open(struct_src, "r") as f:
            structure = json.load(f)
        for phase in structure.get("phases", []):
            for mod in phase.get("modules", []):
                print(f"  {mod.get('filename')}")

    print("\n=== CONTRACTS (exports) ===")
    contracts = None
    if os.path.isfile(contracts_src):
        with open(contracts_src, "r") as f:
            contracts = json.load(f)
        for mod_name, contract in contracts.items():
            exports = contract.get("exports", [])
            print(f"  {mod_name}: {len(exports)} exports")
            for exp in exports:
                print(f"    - {exp.get('name')} ({exp.get('kind')})")

    print("\n=== PROMPTS (first 500 chars) ===")
    for mod_name, prompt_text in supervisor.prompts.items():
        print(f"  {mod_name}:")
        print(prompt_text[:500])
        print("    ...")

    print("\n=== GENERATED CODE ===")
    if os.path.isdir(config.OUTPUT_DIR):
        for fname in os.listdir(config.OUTPUT_DIR):
            src = os.path.join(config.OUTPUT_DIR, fname)
            if os.path.isfile(src):
                with open(src, "r") as f:
                    code = f.read()
                print(f"  --- {fname} ---")
                print(code)
                print()

    print(f"\n=== FINAL STATUS ===")
    print(f"status={supervisor.status}")
    print(f"fix_attempts={supervisor.fix_attempts}")

    print(f"\nDebug artifacts saved to: {os.path.abspath(debug_dir)}")

    # Final assertions
    assert supervisor.status == "completed", f"Expected 'completed', got {supervisor.status}"
    output_files = os.listdir(config.OUTPUT_DIR) if os.path.isdir(config.OUTPUT_DIR) else []
    assert len(output_files) >= 1, "No files generated in OUTPUT_DIR"

    print("\nACCEPTANCE TEST PASSED")

except Exception as e:
    print(f"\nFATAL ERROR: {e}")
    import traceback
    traceback.print_exc()
finally:
    print(f"\nTemporary workspace preserved at: {tmp}")
    print("Delete this folder manually when done.")