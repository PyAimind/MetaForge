import queue
from communication.message import Message
from communication.message_channel import MessageChannel
from workspace.workspace_manager import WorkspaceManager
from project_design.structure_designer import design_structure
from project_design.prompt_generator import generate_prompt
import config

class Engineer:
    def __init__(self, channel: MessageChannel, workspace: WorkspaceManager):
        if not isinstance(channel, MessageChannel):
            raise TypeError("channel must be a MessageChannel instance")
        if not isinstance(workspace, WorkspaceManager):
            raise TypeError("workspace must be a WorkspaceManager instance")
        self.channel = channel
        self.workspace = workspace

    def _error_response(self, phase, reason):
        return Message(sender="engineer", receiver="supervisor", msg_type="ResultMsg",
                       phase=phase, payload={"status": "error", "reason": reason})

    def _success_response(self, phase, payload):
        base = {"status": "success"}
        base.update(payload)
        return Message(sender="engineer", receiver="supervisor", msg_type="ResultMsg",
                       phase=phase, payload=base)

    def _handle_design_structure(self, payload, phase):
        idea = payload.get("idea")
        if not isinstance(idea, str):
            return self._error_response(phase, "Missing or invalid 'idea'")
        structure = design_structure(idea)
        self.workspace.write_structure(structure)
        self.workspace.log_event(f"Engineer designed structure for: {idea}", phase)
        return self._success_response(phase, {"structure": structure})

    def _handle_generate_prompts(self, payload, phase):
        structure = self.workspace.read_structure()
        if not isinstance(structure, dict) or not structure:
            return self._error_response(phase, "No valid project structure found")
        phases = structure.get("phases", [])
        prompts = {}
        module_count = 0
        for phase_data in phases:
            for module in phase_data.get("modules", []):
                prompt = generate_prompt(module)
                filename = module.get("filename")
                if not filename:
                    filename = f"unnamed_{module_count}"
                prompts[filename] = prompt
                module_count += 1
        self.workspace.log_event(f"Engineer generated prompts for {module_count} modules", phase)
        return self._success_response(phase, {"prompts": prompts})

    def _handle_generate_single_prompt(self, payload, phase):
        module_info = payload.get("module_info")
        if not isinstance(module_info, dict):
            return self._error_response(phase, "Missing or invalid 'module_info'")
        prompt = generate_prompt(module_info)
        return self._success_response(phase, {"prompt": prompt})

    def process_command(self, message: Message) -> Message:
        if message.msg_type != "CommandMsg":
            return self._error_response(message.phase, "Invalid message type: expected CommandMsg")
        if not isinstance(message.payload, dict):
            return self._error_response(message.phase, "Invalid payload: must be a dict")
        action = message.payload.get("action")
        if not action:
            return self._error_response(message.phase, "Missing action")
        try:
            if action == "design_structure":
                return self._handle_design_structure(message.payload, message.phase)
            elif action == "generate_prompts":
                return self._handle_generate_prompts(message.payload, message.phase)
            elif action == "generate_single_prompt":
                return self._handle_generate_single_prompt(message.payload, message.phase)
            else:
                return self._error_response(message.phase, "Unknown action")
        except Exception as e:
            self.workspace.log_event(f"Engineer error: {e}", message.phase)
            return self._error_response(message.phase, f"{type(e).__name__}: {str(e)}")

    def step(self) -> bool:
        try:
            msg = self.channel.receive("engineer", timeout=0.1)
        except queue.Empty:
            return False
        result = self.process_command(msg)
        self.channel.send(result)
        return True