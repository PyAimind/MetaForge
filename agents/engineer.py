import os
import json
import queue
from communication.message import Message
from communication.message_channel import MessageChannel
from workspace.workspace_manager import WorkspaceManager
from project_design.prompt_generator import generate_prompt
from memory.knowledge_base import KnowledgeBase

class Engineer:
    def __init__(self, channel: MessageChannel, workspace: WorkspaceManager, designer, knowledge_base: KnowledgeBase = None):
        if not isinstance(channel, MessageChannel):
            raise TypeError("channel must be a MessageChannel instance")
        if not isinstance(workspace, WorkspaceManager):
            raise TypeError("workspace must be a WorkspaceManager instance")
        if not callable(getattr(designer, 'design', None)):
            raise TypeError("designer must have a callable 'design' method")
        self.channel = channel
        self.workspace = workspace
        self.designer = designer
        self.knowledge_base = knowledge_base

    def _error_response(self, phase, reason):
        return Message(sender="engineer", receiver="supervisor", msg_type="ResultMsg",
                       phase=phase, payload={"status": "error", "reason": reason})

    def _success_response(self, phase, payload):
        base = {"status": "success"}
        base.update(payload)
        return Message(sender="engineer", receiver="supervisor", msg_type="ResultMsg",
                       phase=phase, payload=base)

    def process_command(self, message: Message) -> Message:
        if message.msg_type != "CommandMsg":
            return self._error_response(message.phase, "Invalid message type: expected CommandMsg")
        if not isinstance(message.payload, dict) or "action" not in message.payload:
            return self._error_response(message.phase, "Missing or invalid payload")
        action = message.payload["action"]
        try:
            if action == "design_structure":
                return self._handle_design_structure(message.payload, message.phase)
            elif action == "generate_prompts":
                return self._handle_generate_prompts(message.payload, message.phase)
            elif action == "generate_single_prompt":
                return self._handle_generate_single_prompt(message.payload, message.phase)
            else:
                return self._error_response(message.phase, f"Unknown action: {action}")
        except Exception as e:
            self.workspace.log_event(f"Engineer error: {e}", message.phase)
            return self._error_response(message.phase, str(e))

    def _handle_design_structure(self, payload, phase) -> Message:
        idea = payload.get("idea")
        if not isinstance(idea, str) or not idea.strip():
            return self._error_response(phase, "Missing or invalid 'idea'")
        original_idea = idea
        if self.knowledge_base is not None:
            context = self.knowledge_base.get_prompt_context(query=idea, role="engineer")
            if context:
                idea = f"{context}\n\nProject Idea: {idea}"
        try:
            structure = self.designer.design(idea)
            self.workspace.write_structure(structure)
            self.workspace.log_event(f"Engineer designed structure for: {original_idea}", phase)
            return self._success_response(phase, {"structure": structure})
        except Exception as e:
            self.workspace.log_event(f"Design structure failed: {e}", phase)
            return self._error_response(phase, f"Failed to design structure: {str(e)}")

    def _handle_generate_prompts(self, payload, phase) -> Message:
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

    def _handle_generate_single_prompt(self, payload, phase) -> Message:
        module_info = payload.get("module_info")
        if not isinstance(module_info, dict):
            return self._error_response(phase, "Missing or invalid 'module_info'")
        module_info = dict(module_info)
        if "debugger_diagnosis" in payload:
            module_info["debugger_diagnosis"] = payload["debugger_diagnosis"]
        inspection_errors = payload.get("inspection_errors", [])
        if inspection_errors:
            repair_lines = ["\n### API Inspection Failures (modify ONLY the incorrect APIs):"]
            for err in inspection_errors:
                if err is not None:
                    repair_lines.append(f"- {str(err)}")
            repair_lines.append(
                "\nRewrite ONLY the incorrect APIs listed above. "
                "Keep every correct implementation unchanged. "
                "Do not redesign the module, do not rename other symbols, "
                "and do not add new exports beyond what is required."
            )
            diagnosis = module_info.setdefault("debugger_diagnosis", {})
            diagnosis["suggested_fix"] = "\n".join(repair_lines)
        repair_context = payload.get("repair_context")
        if repair_context:
            all_modules = repair_context.get("all_modules")
            if all_modules:
                lines = []
                lines.append("MULTI‑MODULE RUNTIME FAILURE REPAIR")
                lines.append("")
                lines.append("The product acceptance test failed. The root cause may involve several modules.")
                lines.append("Below is the complete source code and contract of every generated module.")
                lines.append("Inspect all files, identify the root cause, and modify only the files that need to change.")
                lines.append("")

                for mod in all_modules:
                    mod_name = mod.get("module_name", "unknown")
                    source = mod.get("source_code") or ""
                    contract = mod.get("contract") or {}
                    lines.append(f"=== MODULE: {mod_name} ===")
                    lines.append("SOURCE CODE:")
                    lines.append("```")
                    lines.append(source)
                    lines.append("```")
                    lines.append("CONTRACT:")
                    lines.append(json.dumps(contract, indent=2))
                    lines.append("")

                lines.append("INSTRUCTION:")
                lines.append("1. Find the root cause of the runtime failure by examining all modules above.")
                lines.append("2. Modify ONLY the files that are incorrect – do not touch correct files.")
                lines.append("2.5. If `cli.py` is among the modified files, ensure its `list` output matches the MANDATORY CLI Output Contract: each todo printed as `<ID> <DESCRIPTION>` (e.g., `1 Test todo`), with no colon after the ID.")
                lines.append("3. Return the FULL corrected code for EVERY modified module.")
                lines.append("4. Format your answer as a JSON object with module filenames as keys and the "
                             "complete corrected source code as values.")
                lines.append("Example: {\"cli.py\": \"...\", \"todo_manager.py\": \"...\"}")

                repair_prompt = "\n".join(lines)
                diagnosis = module_info.setdefault("debugger_diagnosis", {})
                diagnosis["suggested_fix"] = repair_prompt

                filename = module_info.get("filename") or "fixed_module.py"
                response_payload = {"prompts": {filename: repair_prompt}}
                if payload.get("is_fix"):
                    response_payload["is_fix"] = True
                    response_payload["repair_context"] = repair_context
                return self._success_response(phase, response_payload)

            ctx = repair_context
            lines = []
            lines.append(f"REPAIR TARGET: {ctx.get('module_name', 'unknown')} (attempt {ctx.get('previous_attempts', 0) + 1})")
            lines.append("")
            lines.append("CURRENT CODE (must be modified minimally):")
            lines.append("```")
            lines.append(ctx.get('current_code') or '')
            lines.append("```")
            lines.append("")
            lines.append("CONTRACT:")
            lines.append(json.dumps(ctx.get('contract'), indent=2))
            lines.append("")
            lines.append("API ERRORS:")
            api_errors = ctx.get('api_errors', [])
            if api_errors:
                for err in api_errors:
                    if err is not None:
                        lines.append(f"- {str(err)}")
            else:
                lines.append("None")
            lines.append("")
            lines.append("SEMANTIC ERRORS:")
            semantic_errors = ctx.get('semantic_errors', [])
            if semantic_errors:
                for err in semantic_errors:
                    if err is not None:
                        lines.append(f"- {str(err)}")
            else:
                lines.append("None")
            lines.append("")
            lines.append("RUNTIME ERROR:")
            lines.append(ctx.get('runtime_error') or 'None')
            lines.append("")
            lines.append("DEBUGGER ANALYSIS:")
            debugger = ctx.get('debugger_analysis')
            if debugger:
                lines.append(json.dumps(debugger, indent=2))
            else:
                lines.append("None")
            lines.append("")
            lines.append("INSTRUCTION:")
            lines.append("Modify the existing code above ONLY to fix the reported failures.")
            lines.append("Keep all correct code unchanged.")
            lines.append("Do NOT rewrite the whole module.")
            lines.append("Do NOT rename functions or classes unless required by the contract.")
            repair_prompt = "\n".join(lines)
            diagnosis = module_info.setdefault("debugger_diagnosis", {})
            diagnosis["suggested_fix"] = repair_prompt
            filename = module_info.get("filename") or "fixed_module.py"
            response_payload = {"prompts": {filename: repair_prompt}}
            if payload.get("is_fix"):
                response_payload["is_fix"] = True
                response_payload["repair_context"] = repair_context
            return self._success_response(phase, response_payload)

        for key in ("exports", "required_imports", "dependencies", "parameters"):
            if key in module_info and isinstance(module_info[key], list):
                module_info[key] = [item for item in module_info[key] if item is not None]

        prompt = generate_prompt(module_info)
        response_payload = {"prompts": {"fixed_module.py": prompt}}
        if payload.get("is_fix"):
            response_payload["is_fix"] = True
            response_payload["repair_context"] = payload.get("repair_context", {})
        return self._success_response(phase, response_payload)

    def step(self) -> bool:
        try:
            msg = self.channel.receive("engineer", timeout=0.1)
        except queue.Empty:
            return False
        result = self.process_command(msg)
        self.channel.send(result)
        return True