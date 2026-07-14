import os
from diagnostics.diagnose import DiagnosticReport
from diagnostics.common import read_log_entries, read_workspace_structure, check_file_exists, read_text_file
from project_design.code_generator_llm import FALLBACK_CODE
import config

def check(channel, wm, supervisor, agents):
    report = DiagnosticReport(4)
    coder = None
    for agent in agents:
        if hasattr(agent, 'generator'):
            coder = agent
            break
    coder_ok = coder is not None and hasattr(coder, 'generator')
    report.add_check("Coder agent present and has generator", coder_ok,
                     "Coder missing or no generator" if not coder_ok else "", "ERROR")
    structure = None
    try:
        structure = read_workspace_structure()
    except Exception as e:
        report.add_check("Workspace structure retrieval", False, str(e), "ERROR")
    filename = None
    filepath = None
    if structure and isinstance(structure, dict):
        phases = structure.get("phases", [])
        if phases and isinstance(phases[0], dict):
            modules = phases[0].get("modules", [])
            if modules and isinstance(modules[0], dict):
                filename = modules[0].get("filename")
                filepath = os.path.join(config.OUTPUT_DIR, filename) if filename else None
    if not filepath:
        report.add_check("Output file path resolved", False, "No valid structure or filename", "ERROR")
    else:
        report.add_check("Output file path resolved", True)
    file_ok = False
    content = None
    if filepath and check_file_exists(filepath):
        content = read_text_file(filepath)
        if content is not None and content.strip() and content.strip() != FALLBACK_CODE.strip():
            try:
                compile(content, filepath, 'exec')
                file_ok = True
            except Exception:
                pass
    report.add_check("Output file exists and is valid Python (not fallback)", file_ok,
                     "File missing or invalid" if not file_ok else "", "ERROR")
    log_ok = False
    try:
        entries = read_log_entries()
        log_ok = any("Coder wrote file" in e.get("event", "") for e in entries)
    except Exception as e:
        report.add_check("Build log inspection", False, str(e), "ERROR")
    else:
        report.add_check("Build log contains Coder write entry", log_ok,
                         "Log entry missing" if not log_ok else "", "ERROR")
    if not structure:
        diag = "Project structure not found."
        cause = "Project structure not found."
        fix = "Ensure Step 3 completed successfully."
    elif not coder_ok:
        diag = "Coder agent is missing or not properly initialized."
        cause = "Coder agent is missing or not properly initialized."
        fix = "Check DI container in main.py."
    elif not file_ok:
        diag = "Coder did not produce a valid output file."
        if content is not None and content.strip() == FALLBACK_CODE.strip():
            diag = "Coder used fallback code instead of generating real code."
            cause = "Coder used fallback code instead of generating real code."
            fix = "Check the LLM provider connection in CodeGeneratorLLM."
        else:
            cause = "Coder did not write the output file."
            fix = "Inspect process_command in agents/coder.py."
    elif not log_ok:
        diag = "Coder did not log the file write event."
        cause = "Coder did not log the file write event."
        fix = "Check the logging logic in agents/coder.py."
    else:
        diag = "Step 4 is healthy. Coder successfully generated valid Python code."
        cause = ""
        fix = ""
    if not (not structure or not coder_ok or not file_ok or not log_ok):
        report.finalize(diag, cause, fix)
    else:
        report.finalize(diag, cause, fix)
    return report