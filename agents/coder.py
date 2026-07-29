import os
import json
import queue
from communication.message import Message
from communication.message_channel import MessageChannel
from workspace.workspace_manager import WorkspaceManager
from project_design.code_generator_llm import FALLBACK_CODE
from project_design.context_manager import ContextManager
from memory.knowledge_base import KnowledgeBase
import config


class Coder:
    def __init__(self, channel: MessageChannel, workspace: WorkspaceManager,
                 generator: object, context_manager: ContextManager, knowledge_base: KnowledgeBase = None):
        if not isinstance(channel, MessageChannel):
            raise TypeError("channel must be a MessageChannel instance")
        if not isinstance(workspace, WorkspaceManager):
            raise TypeError("workspace must be a WorkspaceManager instance")
        if generator is None or not callable(getattr(generator, 'generate', None)):
            raise TypeError("generator must have a callable 'generate' method")
        if context_manager is not None and not isinstance(context_manager, ContextManager):
            raise TypeError("context_manager must be a ContextManager instance")
        self.channel = channel
        self.workspace = workspace
        self.generator = generator
        self.context_manager = context_manager
        self.knowledge_base = knowledge_base
        self.current_context = {}

    def _load_contract(self, filename: str) -> dict:
        base = os.path.basename(filename)
        contracts_path = os.path.join(config.WORKSPACE_DIR, "contracts.json")
        if not os.path.exists(contracts_path):
            return {}
        try:
            with open(contracts_path, 'r', encoding='utf-8') as f:
                contracts = json.load(f)
            return contracts.get(base, {})
        except (OSError, json.JSONDecodeError, ValueError):
            return {}

    def _build_module_info(self, filename: str, payload: dict, phase: int) -> dict:
        module_info = {
            "filename": filename,
            "description": payload.get("description", ""),
            "dependencies": payload.get("dependencies", []),
            "purpose": payload.get("purpose", "")
        }
        if self.context_manager is not None:
            try:
                other_modules = {k: v for k, v in self.context_manager.modules.items() if k != filename}
                context_info = {"current_module": filename, "generated_modules": other_modules}
                module_info["project_context"] = context_info
            except Exception as e:
                self.workspace.log_event(f"Coder: failed to get project context for {filename}: {e}", phase)
        else:
            module_info["project_context"] = {
                "current_module": filename,
                "generated_modules": {}
            }
        kb_context = ""
        if self.knowledge_base is not None:
            try:
                deps = module_info.get("dependencies", [])
                dep_string = " ".join(deps) if deps else ""
                search_query = " ".join(filter(None, [module_info.get("purpose", ""), module_info.get("description", ""), dep_string]))
                context = self.knowledge_base.get_prompt_context(query=search_query, role="coder")
                if context:
                    kb_context = context
            except Exception as e:
                self.workspace.log_event(f"Coder: failed to get knowledge base context for {filename}: {e}", phase)
        module_info["knowledge_base"] = kb_context
        contract = self._load_contract(filename)
        module_info["exports"] = contract.get("exports", [])
        module_info["required_imports"] = contract.get("required_imports", [])
        return module_info

    def process_command(self, message: Message) -> Message:
        if message.msg_type != "CommandMsg":
            return Message(sender="coder", receiver="supervisor", msg_type="ResultMsg",
                           phase=message.phase, payload={"status": "error", "reason": "Invalid message type"})

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
                module_info = self._build_module_info(filename, payload, message.phase)
                code = self.generator.generate(module_info)
        else:
            module_info = self._build_module_info(filename, payload, message.phase)
            try:
                code = self.generator.generate(module_info)
            except Exception as e:
                self.workspace.log_event(f"Coder generator failed for {filename}: {e}", message.phase)
                code = FALLBACK_CODE

        if code == FALLBACK_CODE:
            self.workspace.log_event(f"Coder used FALLBACK for: {filename}", message.phase)

        if self.context_manager is not None:
            try:
                self.context_manager.add_module(filename, code)
                self.current_context = {"generated_modules": self.context_manager.modules, "module_count": len(self.context_manager.modules)}
            except Exception as e:
                self.workspace.log_event(f"Coder: failed to add module to context for {filename}: {e}", message.phase)

        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        filepath = os.path.join(config.OUTPUT_DIR, filename)

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(code)
            self.workspace.log_event(f"Coder wrote file: {filepath}", message.phase)
            try:
                contracts_path = os.path.join(config.WORKSPACE_DIR, "contracts.json")
                if os.path.isfile(contracts_path):
                    with open(contracts_path, 'r', encoding='utf-8') as cf:
                        contracts = json.load(cf)
                    if filename in contracts:
                        contracts[filename]["generated"] = True
                    with open(contracts_path, 'w', encoding='utf-8') as cf:
                        json.dump(contracts, cf, indent=2)
            except Exception:
                pass
            final_status = "fallback" if code.strip() == FALLBACK_CODE.strip() else "success"
            return Message(sender="coder", receiver="supervisor", msg_type="ResultMsg",
                           phase=message.phase, payload={"filepath": filepath, "status": final_status})
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