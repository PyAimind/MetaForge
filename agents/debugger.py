import re

class Debugger:
    def __init__(self, knowledge_base=None):
        self.knowledge_base = knowledge_base

    def analyze_error(self, filepath: str, stderr: str, stdout: str, return_code: int) -> dict:
        diagnosis = "UnknownError"
        root_cause = ""
        suggested_fix = ""
        confidence = 0.3

        if not stderr and not stdout and return_code == -1:
            diagnosis = "TimeoutError"
            confidence = 0.6
            root_cause = "The code took too long to execute"
            suggested_fix = "Check for infinite loops or blocking input calls like input()"
        elif "SyntaxError" in stderr:
            diagnosis = "SyntaxError"
            confidence = 0.99
            match = re.search(r'File ".*?", line (\d+)', stderr)
            line_number = match.group(1) if match else "unknown"
            root_cause = f"The generated code has invalid Python syntax at line {line_number}"
            suggested_fix = f"Fix the syntax error at line {line_number}"
        elif re.search(r"ModuleNotFoundError: No module named '([^']+)'", stderr) or re.search(r"ImportError: No module named '([^']+)'", stderr):
            diagnosis = "ImportError"
            confidence = 0.95
            m = re.search(r"(?:ModuleNotFoundError|ImportError): No module named '([^']+)'", stderr)
            module_name = m.group(1) if m else "unknown"
            root_cause = f"A required module '{module_name}' is missing or not yet generated"
            suggested_fix = f"Ensure the dependency module '{module_name}' is generated first, or remove the import"
        elif re.search(r"NameError: name '([^']+)' is not defined", stderr):
            diagnosis = "NameError"
            confidence = 0.95
            m = re.search(r"NameError: name '([^']+)' is not defined", stderr)
            name = m.group(1) if m else "unknown"
            root_cause = f"The name '{name}' was used before it was defined"
            suggested_fix = f"Define '{name}' before using it, or import it from another module"
        elif return_code != 0:
            diagnosis = "RuntimeError"
            confidence = 0.7
            root_cause = "The code crashed at runtime"
            suggested_fix = "Review the generated code logic for edge cases"
        else:
            diagnosis = "UnknownError"
            confidence = 0.3
            root_cause = stderr[-300:] if stderr else "Unclassified error"
            suggested_fix = "Manually review the stderr output"

        if self.knowledge_base:
            try:
                search_query = f"{diagnosis} {root_cause}"
                queries = [search_query, diagnosis, root_cause]
                failures = []
                lessons = []
                for q in queries:
                    results = self.knowledge_base.find_similar_failures(q)
                    failures = results.get("failures", [])
                    lessons = results.get("lessons", [])
                    if failures:
                        break
                if failures:
                    confidence = min(1.0, confidence + 0.05)
                    fix_reason = failures[0].get("reason", failures[0].get("title", ""))
                    if fix_reason:
                        suggested_fix += f" In a previous similar case, this was fixed by: {fix_reason}"
                elif lessons:
                    confidence = min(1.0, confidence + 0.02)
                    lesson_text = lessons[0].get("description", "")
                    if lesson_text:
                        suggested_fix += f" Related lesson: {lesson_text}"
            except Exception as e:
                raise e

        return {
            "diagnosis": diagnosis,
            "root_cause": root_cause,
            "suggested_fix": suggested_fix,
            "confidence": confidence
        }