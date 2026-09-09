import os
import json
import queue
import tempfile
from communication.message import Message
from communication.message_channel import MessageChannel
from workspace.workspace_manager import WorkspaceManager
from project_design.code_executor import CodeExecutor
import config

class Tester:
    def __init__(self, channel: MessageChannel, workspace: WorkspaceManager, executor):
        if not isinstance(channel, MessageChannel):
            raise TypeError("channel must be a MessageChannel instance")
        if not isinstance(workspace, WorkspaceManager):
            raise TypeError("workspace must be a WorkspaceManager instance")
        if executor is None or not callable(getattr(executor, 'execute', None)) or not callable(getattr(executor, 'classify_error', None)):
            raise TypeError("executor must have callable 'execute' and 'classify_error' methods")
        self.channel = channel
        self.workspace = workspace
        self.executor = executor

    def _error_response(self, phase, reason):
        return Message(
            sender="tester",
            receiver="supervisor",
            msg_type="ResultMsg",
            phase=phase,
            payload={"status": "error", "reason": reason}
        )

    def _run_generic_acceptance_tests(self, acceptance_tests: list, output_dir: str) -> dict:
        if not isinstance(acceptance_tests, list) or not acceptance_tests:
            return {"status": "unsupported", "reason": "No acceptance tests provided"}

        results = []
        with tempfile.TemporaryDirectory() as test_dir:
            for test in acceptance_tests:
                if not isinstance(test, dict):
                    results.append({
                        "description": "Invalid test object",
                        "passed": False,
                        "status": "error",
                        "actual_stdout": "",
                        "stderr": "",
                        "return_code": None,
                        "error_reason": "Acceptance test is not a dictionary"
                    })
                    continue

                description = test.get("description", "")
                entrypoint = test.get("entrypoint", "")
                args = test.get("args", [])
                expected_stdout = test.get("expected_stdout_contains", [])
                expected_return_code = test.get("expected_return_code", 0)
                timeout_seconds = test.get("timeout_seconds", 10)

                if not entrypoint or not isinstance(entrypoint, str) or not entrypoint.endswith(".py"):
                    results.append({
                        "description": description,
                        "passed": False,
                        "status": "missing_entrypoint",
                        "actual_stdout": "",
                        "stderr": "",
                        "return_code": None,
                        "error_reason": f"Entrypoint not found: {entrypoint}"
                    })
                    continue

                filepath = os.path.join(output_dir, entrypoint)
                if not os.path.isfile(filepath):
                    results.append({
                        "description": description,
                        "passed": False,
                        "status": "missing_entrypoint",
                        "actual_stdout": "",
                        "stderr": "",
                        "return_code": None,
                        "error_reason": f"Entrypoint not found: {entrypoint}"
                    })
                    continue

                try:
                    result = self.executor.execute(
                        filepath,
                        working_directory=test_dir,
                        timeout_seconds=timeout_seconds,
                        args=args,
                    )
                except Exception as exc:
                    results.append({
                        "description": description,
                        "passed": False,
                        "status": "error",
                        "actual_stdout": "",
                        "stderr": "",
                        "return_code": None,
                        "error_reason": str(exc),
                    })
                    continue

                actual_return_code = result.get("return_code")
                actual_stdout = result.get("stdout", "")
                actual_stderr = result.get("stderr", "")
                executor_status = result.get("status")

                if executor_status == "timeout":
                    status = "timeout"
                    passed = False
                    error_reason = "Execution timed out"
                elif executor_status == "error":
                    status = "error"
                    passed = False
                    error_reason = actual_stderr or "Execution error"
                else:
                    stdout_ok = all(sub in actual_stdout for sub in expected_stdout)
                    return_ok = actual_return_code == expected_return_code
                    if stdout_ok and return_ok:
                        status = "passed"
                        passed = True
                        error_reason = None
                    else:
                        status = "failed"
                        passed = False
                        error_reason = None

                results.append({
                    "description": description,
                    "passed": passed,
                    "status": status,
                    "actual_stdout": actual_stdout,
                    "stderr": actual_stderr,
                    "return_code": actual_return_code,
                    "error_reason": error_reason,
                })

        all_passed = all(r["passed"] for r in results)
        return {
            "status": "passed" if all_passed else "failed",
            "tests": results,
        }

    def process_command(self, message: Message) -> Message:
        if message.msg_type != "CommandMsg":
            return self._error_response(message.phase, "Invalid message type")
        if not isinstance(message.payload, dict):
            return self._error_response(message.phase, "Invalid payload")

        acceptance_tests = message.payload.get("acceptance_tests")
        if acceptance_tests is not None:
            summary = self._run_generic_acceptance_tests(acceptance_tests, config.OUTPUT_DIR)
            if summary["status"] == "unsupported":
                self.workspace.log_event("Tester: no acceptance tests provided", message.phase)
                return Message(
                    sender="tester",
                    receiver="supervisor",
                    msg_type="ResultMsg",
                    phase=message.phase,
                    payload={"status": "unsupported", "reason": summary["reason"]}
                )
            self.workspace.save_test_result(message.phase, summary["status"], json.dumps(summary))
            self.workspace.log_event(f"Tester acceptance summary: {summary['status']}", message.phase)
            return Message(
                sender="tester",
                receiver="supervisor",
                msg_type="ResultMsg",
                phase=message.phase,
                payload={"status": summary["status"], "tests": summary["tests"]}
            )

        filepath = message.payload.get("filepath")
        if not isinstance(filepath, str) or not filepath.strip():
            return self._error_response(message.phase, "Missing or invalid filepath")
        abs_file = os.path.abspath(filepath)
        abs_output = os.path.abspath(config.OUTPUT_DIR)
        try:
            if os.path.commonpath([abs_output, abs_file]) != abs_output:
                return self._error_response(message.phase, "Access denied")
        except ValueError:
            return self._error_response(message.phase, "Access denied")
        if not os.path.isfile(abs_file):
            return self._error_response(message.phase, "File not found")
        try:
            with open(abs_file, 'r') as f:
                content = f.read()
            compile(content, abs_file, 'exec')
        except Exception as e:
            return self._error_response(message.phase, f"Syntax error in {abs_file}: {str(e)}")

        cli_keywords = ("argparse", "sys.argv")
        if any(kw in content for kw in cli_keywords):
            result = self.executor.execute(abs_file, timeout_seconds=5, args=["--help"])
            if not isinstance(result, dict) or "status" not in result:
                return self._error_response(message.phase, "Executor returned an invalid result for CLI testing")
            if result["status"] == "passed":
                self.workspace.save_test_result(message.phase, "passed", json.dumps({"execution_status": "cli_help_tested"}))
                self.workspace.log_event(f"Tester successfully tested CLI with --help: {abs_file}", message.phase)
                return Message(sender="tester", receiver="supervisor", msg_type="ResultMsg",
                               phase=message.phase, payload={"filepath": abs_file, "status": "passed", "execution_status": "cli_help_tested"})
            elif result["status"] == "failed":
                error_type = self.executor.classify_error(result["stderr"])
                if error_type == "python_error":
                    self.workspace.save_test_result(message.phase, "failed", json.dumps(result))
                    self.workspace.log_event(f"Tester failed: {abs_file} (Python error)", message.phase)
                    payload = dict(result)
                    payload["filepath"] = abs_file
                    return Message(sender="tester", receiver="supervisor", msg_type="ResultMsg",
                                   phase=message.phase, payload=payload)
                else:
                    self.workspace.save_test_result(message.phase, "failed", json.dumps(result))
                    self.workspace.log_event(f"Tester: CLI validation failed: {abs_file}", message.phase)
                    payload = dict(result)
                    payload["filepath"] = abs_file
                    return Message(sender="tester", receiver="supervisor", msg_type="ResultMsg",
                                   phase=message.phase, payload=payload)
            elif result["status"] == "timeout":
                self.workspace.save_test_result(message.phase, "failed", json.dumps(result))
                self.workspace.log_event(f"Tester: CLI execution timed out: {abs_file}", message.phase)
                payload = dict(result)
                payload["filepath"] = abs_file
                return Message(sender="tester", receiver="supervisor", msg_type="ResultMsg",
                               phase=message.phase, payload=payload)
            else:
                self.workspace.save_test_result(message.phase, "error", json.dumps({"error": "cli_execution_failed", "stderr": result.get("stderr", "")}))
                self.workspace.log_event(f"Tester error: {abs_file}", message.phase)
                payload = dict(result)
                payload["filepath"] = abs_file
                return Message(sender="tester", receiver="supervisor", msg_type="ResultMsg",
                               phase=message.phase, payload=payload)

        try:
            result = self.executor.execute(abs_file)
        except Exception as e:
            try:
                self.workspace.log_event(f"Tester executor error: {e}", message.phase)
            except Exception:
                pass
            return self._error_response(message.phase, f"Executor failed: {str(e)}")
        required_keys = {"status", "return_code", "stdout", "stderr", "execution_time"}
        if not isinstance(result, dict) or not required_keys.issubset(result):
            return self._error_response(message.phase, "Invalid executor result")
        self.workspace.save_test_result(message.phase, result["status"], json.dumps(result))
        self.workspace.log_event(f"Tester {result['status']}: {abs_file}", message.phase)
        payload = dict(result)
        payload["filepath"] = abs_file
        return Message(
            sender="tester",
            receiver="supervisor",
            msg_type="ResultMsg",
            phase=message.phase,
            payload=payload
        )

    def step(self) -> bool:
        try:
            msg = self.channel.receive("tester", timeout=0.1)
        except queue.Empty:
            return False
        result = self.process_command(msg)
        self.channel.send(result)
        return True