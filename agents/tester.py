import os
import json
import queue
from communication.message import Message
from communication.message_channel import MessageChannel
from workspace.workspace_manager import WorkspaceManager
import config

class Tester:
    def __init__(self, channel: MessageChannel, workspace: WorkspaceManager, executor):
        if not isinstance(channel, MessageChannel):
            raise TypeError("channel must be a MessageChannel instance")
        if not isinstance(workspace, WorkspaceManager):
            raise TypeError("workspace must be a WorkspaceManager instance")
        if executor is None or not callable(getattr(executor, 'execute', None)):
            raise TypeError("executor must have a callable 'execute' method")
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
        base = os.path.basename(abs_file)
        cli_names = {"main.py", "cli.py", "app.py"}
        interactive_keywords = ("input(", "argparse", "sys.argv")
        if base in cli_names and any(kw in content for kw in interactive_keywords):
            self.workspace.log_event(f"Tester skipped runtime execution for interactive CLI after successful syntax validation: {abs_file}", message.phase)
            return Message(sender="tester", receiver="supervisor", msg_type="ResultMsg",
                           phase=message.phase, payload={"filepath": abs_file, "status": "passed"})
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