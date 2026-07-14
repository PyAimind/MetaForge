import os
from diagnostics.diagnose import DiagnosticReport
from diagnostics.common import read_log_entries, read_test_results, read_workspace_structure, check_file_exists
import config

def check(channel, wm, supervisor, agents):
    report = DiagnosticReport(5)
    tester = None
    for agent in agents:
        if hasattr(agent, 'executor'):
            tester = agent
            break
    tester_ok = tester is not None and hasattr(tester, 'executor')
    report.add_check("Tester agent present and has executor", tester_ok,
                     "Tester missing or no executor" if not tester_ok else "", "ERROR")
    results = None
    try:
        results = read_test_results()
    except Exception as e:
        report.add_check("Test results file read", False, str(e), "ERROR")
    has_passed = False
    if results is not None and isinstance(results, list):
        has_passed = any(isinstance(r, dict) and r.get("status") == "passed" for r in results)
    report.add_check("Test results contain a passed entry", has_passed,
                     "No passed test found" if not has_passed else "", "ERROR")
    structure = None
    try:
        structure = read_workspace_structure()
    except Exception as e:
        report.add_check("Workspace structure retrieval", False, str(e), "ERROR")
    file_exists = False
    if structure and isinstance(structure, dict):
        phases = structure.get("phases", [])
        if phases and isinstance(phases[0], dict):
            modules = phases[0].get("modules", [])
            if modules and isinstance(modules[0], dict):
                filename = modules[0].get("filename")
                if filename:
                    filepath = os.path.join(config.OUTPUT_DIR, filename)
                    file_exists = check_file_exists(filepath)
    report.add_check("Tested output file still exists", file_exists,
                     "File missing or structure unavailable" if not file_exists else "", "ERROR")
    log_ok = False
    try:
        entries = read_log_entries()
        log_ok = any("Tester passed" in e.get("event", "") for e in entries)
    except Exception as e:
        report.add_check("Build log inspection", False, str(e), "ERROR")
    else:
        report.add_check("Build log contains Tester passed entry", log_ok,
                         "Log entry missing" if not log_ok else "", "ERROR")
    if not tester_ok:
        diag = "Tester agent is missing or not properly initialized."
        cause = "Tester agent is missing or not properly initialized."
        fix = "Check DI container in main.py."
    elif results is None or not isinstance(results, list):
        diag = "Tester did not save test results."
        cause = "Tester did not save test results."
        fix = "Inspect save_test_result in workspace/workspace_manager.py."
    elif not has_passed:
        diag = "The generated code did not pass the test."
        cause = "The generated code did not pass the test."
        fix = "Inspect the generated code for runtime errors."
    elif not file_exists:
        diag = "The tested file was deleted or moved."
        cause = "The tested file was deleted or moved."
        fix = "Check file system operations after testing."
    elif not log_ok:
        diag = "Tester did not log the test event."
        cause = "Tester did not log the test event."
        fix = "Check the logging logic in agents/tester.py."
    else:
        diag = "Step 5 is healthy. Tester successfully executed the code and saved the results."
        cause = ""
        fix = ""
    report.finalize(diag, cause, fix)
    return report