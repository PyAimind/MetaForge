import os
import json
import queue
from communication.message import Message
from communication.message_channel import MessageChannel
from workspace.workspace_manager import WorkspaceManager
import config

class Supervisor:
    def __init__(self, channel: MessageChannel, workspace: WorkspaceManager):
        if not isinstance(channel, MessageChannel):
            raise TypeError("channel must be a MessageChannel instance")
        if not isinstance(workspace, WorkspaceManager):
            raise TypeError("workspace must be a WorkspaceManager instance")

        self.channel = channel
        self.workspace = workspace

        self.idea = ""
        self.status = "idle"
        self.modules = []
        self.current_module_index = 0
        self.prompts = {}

    def set_idea(self, idea: str) -> None:
        self.idea = idea
        self.status = "designing"
        self.workspace.log_event(f"Supervisor received idea: {idea}")

    def _send_command(self, receiver: str, action: str, payload: dict) -> None:
        msg = Message(
            sender="supervisor",
            receiver=receiver,
            msg_type="CommandMsg",
            phase=self.current_module_index + 1,
            payload={"action": action, **payload}
        )
        self.channel.send(msg)

    def step(self) -> bool:
        try:
            if self.status in ("idle", "completed", "error"):
                return False

            if self.status == "designing":
                return self._handle_designing()
            elif self.status == "waiting_for_engineer":
                return self._handle_waiting_for_engineer()
            elif self.status == "waiting_for_coder":
                return self._handle_waiting_for_coder()
            elif self.status == "waiting_for_tester":
                return self._handle_waiting_for_tester()

            return False

        except Exception as e:
            self.workspace.log_event(f"Supervisor error: {e}")
            self.status = "error"
            return False

    def _handle_designing(self) -> bool:
        self._send_command("engineer", "design_structure", {"idea": self.idea})
        self.status = "waiting_for_engineer"
        self.workspace.log_event("Supervisor sent design request to Engineer")
        return True

    def _handle_waiting_for_engineer(self) -> bool:
        try:
            msg = self.channel.receive("supervisor", timeout=0.1)
        except queue.Empty:
            return False

        if msg.payload.get("status") != "success":
            self.workspace.log_event(f"Engineer error: {msg.payload.get('reason', '')}")
            self.status = "error"
            return True

        if "structure" in msg.payload:
            structure = msg.payload["structure"]
            self.modules = []
            for phase in structure.get("phases", []):
                for mod in phase.get("modules", []):
                    self.modules.append(mod)

            self.workspace.log_event("Supervisor received structure from Engineer")
            self._send_command("engineer", "generate_prompts", {})
            return True

        if "prompts" in msg.payload:
            self.prompts.update(msg.payload["prompts"])

            if self.current_module_index < len(self.modules):
                mod = self.modules[self.current_module_index]
                prompt = self.prompts.get(mod["filename"], "")
                self._send_command("coder", "code", {
                    "filename": mod["filename"],
                    "description": mod.get("description", ""),
                    "dependencies": mod.get("dependencies", []),
                    "purpose": mod.get("purpose", ""),
                    "code": prompt
                })
                self.status = "waiting_for_coder"
            else:
                self.status = "completed"

        return True

    def _handle_waiting_for_coder(self) -> bool:
        try:
            msg = self.channel.receive("supervisor", timeout=0.1)
        except queue.Empty:
            return False

        coder_status = msg.payload.get("status")
        if coder_status == "success":
            filepath = msg.payload.get("filepath", "")
            self._send_command("tester", "test", {"filepath": filepath})
            self.status = "waiting_for_tester"
        elif coder_status == "fallback":
            filename = os.path.basename(msg.payload.get("filepath", ""))
            self.workspace.log_event(f"Supervisor: Coder used fallback code for module '{filename}'", self.current_module_index + 1)
            self.status = "error"
            return True
        else:
            self.workspace.log_event(f"Coder error: {msg.payload.get('reason', '')}")
            if self.current_module_index < len(self.modules):
                mod = self.modules[self.current_module_index]
                self._send_command("engineer", "generate_single_prompt", {
                    "module_info": mod,
                    "is_fix": True
                })
                self.status = "waiting_for_engineer"

        return True

    def _handle_waiting_for_tester(self) -> bool:
        try:
            msg = self.channel.receive("supervisor", timeout=0.1)
        except queue.Empty:
            return False

        status = msg.payload.get("status")

        if status == "passed":
            self.current_module_index += 1
            if self.current_module_index < len(self.modules):
                mod = self.modules[self.current_module_index]
                prompt = self.prompts.get(mod["filename"], "")
                self._send_command("coder", "code", {
                    "filename": mod["filename"],
                    "description": mod.get("description", ""),
                    "dependencies": mod.get("dependencies", []),
                    "purpose": mod.get("purpose", ""),
                    "code": prompt
                })
                self.status = "waiting_for_coder"
            else:
                self.status = "completed"
                self.workspace.log_event("Supervisor: project completed successfully")

        elif status in ("failed", "timeout"):
            self.workspace.log_event(f"Tester {status} for module index {self.current_module_index}")
            if self.current_module_index < len(self.modules):
                mod = self.modules[self.current_module_index]
                self._send_command("engineer", "generate_single_prompt", {
                    "module_info": mod,
                    "is_fix": True
                })
                self.status = "waiting_for_engineer"

        return True
