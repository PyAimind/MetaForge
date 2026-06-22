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

    def process_command(self, message: Message) -> Message:
        try:
            if message.msg_type != "CommandMsg":
                return Message(sender="coder", receiver="supervisor", msg_type="ResultMsg",
                               phase=message.phase, payload={"status": "error", "reason": "Invalid message type: expected CommandMsg"})
            filename = message.payload.get("filename", "untitled.py")
            code = message.payload.get("code")
            filename = os.path.basename(filename)
            if not filename:
                filename = "untitled.py"
            if not code:
                code = "# simulated code\nprint('Hello from MetaForge')"
            os.makedirs(config.OUTPUT_DIR, exist_ok=True)
            filepath = os.path.join(config.OUTPUT_DIR, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(code)
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