import os
import queue
from communication.message import Message
from communication.message_channel import MessageChannel
from workspace.workspace_manager import WorkspaceManager
import config

class Coder:
    def __init__(self, channel: MessageChannel, workspace: WorkspaceManager):
        if not isinstance(channel, MessageChannel):
            raise TypeError("channel must be a MessageChannel instance")
        if not isinstance(workspace, WorkspaceManager):
            raise TypeError("workspace must be a WorkspaceManager instance")
        self.channel = channel
        self.workspace = workspace

    def _looks_like_prompt(self, text: str) -> bool:
        markers = ["Write a Python file", "### Dependencies", "### Implementation Requirements", "### Strict Constraints"]
        return any(marker in text for marker in markers)

    def _extract_python_code(self, text: str) -> str:
        lines = text.split('\n')
        inside = False
        captured = []
        for line in lines:
            if line.startswith("```python"):
                inside = True
                continue
            if line.startswith("```") and inside:
                break
            if inside:
                captured.append(line)
        return '\n'.join(captured)

    def process_command(self, message: Message) -> Message:
        try:
            if message.msg_type != "CommandMsg":
                return Message(sender="coder", receiver="supervisor", msg_type="ResultMsg",
                               phase=message.phase, payload={"status": "error", "reason": "Invalid message type: expected CommandMsg"})
            filename = message.payload.get("filename", "untitled.py")
            filename = os.path.basename(filename)
            if not filename:
                filename = "untitled.py"
            code = message.payload.get("code")
            if not isinstance(code, str):
                code = ""
            if code and not self._looks_like_prompt(code):
                final_code = code
            elif code and self._looks_like_prompt(code):
                extracted = self._extract_python_code(code)
                if extracted and extracted.strip():
                    final_code = extracted
                else:
                    final_code = "# Placeholder module\ndef placeholder():\n    pass\n"
            else:
                final_code = "# Placeholder module\ndef placeholder():\n    pass\n"
            os.makedirs(config.OUTPUT_DIR, exist_ok=True)
            filepath = os.path.join(config.OUTPUT_DIR, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(final_code)
            self.workspace.log_event(f"Coder wrote file: {filepath}", message.phase)
            return Message(sender="coder", receiver="supervisor", msg_type="ResultMsg",
                           phase=message.phase, payload={"filepath": filepath, "status": "success"})
        except Exception as e:
            phase = getattr(message, "phase", -1)
            self.workspace.log_event(f"Coder error: {e}", phase)
            return Message(sender="coder", receiver="supervisor", msg_type="ResultMsg",
                           phase=phase, payload={"status": "error", "reason": f"{type(e).__name__}: {str(e)}"})

    def step(self) -> bool:
        try:
            msg = self.channel.receive("coder", timeout=0.1)
        except queue.Empty:
            return False
        result = self.process_command(msg)
        self.channel.send(result)
        return True