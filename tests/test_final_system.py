import sys
import os
import json
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from workspace.workspace_manager import WorkspaceManager
from communication.message_channel import MessageChannel
from agents.supervisor import Supervisor
from agents.engineer import Engineer
from agents.coder import Coder
from agents.tester import Tester

def check(step, description, condition, fail_reason):
    if condition:
        print(f"[STEP {step}] {description} ✅")
        return True
    else:
        print(f"[STEP {step}] {description} ❌ REASON: {fail_reason}")
        sys.exit(1)

with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")
    wm = WorkspaceManager()
    channel = MessageChannel()
    supervisor = Supervisor(channel, wm)
    engineer = Engineer(channel, wm)
    coder = Coder(channel, wm)
    tester = Tester(channel, wm)
    print("[SYSTEM] All components initialized.")

    supervisor.set_idea("Simple Calculator")
    step_ok = supervisor.step()
    check(2, "Supervisor sends design_structure to Engineer",
          step_ok and supervisor.status == "waiting_for_engineer",
          "Supervisor did not transition to waiting_for_engineer")

    msg = channel.receive("engineer", timeout=0.2)
    check("3a", "Engineer received design_structure command",
          msg is not None and msg.payload.get("action") == "design_structure",
          "Engineer queue empty or wrong command")
    if msg is not None:
        channel.send(msg)
    engineer_step = engineer.step()
    check("3b", "Engineer processed design_structure",
          engineer_step,
          "Engineer step returned False")
    eng_resp = channel.receive("supervisor", timeout=0.2)
    check("3c", "Engineer sent structure response to Supervisor",
          eng_resp is not None and eng_resp.payload.get("status") == "success" and "structure" in eng_resp.payload,
          "Missing structure in Engineer response")
    if eng_resp is not None:
        channel.send(eng_resp)
    sup_step = supervisor.step()
    eng_cmd = channel.receive("engineer", timeout=0.2)
    check(3, "Engineer returns structure and Supervisor requests prompts",
          eng_cmd is not None and eng_cmd.payload.get("action") == "generate_prompts",
          "No generate_prompts command sent to Engineer")
    if eng_cmd is not None:
        channel.send(eng_cmd)

    engineer_step = engineer.step()
    check("4a", "Engineer processed generate_prompts",
          engineer_step,
          "Engineer step returned False")
    eng_prompts = channel.receive("supervisor", timeout=0.2)
    check("4b", "Engineer sent prompts response",
          eng_prompts is not None and eng_prompts.payload.get("status") == "success" and "prompts" in eng_prompts.payload,
          "Missing prompts in Engineer response")
    if eng_prompts is not None:
        channel.send(eng_prompts)
    sup_step = supervisor.step()
    coder_cmd = channel.receive("coder", timeout=0.2)
    check(4, "Prompts generated and first module sent to Coder",
          coder_cmd is not None and coder_cmd.payload.get("action") == "code" and coder_cmd.payload.get("filename") == "input_handler.py",
          "No code command for input_handler.py in Coder queue")
    if coder_cmd is not None:
        channel.send(coder_cmd)

    check("5a", "Coder processed code command for input_handler.py", coder.step(), "Coder step returned False")
    check("5b", "Supervisor processed Coder response", supervisor.step(), "Supervisor step returned False")
    filepath = os.path.join(config.OUTPUT_DIR, "input_handler.py")
    file_ok = os.path.exists(filepath)
    content = ""
    if file_ok:
        with open(filepath, encoding='utf-8') as f:
            content = f.read()
    no_leak = all(x not in content for x in ["### Dependencies", "Write a Python file", "Deliver ONLY raw Python code"])
    valid_python = False
    if no_leak and file_ok:
        try:
            compile(content, filepath, 'exec')
            valid_python = True
        except Exception:
            pass
    check(5, "Coder creates valid input_handler.py (no prompt leakage)",
          file_ok and len(content.strip()) > 0 and no_leak and valid_python,
          "File missing, empty, contains prompt text, or not valid Python")

    check("6a", "Tester processed test command", tester.step(), "Tester step returned False")
    check("6b", "Supervisor processed Tester response", supervisor.step(), "Supervisor step returned False")
    coder_cmd2 = channel.receive("coder", timeout=0.2)
    check(6, "Tester passes input_handler.py and Supervisor advances to calculator.py",
          coder_cmd2 is not None and coder_cmd2.payload.get("filename") == "calculator.py",
          "Tester did not pass or Supervisor stuck")
    if coder_cmd2 is not None:
        channel.send(coder_cmd2)

    check("7a", "Coder processed code command for calculator.py", coder.step(), "Coder step returned False")
    check("7b", "Supervisor processed Coder response", supervisor.step(), "Supervisor step returned False")
    filepath2 = os.path.join(config.OUTPUT_DIR, "calculator.py")
    file_ok2 = os.path.exists(filepath2)
    content2 = ""
    if file_ok2:
        with open(filepath2, encoding='utf-8') as f:
            content2 = f.read()
    no_leak2 = all(x not in content2 for x in ["### Dependencies", "Write a Python file", "Deliver ONLY raw Python code"])
    valid_python2 = False
    if no_leak2 and file_ok2:
        try:
            compile(content2, filepath2, 'exec')
            valid_python2 = True
        except Exception:
            pass
    check("7c", "Tester processed test command", tester.step(), "Tester step returned False")
    check("7d", "Supervisor processed Tester response", supervisor.step(), "Supervisor step returned False")
    coder_cmd3 = channel.receive("coder", timeout=0.2)
    check(7, "calculator.py built and tested, advancing to main.py",
          file_ok2 and len(content2.strip()) > 0 and no_leak2 and valid_python2 and coder_cmd3 is not None and coder_cmd3.payload.get("filename") == "main.py",
          "Module failed")
    if coder_cmd3 is not None:
        channel.send(coder_cmd3)

    check("8a", "Coder processed code command for main.py", coder.step(), "Coder step returned False")
    check("8b", "Supervisor processed Coder response", supervisor.step(), "Supervisor step returned False")
    filepath3 = os.path.join(config.OUTPUT_DIR, "main.py")
    file_ok3 = os.path.exists(filepath3)
    content3 = ""
    if file_ok3:
        with open(filepath3, encoding='utf-8') as f:
            content3 = f.read()
    no_leak3 = all(x not in content3 for x in ["### Dependencies", "Write a Python file", "Deliver ONLY raw Python code"])
    valid_python3 = False
    if no_leak3 and file_ok3:
        try:
            compile(content3, filepath3, 'exec')
            valid_python3 = True
        except Exception:
            pass
    check("8c", "Tester processed test command", tester.step(), "Tester step returned False")
    check("8d", "Supervisor processed Tester response", supervisor.step(), "Supervisor step returned False")
    check(8, "main.py built and tested",
          file_ok3 and len(content3.strip()) > 0 and no_leak3 and valid_python3,
          "Module failed")

    all_files_ok = all(os.path.exists(p) and os.path.getsize(p) > 0 for p in [filepath, filepath2, filepath3])
    check(9, "Project completed successfully",
          supervisor.status == "completed" and all_files_ok,
          "Project did not reach completed state")

    try:
        with open(config.STRUCTURE_FILE) as f:
            structure = json.load(f)
        with open(config.LOG_FILE) as f:
            log_entries = json.load(f)
        logs_ok = isinstance(log_entries, list)
        structure_ok = isinstance(structure, dict) and structure.get("project_name") == "Simple Calculator"
        has_completed = any("project completed" in e.get("event", "").lower() for e in log_entries)
        has_tester = any("tester passed" in e.get("event", "").lower() for e in log_entries)
        check(10, "Workspace files are valid and contain expected logs",
              logs_ok and structure_ok and has_completed and has_tester,
              "Workspace validation failed")
    except Exception as e:
        check(10, "Workspace files are valid and contain expected logs",
              False, str(e))

    print("ALL SYSTEM TESTS PASSED.")