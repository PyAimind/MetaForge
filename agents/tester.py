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

    def _run_acceptance_test(self, cli_file: str) -> dict:
        with tempfile.TemporaryDirectory() as test_dir:
            res = self.executor.execute(cli_file, args=["--help"], timeout_seconds=10, working_directory=test_dir)
            if res["return_code"] != 0:
                return {"status": "runtime_failure", "reason": f"help returned {res['return_code']}: {res['stderr']}"}

            res = self.executor.execute(cli_file, args=["add", "Test todo"], timeout_seconds=10, working_directory=test_dir)
            if res["return_code"] != 0:
                return {"status": "runtime_failure", "reason": f"add returned {res['return_code']}: {res['stderr']}"}

            res = self.executor.execute(cli_file, args=["list"], timeout_seconds=10, working_directory=test_dir)
            if res["return_code"] != 0:
                return {"status": "runtime_failure", "reason": f"list returned {res['return_code']}: {res['stderr']}"}
            if "Test todo" not in res["stdout"]:
                return {"status": "runtime_failure", "reason": f"list did not contain 'Test todo': {res['stdout']}"}

            todo_id = None
            for line in res["stdout"].splitlines():
                stripped = line.strip()
                if stripped and stripped[0].isdigit():
                    todo_id = stripped.split()[0]
                    break
            if todo_id is None:
                return {"status": "runtime_failure", "reason": "Could not find a task ID in list output"}

            res = self.executor.execute(cli_file, args=["remove", todo_id], timeout_seconds=10, working_directory=test_dir)
            if res["return_code"] != 0:
                return {"status": "runtime_failure", "reason": f"remove {todo_id} returned {res['return_code']}: {res['stderr']}"}

            res = self.executor.execute(cli_file, args=["list"], timeout_seconds=10, working_directory=test_dir)
            if res["return_code"] != 0:
                return {"status": "runtime_failure", "reason": f"list after remove returned {res['return_code']}: {res['stderr']}"}
            if todo_id in res["stdout"]:
                return {"status": "runtime_failure", "reason": f"ID {todo_id} still present after remove"}

            return {"status": "accepted"}

    def process_command(self, message: Message) -> Message:
        if message.msg_type != "CommandMsg":
            return self._error_response(message.phase, "Invalid message type")
        if not isinstance(message.payload, dict):
            return self._error_response(message.phase, "Invalid payload")
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
                acceptance = self._run_acceptance_test(abs_file)
                if acceptance["status"] == "runtime_failure":
                    self.workspace.save_test_result(message.phase, "runtime_failure", json.dumps(acceptance))
                    self.workspace.log_event(f"Tester acceptance failed: {abs_file}: {acceptance['reason']}", message.phase)
                    return Message(sender="tester", receiver="supervisor", msg_type="ResultMsg",
                                   phase=message.phase, payload={"filepath": abs_file, "status": "runtime_failure", "reason": acceptance["reason"]})
                self.workspace.save_test_result(message.phase, "passed", json.dumps({"execution_status": "cli_acceptance_passed"}))
                self.workspace.log_event(f"Tester successfully passed acceptance: {abs_file}", message.phase)
                return Message(sender="tester", receiver="supervisor", msg_type="ResultMsg",
                               phase=message.phase, payload={"filepath": abs_file, "status": "passed", "execution_status": "cli_acceptance_passed"})
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