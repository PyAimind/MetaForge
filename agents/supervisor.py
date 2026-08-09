import os
import json
import queue
from communication.message import Message
from communication.message_channel import MessageChannel
from workspace.workspace_manager import WorkspaceManager
import config
from agents.debugger import Debugger
from project_design.repair_context import RepairContext

class Supervisor:
    def __init__(self, channel: MessageChannel, workspace: WorkspaceManager, debugger: Debugger = None, api_inspector=None, semantic_analyzer=None):
        if not isinstance(channel, MessageChannel):
            raise TypeError("channel must be a MessageChannel instance")
        if not isinstance(workspace, WorkspaceManager):
            raise TypeError("workspace must be a WorkspaceManager instance")

        self.channel = channel
        self.workspace = workspace
        self.debugger = debugger
        self.api_inspector = api_inspector
        self.semantic_analyzer = semantic_analyzer

        self.idea = ""
        self.status = "idle"
        self.modules = []
        self.current_module_index = 0
        self.prompts = {}
        self.fix_attempts = {}

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

    def _analyze_failure(self, filepath, stderr, stdout, return_code) -> dict:
        if self.debugger is None:
            return {}
        try:
            return self.debugger.analyze_error(filepath, stderr, stdout, return_code)
        except Exception:
            return {}

    def _build_repair_context(self, module_info: dict, filepath: str = "", include_all_modules: bool = False) -> "RepairContext":
        from project_design.repair_context import RepairContext

        mod_key = module_info.get("filename", "unknown.py")
        ctx = RepairContext(mod_key, filepath)
        ctx.previous_attempts = self.fix_attempts.get(mod_key, 0)
        if not isinstance(ctx.api_errors, list):
            ctx.api_errors = []

        if filepath and os.path.isfile(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    ctx.current_code = f.read()
            except Exception:
                pass

        contracts_path = os.path.join(config.WORKSPACE_DIR, "contracts.json")
        all_contracts = {}
        if os.path.isfile(contracts_path):
            try:
                with open(contracts_path, 'r', encoding='utf-8') as f:
                    all_contracts = json.load(f)
            except Exception:
                pass

        ctx.contract = all_contracts.get(mod_key)

        if include_all_modules:
            ctx.all_modules = []
            for name, contract in all_contracts.items():
                if not isinstance(contract, dict) or not contract.get("generated", False):
                    continue
                source_code = None
                module_path = os.path.join(config.OUTPUT_DIR, name)
                if os.path.isfile(module_path):
                    try:
                        with open(module_path, 'r', encoding='utf-8') as f:
                            source_code = f.read()
                    except Exception:
                        pass
                ctx.all_modules.append({
                    "module_name": name,
                    "source_code": source_code,
                    "contract": contract
                })

        return ctx

    def _dependencies_ready(self, module: dict) -> bool:
        contracts_path = os.path.join(config.WORKSPACE_DIR, "contracts.json")
        if not os.path.isfile(contracts_path):
            return len(module.get("dependencies", [])) == 0
        try:
            with open(contracts_path, 'r', encoding='utf-8') as f:
                contracts = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError):
            return False
        deps = module.get("dependencies", [])
        for dep in deps:
            dep_contract = contracts.get(dep)
            if not isinstance(dep_contract, dict) or not (dep_contract.get("generated") and dep_contract.get("validated")):
                return False
        return True

    def step(self) -> bool:
        try:
            if self.status in ("idle", "completed", "error"):
                return False

            if self.status == "designing":
                return self._handle_designing()
            elif self.status == "waiting_for_engineer":
                return self._handle_waiting_for_engineer()
            elif self.status == "waiting_for_dependencies":
                return self._handle_waiting_for_dependencies()
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
            from project_design.contract_generator import ContractGenerator
            ContractGenerator(self.workspace).generate_contracts()
            self.workspace.log_event("Supervisor generated contracts.json")
            self._send_command("engineer", "generate_prompts", {})
            return True

        if "prompts" in msg.payload:
            prompts = msg.payload["prompts"]
            self.prompts.update(prompts)

            if "fixed_module.py" in prompts:
                mod = self.modules[self.current_module_index]
                filename = mod["filename"]
                prompt_text = prompts["fixed_module.py"]
                self.prompts[filename] = prompt_text
                coder_payload = {
                    "filename": filename,
                    "description": mod.get("description", ""),
                    "dependencies": mod.get("dependencies", []),
                    "purpose": mod.get("purpose", ""),
                    "code": prompt_text
                }
                is_repair = msg.payload.get("is_fix", False) or "REPAIR TARGET:" in prompt_text
                if is_repair:
                    coder_payload["is_fix"] = True
                    coder_payload["repair_context"] = msg.payload.get("repair_context", {})
                self._send_command("coder", "code", coder_payload)
                self.status = "waiting_for_coder"
                return True

            dispatched = False
            for i in range(self.current_module_index, len(self.modules)):
                mod = self.modules[i]
                if self._dependencies_ready(mod):
                    self.current_module_index = i
                    prompt = self.prompts.get(mod["filename"], "")
                    coder_payload = {
                        "filename": mod["filename"],
                        "description": mod.get("description", ""),
                        "dependencies": mod.get("dependencies", []),
                        "purpose": mod.get("purpose", ""),
                        "code": prompt
                    }
                    is_repair = msg.payload.get("is_fix", False) or "REPAIR TARGET:" in prompt
                    if is_repair:
                        coder_payload["is_fix"] = True
                        coder_payload["repair_context"] = msg.payload.get("repair_context", {})
                    self._send_command("coder", "code", coder_payload)
                    self.status = "waiting_for_coder"
                    dispatched = True
                    break
            if not dispatched:
                self.status = "waiting_for_dependencies"
            return True

        return True

    def _handle_waiting_for_dependencies(self) -> bool:
        for i in range(self.current_module_index, len(self.modules)):
            mod = self.modules[i]
            if self._dependencies_ready(mod):
                self.current_module_index = i
                prompt = self.prompts.get(mod["filename"], "")
                self._send_command("coder", "code", {
                    "filename": mod["filename"],
                    "description": mod.get("description", ""),
                    "dependencies": mod.get("dependencies", []),
                    "purpose": mod.get("purpose", ""),
                    "code": prompt
                })
                self.status = "waiting_for_coder"
                return True
        return False

    def _handle_waiting_for_coder(self) -> bool:
        try:
            msg = self.channel.receive("supervisor", timeout=0.1)
        except queue.Empty:
            return False

        coder_status = msg.payload.get("status")
        if coder_status == "success":
            filepath = msg.payload.get("filepath", "")
            if self.api_inspector:
                mod_key = self.modules[self.current_module_index]["filename"]
                exports = []
                contracts_path = os.path.join(config.WORKSPACE_DIR, "contracts.json")
                if os.path.isfile(contracts_path):
                    try:
                        with open(contracts_path, 'r', encoding='utf-8') as f:
                            contracts = json.load(f)
                        mod_contract = contracts.get(mod_key, {})
                        exports = mod_contract.get("exports", [])
                    except Exception:
                        pass
                inspect_result = self.api_inspector.inspect(filepath, exports)
                if not inspect_result["valid"]:
                    self.workspace.log_event(
                        f"API Inspector failed for {mod_key}: {inspect_result['errors']}",
                        self.current_module_index + 1
                    )
                    self.fix_attempts[mod_key] = self.fix_attempts.get(mod_key, 0) + 1
                    if self.fix_attempts[mod_key] > 3:
                        self.workspace.log_event(f"Supervisor: Max fix attempts reached for {mod_key}", self.current_module_index + 1)
                        self.status = "error"
                        return True
                    ctx = self._build_repair_context(self.modules[self.current_module_index], filepath)
                    ctx.api_errors = [str(e) for e in inspect_result.get("errors", [])]
                    self._send_command("engineer", "generate_single_prompt", {
                        "module_info": self.modules[self.current_module_index],
                        "is_fix": True,
                        "repair_context": vars(ctx)
                    })
                    self.status = "waiting_for_engineer"
                    return True
            if self.semantic_analyzer:
                mod = self.modules[self.current_module_index]
                mod_key = mod["filename"]
                mod_deps = mod.get("dependencies", [])
                if mod_deps:
                    contracts_path = os.path.join(config.WORKSPACE_DIR, "contracts.json")
                    dep_contracts = {}
                    if os.path.isfile(contracts_path):
                        try:
                            with open(contracts_path, 'r', encoding='utf-8') as f:
                                all_contracts = json.load(f)
                            for dep in mod_deps:
                                if dep in all_contracts:
                                    dep_contracts[dep] = all_contracts[dep]
                        except Exception:
                            pass
                    if dep_contracts:
                        analysis = self.semantic_analyzer.analyze(filepath, dep_contracts)
                        if not analysis["valid"]:
                            self.workspace.log_event(
                                f"Semantic Analyzer failed for {mod_key}: {analysis['errors']}",
                                self.current_module_index + 1
                            )
                            self.fix_attempts[mod_key] = self.fix_attempts.get(mod_key, 0) + 1
                            if self.fix_attempts[mod_key] > 3:
                                self.workspace.log_event(f"Supervisor: Max fix attempts reached for {mod_key}", self.current_module_index + 1)
                                self.status = "error"
                                return True
                            ctx = self._build_repair_context(mod, filepath)
                            ctx.semantic_errors = [str(e) for e in analysis.get("errors", [])]
                            self._send_command("engineer", "generate_single_prompt", {
                                "module_info": mod,
                                "is_fix": True,
                                "repair_context": vars(ctx)
                            })
                            self.status = "waiting_for_engineer"
                            return True
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
            try:
                contracts_path = os.path.join(config.WORKSPACE_DIR, "contracts.json")
                if os.path.isfile(contracts_path):
                    with open(contracts_path, 'r', encoding='utf-8') as f:
                        contracts = json.load(f)
                    mod_key = self.modules[self.current_module_index]["filename"]
                    if mod_key in contracts:
                        contracts[mod_key]["validated"] = True
                    with open(contracts_path, 'w', encoding='utf-8') as f:
                        json.dump(contracts, f, indent=2)
            except Exception:
                pass
            mod_key = self.modules[self.current_module_index]["filename"]
            self.fix_attempts[mod_key] = 0
            self.current_module_index += 1
            if self.current_module_index < len(self.modules):
                self.status = "waiting_for_dependencies"
            else:
                self.status = "completed"
                self.workspace.log_event("Supervisor: project completed successfully")

        elif status in ("failed", "timeout", "runtime_failure"):
            self.workspace.log_event(f"Tester {status} for module index {self.current_module_index}")
            if self.current_module_index < len(self.modules):
                mod = self.modules[self.current_module_index]
                mod_key = mod["filename"]
                self.fix_attempts[mod_key] = self.fix_attempts.get(mod_key, 0) + 1
                if self.fix_attempts[mod_key] > 3:
                    self.workspace.log_event(f"Supervisor: Max fix attempts reached for {mod_key}", self.current_module_index + 1)
                    self.status = "error"
                    return True
                payload = {
                    "module_info": mod,
                    "is_fix": True
                }
                filepath = msg.payload.get("filepath", "")
                stderr = msg.payload.get("stderr", "")
                stdout = msg.payload.get("stdout", "")
                return_code = msg.payload.get("return_code")

                diagnosis = None
                if return_code is not None:
                    diagnosis = self._analyze_failure(filepath, stderr, stdout, return_code)
                    if diagnosis:
                        payload["debugger_diagnosis"] = diagnosis

                ctx = self._build_repair_context(mod, filepath, include_all_modules=(status == "runtime_failure"))
                ctx.runtime_error = f"stderr: {stderr}, stdout: {stdout}, return_code: {return_code}"
                if diagnosis:
                    ctx.debugger_analysis = diagnosis
                if status == "runtime_failure":
                    ctx.api_errors.append(
                        "Product acceptance test failed. The failure may be caused by an "
                        "interface or contract mismatch between multiple modules, not only "
                        "this file. Inspect all related modules to identify the root cause."
                    )
                payload["repair_context"] = vars(ctx)

                self._send_command("engineer", "generate_single_prompt", payload)
                self.status = "waiting_for_engineer"

        return True