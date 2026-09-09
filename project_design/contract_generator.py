import json
import os
import config

class ContractGenerator:
    def __init__(self, workspace):
        self.workspace = workspace

    def _normalize_export(self, exp: dict) -> dict:
        if not isinstance(exp, dict):
            return None
        name = exp.get("name")
        kind = exp.get("kind")
        if not isinstance(name, str) or not name.strip():
            return None
        if kind not in ("function", "class"):
            return None

        parameters = exp.get("parameters")
        if not isinstance(parameters, list):
            parameters = []

        returns = exp.get("returns")
        if not isinstance(returns, str) or not returns.strip():
            returns = None

        constructor = None
        if "constructor" in exp:
            constr = exp["constructor"]
            if isinstance(constr, dict) and isinstance(constr.get("parameters"), list):
                constructor = {"parameters": constr["parameters"]}

        methods = exp.get("methods")
        if not isinstance(methods, list):
            methods = []
        else:
            normalized_methods = []
            for method in methods:
                if not isinstance(method, dict):
                    continue
                m_name = method.get("name")
                m_kind = method.get("kind")
                if not isinstance(m_name, str) or not m_name.strip():
                    continue
                if m_kind not in ("function", "class"):
                    continue
                m_params = method.get("parameters")
                if not isinstance(m_params, list):
                    m_params = []
                m_returns = method.get("returns")
                if not isinstance(m_returns, str) or not m_returns.strip():
                    m_returns = None
                normalized_methods.append({
                    "name": m_name,
                    "kind": m_kind,
                    "parameters": m_params,
                    "returns": m_returns,
                    "constructor": None,
                    "methods": []
                })
            methods = normalized_methods

        return {
            "name": name,
            "kind": kind,
            "parameters": parameters,
            "returns": returns,
            "constructor": constructor,
            "methods": methods
        }

    def generate_contracts(self):
        try:
            structure = self.workspace.read_structure()
            if not isinstance(structure, dict) or not isinstance(structure.get("phases"), list):
                return {}
            contracts = {}
            for phase in structure["phases"]:
                for module in phase.get("modules", []):
                    if not isinstance(module, dict):
                        continue
                    filename = module.get("filename")
                    if not filename:
                        continue
                    exports = module.get("exports", [])
                    normalized_exports = []
                    for exp in exports:
                        norm = self._normalize_export(exp)
                        if norm:
                            normalized_exports.append(norm)

                    dependencies = module.get("dependencies", [])
                    if not isinstance(dependencies, list):
                        dependencies = []

                    required_imports = module.get("required_imports", [])
                    if not isinstance(required_imports, list):
                        required_imports = []

                    module_type = module.get("type", "library")
                    if module_type not in ("library", "entrypoint"):
                        module_type = "library"

                    contract = {
                        "module": filename,
                        "type": module_type,
                        "dependencies": dependencies,
                        "exports": normalized_exports,
                        "required_imports": required_imports,
                        "generated": False,
                        "validated": False
                    }
                    contracts[filename] = contract
            try:
                filepath = os.path.join(config.WORKSPACE_DIR, "contracts.json")
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(contracts, f, indent=2)
            except OSError:
                pass
            return contracts
        except Exception:
            return {}