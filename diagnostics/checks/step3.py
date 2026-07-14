from diagnostics.diagnose import DiagnosticReport
from diagnostics.common import read_log_entries, read_workspace_structure
import config

def check(channel, wm, supervisor, agents):
    report = DiagnosticReport(3)
    engineer = None
    for agent in agents:
        if hasattr(agent, 'designer'):
            engineer = agent
            break
    eng_ok = engineer is not None and hasattr(engineer, 'designer')
    report.add_check("Engineer agent present and has designer", eng_ok,
                     "Engineer missing or no designer" if not eng_ok else "", "ERROR")
    structure = None
    try:
        structure = wm.read_structure()
    except Exception as e:
        report.add_check("Workspace structure retrieval", False, str(e), "ERROR")
    valid_project = False
    valid_phases = False
    valid_modules = False
    if structure is not None:
        try:
            valid_project = isinstance(structure.get("project_name"), str) and structure["project_name"].strip() != ""
        except Exception:
            valid_project = False
        report.add_check("Structure has valid project_name", valid_project,
                         "Missing or empty project_name" if not valid_project else "", "ERROR")
        try:
            phases = structure.get("phases")
            valid_phases = isinstance(phases, list) and len(phases) > 0
        except Exception:
            valid_phases = False
        report.add_check("Structure has non-empty phases", valid_phases,
                         "Missing or empty phases" if not valid_phases else "", "ERROR")
        if valid_phases:
            try:
                modules = phases[0].get("modules")
                valid_modules = isinstance(modules, list) and len(modules) > 0
            except Exception:
                valid_modules = False
            report.add_check("First phase has non-empty modules", valid_modules,
                             "Modules missing or empty" if not valid_modules else "", "ERROR")
        else:
            report.add_check("First phase has non-empty modules", False, "Phases missing", "ERROR")
    else:
        report.add_check("Structure has valid project_name", False, "Structure not available", "ERROR")
        report.add_check("Structure has non-empty phases", False, "Structure not available", "ERROR")
        report.add_check("First phase has non-empty modules", False, "Structure not available", "ERROR")
    log_ok = False
    try:
        entries = read_log_entries()
        log_ok = any("Engineer designed structure" in e.get("event", "") for e in entries)
    except Exception as e:
        report.add_check("Build log inspection", False, str(e), "ERROR")
    else:
        report.add_check("Build log contains Engineer design entry", log_ok,
                         "Log entry missing" if not log_ok else "", "ERROR")
    if structure is None:
        diag = "Workspace structure could not be retrieved."
        cause = "WorkspaceManager is unavailable or corrupted."
        fix = "Check workspace configuration and file permissions."
    elif not eng_ok:
        diag = "Engineer agent is missing or not properly initialized."
        cause = "Engineer agent is missing or not properly initialized."
        fix = "Check DI container in main.py."
    elif not valid_project or not valid_phases or not valid_modules:
        diag = "Project structure is incomplete or invalid."
        cause = "Engineer did not generate a valid project structure."
        fix = "Inspect _handle_design_structure in agents/engineer.py."
    elif not log_ok:
        diag = "Engineer did not log the design event."
        cause = "Engineer did not log the design event."
        fix = "Check the logging logic in agents/engineer.py."
    else:
        diag = "Step 3 is healthy."
        cause = ""
        fix = ""
    report.finalize(diag, cause, fix)
    return report