import sys
import os
import json
import subprocess
import queue
from communication.message import Message
from communication.message_channel import MessageChannel
from workspace.workspace_manager import WorkspaceManager
import config

class Tester:
    def __init__(self, channel: MessageChannel, workspace: WorkspaceManager):
        if not isinstance(channel, MessageChannel):
            raise TypeError("channel must be a MessageChannel instance")
        if not isinstance(workspace, WorkspaceManager):
            raise TypeError("workspace must be a WorkspaceManager instance")
        self.channel = channel
        self.workspace = workspace
        self._current_filepath = ""

    def _error_response(self, phase: int, reason: str) -> Message:
        return Message(sender="tester", receiver="supervisor", msg_type="ResultMsg",
                       phase=phase, payload={"status": "error", "reason": reason})

    def _validate_message(self, message: Message) -> Message:
        if message.msg_type != "CommandMsg":
            return self._error_response(message.phase, "Invalid message type: expected CommandMsg")
        if not isinstance(message.payload, dict):
            return self._error_response(message.phase, "Invalid payload: must be a dict")
        filepath = message.payload.get("filepath")
        if not isinstance(filepath, str) or not filepath:
            return self._error_response(message.phase, "Missing or invalid filepath")
        filepath = os.path.realpath(filepath)
        output_dir_real = os.path.realpath(config.OUTPUT_DIR)
        if os.path.commonpath([output_dir_real, filepath]) != output_dir_real:
            return self._error_response(message.phase, "Filepath outside output directory")
        self._current_filepath = filepath
        return None

    def _build_result(self, result: subprocess.CompletedProcess) -> dict:
        return {"status": "passed" if result.returncode == 0 else "failed",
                "stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}

    def _safe_log(self, exec_result: dict, filepath: str, phase: int) -> None:
        try:
            self.workspace.save_test_result(phase, exec_result["status"],
                                            json.dumps({"stdout": exec_result["stdout"], "stderr": exec_result["stderr"]}))
            self.workspace.log_event(f"Tester {exec_result['status']}: {filepath}", phase)
        except Exception:
            try:
                self.workspace.log_event("Tester failed to log test result", phase)
            except Exception:
                pass

    def step(self) -> bool:
        try:
            msg: Message = self.channel.receive("tester", timeout=0.1)
        except queue.Empty:
            return False
        try:
            result = self.process_command(msg)
        except Exception as e:
            error_result = Message(sender="tester", receiver="supervisor", msg_type="ResultMsg",
                                   phase=msg.phase, payload={"status": "error", "reason": f"{type(e).__name__}: {str(e)}"})
            result = error_result
        self.channel.send(result)
        return True

    def process_command(self, message: Message) -> Message:
        error = self._validate_message(message)
        if error is not None:
            return error
        filepath = self._current_filepath
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        exec_result = self._execute_file(filepath)
        self._safe_log(exec_result, filepath, message.phase)
        return Message(sender="tester", receiver="supervisor", msg_type="ResultMsg",
                       phase=message.phase, payload={"filepath": filepath, "status": exec_result["status"],
                                                     "stdout": exec_result["stdout"], "stderr": exec_result["stderr"],
                                                     "returncode": exec_result["returncode"]})

    def _execute_file(self, filepath: str) -> dict:
        try:
            result = subprocess.run([sys.executable, filepath], capture_output=True, text=True, timeout=5, cwd=config.OUTPUT_DIR)
            return self._build_result(result)
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "stdout": "", "stderr": "Execution timed out after 5 seconds", "returncode": -1}
        except Exception as e:
            return {"status": "error", "stdout": "", "stderr": str(e), "returncode": -1}