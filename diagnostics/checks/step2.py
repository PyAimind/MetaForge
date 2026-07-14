import queue
from diagnostics.diagnose import DiagnosticReport
from diagnostics.common import read_log_entries
import config

def check(channel, wm, supervisor, agents):
    report = DiagnosticReport(2)
    engineer = None
    for agent in agents:
        if hasattr(agent, 'designer'):
            engineer = agent
            break
    eng_ok = engineer is not None and hasattr(engineer, 'designer')
    report.add_check("Engineer agent present and has designer", eng_ok,
                     "Engineer missing or no designer" if not eng_ok else "", "ERROR")
    status_ok = False
    try:
        status_ok = supervisor.status == "waiting_for_engineer"
    except Exception as e:
        report.add_check("Supervisor status check", False, str(e), "ERROR")
    else:
        report.add_check("Supervisor status is waiting_for_engineer", status_ok,
                         f"Got {supervisor.status}" if not status_ok else "", "ERROR")
    log_ok = False
    try:
        entries = read_log_entries()
        log_ok = any("Supervisor sent design request" in e.get("event", "") for e in entries)
    except Exception as e:
        report.add_check("Build log inspection", False, str(e), "ERROR")
    else:
        report.add_check("Build log contains design dispatch entry", log_ok,
                         "Log entry missing" if not log_ok else "", "ERROR")
    if not eng_ok:
        diag = "Engineer agent is missing or not properly initialized."
        cause = "Engineer agent is missing or not properly initialized."
        fix = "Check DI container in main.py."
    elif not status_ok:
        diag = "Supervisor state machine did not transition to waiting_for_engineer."
        cause = "Supervisor state machine did not transition."
        fix = "Inspect agents/supervisor.py."
    elif not log_ok:
        diag = "Supervisor did not log the design dispatch."
        cause = "Supervisor did not log the design dispatch."
        fix = "Check logging in agents/supervisor.py."
    else:
        diag = "Step 2 is healthy. Supervisor successfully sent design request to Engineer."
        cause = ""
        fix = ""
    report.finalize(diag, cause, fix)
    return report