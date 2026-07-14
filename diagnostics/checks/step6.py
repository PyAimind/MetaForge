import os
from diagnostics.diagnose import DiagnosticReport
from diagnostics.common import read_log_entries, read_workspace_structure, check_file_exists
import config

def check(channel, wm, supervisor, agents):
    report = DiagnosticReport(6)
    engineer = coder = tester = None
    for agent in agents:
        if hasattr(agent, 'designer'):
            engineer = agent
        elif hasattr(agent, 'generator'):
            coder = agent
        elif hasattr(agent, 'executor'):
            tester = agent
    agents_ok = engineer is not None and coder is not None and tester is not None
    report.add_check("All agents present and responsive", agents_ok,
                     "Missing agents" if not agents_ok else "", "ERROR")
    status_ok = False
    try:
        status_ok = supervisor.status == "completed"
    except Exception as e:
        report.add_check("Supervisor final status check", False, str(e), "ERROR")
    else:
        report.add_check("Supervisor status is completed", status_ok,
                         f"Got {supervisor.status}" if not status_ok else "", "ERROR")
    structure = None
    try:
        structure = read_workspace_structure()
    except Exception as e:
        report.add_check("Workspace structure retrieval", False, str(e), "ERROR")
    files_ok = False
    if structure and isinstance(structure, dict):
        filenames = []
        for phase in structure.get("phases", []):
            for mod in phase.get("modules", []):
                fname = mod.get("filename")
                if fname:
                    filenames.append(fname)
        if filenames:
            files_ok = all(check_file_exists(os.path.join(config.OUTPUT_DIR, f)) for f in filenames)
        else:
            files_ok = False
    report.add_check("All output files exist", files_ok,
                     "Missing output files" if not files_ok else "", "ERROR")
    log_ok = False
    try:
        entries = read_log_entries()
        log_ok = any("project completed" in e.get("event", "").lower() for e in entries)
    except Exception as e:
        report.add_check("Build log inspection", False, str(e), "ERROR")
    else:
        report.add_check("Build log contains project completion entry", log_ok,
                         "Log entry missing" if not log_ok else "", "ERROR")
    if not agents_ok:
        diag = "One or more agents failed during the pipeline."
        cause = "One or more agents failed during the pipeline."
        fix = "Run diagnostics for earlier steps to identify the failed agent."
    elif not status_ok:
        diag = "Supervisor did not reach the completed state."
        cause = "Supervisor did not reach the completed state."
        fix = "Inspect the orchestration loop in main.py and Supervisor._handle_waiting_for_tester()."
    elif not files_ok:
        diag = "Some modules were not generated."
        cause = "Some modules were not generated."
        fix = "Check Coder output for missing files."
    elif not log_ok:
        diag = "Project completion was not logged."
        cause = "Project completion was not logged."
        fix = "Check the final logging logic in agents/supervisor.py."
    else:
        diag = "Step 6 is healthy. Project completed successfully."
        cause = ""
        fix = ""
    report.finalize(diag, cause, fix)
    return report