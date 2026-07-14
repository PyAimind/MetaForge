import queue
from diagnostics.common import read_log_entries
import config

class DiagnosticReport:
    def __init__(self, step):
        self.step = step
        self.checks = []

    def add_check(self, description, passed, detail="", severity="ERROR"):
        self.checks.append({"description": description, "passed": passed, "detail": detail, "severity": severity})

    def finalize(self, diagnosis, root_cause="", suggested_fix=""):
        self.diagnosis = diagnosis
        self.root_cause = root_cause
        self.suggested_fix = suggested_fix

    def to_string(self):
        lines = [f"STEP {self.step} DIAGNOSTIC REPORT", "-" * 30]
        for i, c in enumerate(self.checks, 1):
            if c["passed"]:
                lines.append(f"[{i}] {c['description']}: ✓")
            else:
                lines.append(f"[{i}] {c['description']}: ✗ ({c['detail']}) [{c['severity']}]")
        lines.append("")
        lines.append("### Diagnosis")
        lines.append(self.diagnosis)
        if self.root_cause:
            lines.append("")
            lines.append("### Root Cause Analysis")
            lines.append(self.root_cause)
        if self.suggested_fix:
            lines.append("")
            lines.append("### Suggested Fix")
            lines.append(self.suggested_fix)
        return "\n".join(lines)

    def print_report(self):
        print(self.to_string())


def run_diagnostics(step, channel, wm, supervisor, agents):
    if step == 2:
        from diagnostics.checks.step2 import check
        return check(channel, wm, supervisor, agents)
    elif step == 3:
        from diagnostics.checks.step3 import check
        return check(channel, wm, supervisor, agents)
    elif step == 4:
        from diagnostics.checks.step4 import check
        return check(channel, wm, supervisor, agents)
    elif step == 5:
        from diagnostics.checks.step5 import check
        return check(channel, wm, supervisor, agents)
    elif step == 6:
        from diagnostics.checks.step6 import check
        return check(channel, wm, supervisor, agents)
    else:
        report = DiagnosticReport(step)
        report.add_check("Unsupported step", False, f"Step {step} not implemented")
        report.finalize("No diagnostic available")
        return report

