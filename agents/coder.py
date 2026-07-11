import os
import json
import queue
from communication.message import Message
from communication.message_channel import MessageChannel
from workspace.workspace_manager import WorkspaceManager
from project_design.code_generator_llm import FALLBACK_CODE
import config

class Coder:
    def __init__(self, channel: MessageChannel, workspace: WorkspaceManager, generator: object):
        if not isinstance(channel, MessageChannel):
            raise TypeError("channel must be a MessageChannel instance")
        if not isinstance(workspace, WorkspaceManager):
            raise TypeError("workspace must be a WorkspaceManager instance")
        if generator is None or not callable(getattr(generator, 'generate', None)):
            raise TypeError("generator must have a callable 'generate' method")
        self.channel = channel
        self.workspace = workspace
        self.generator = generator

    def process_command(self, message: Message) -> Message:
        if message.msg_type != "CommandMsg":
            return Message(sender="coder", receiver="supervisor", msg_type="ResultMsg",
                           phase=message.phase, payload={"status": "error", "reason": "Invalid message type: expected CommandMsg"})
        payload = message.payload
        filename = payload.get("filename", "untitled.py")
        if not isinstance(filename, str) or not filename.strip():
            filename = "untitled.py"
        else:
            filename = os.path.basename(filename.strip())
        if not filename.endswith(".py"):
            filename += ".py"
        provided_code = payload.get("code")
        if isinstance(provided_code, str) and provided_code.strip():
            try:
                compile(provided_code, filename, 'exec')
                code = provided_code
            except Exception:
                self.workspace.log_event(f"Coder: direct code invalid for {filename}, using generator", message.phase)
                module_info = {
                    "filename": filename,
                    "description": payload.get("description", ""),
                    "dependencies": payload.get("dependencies", []),
                    "purpose": payload.get("purpose", "")
                }
                code = self.generator.generate(module_info)
        else:
            module_info = {
                "filename": filename,
                "description": payload.get("description", ""),
                "dependencies": payload.get("dependencies", []),
                "purpose": payload.get("purpose", "")
            }
            try:
                code = self.generator.generate(module_info)
            except Exception as e:
                self.workspace.log_event(f"Coder generator failed for {filename}: {e}", message.phase)
                code = FALLBACK_CODE
        if code == FALLBACK_CODE:
            self.workspace.log_event(f"Coder used FALLBACK for: {filename}", message.phase)
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        filepath = os.path.join(config.OUTPUT_DIR, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(code)
            self.workspace.log_event(f"Coder wrote file: {filepath}", message.phase)
            return Message(sender="coder", receiver="supervisor", msg_type="ResultMsg",
                           phase=message.phase, payload={"filepath": filepath, "status": "success"})
        except Exception as e:
            self.workspace.log_event(f"Coder error: {e}", message.phase)
            return Message(sender="coder", receiver="supervisor", msg_type="ResultMsg",
                           phase=message.phase, payload={"status": "error", "reason": f"{type(e).__name__}: {str(e)}"})

    def step(self) -> bool:
        try:
            msg = self.channel.receive("coder", timeout=0.1)
        except queue.Empty:
            return False
        result = self.process_command(msg)
        self.channel.send(result)
        return True