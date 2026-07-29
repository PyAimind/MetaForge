import json
import os
import config

class ContractGenerator:
    def __init__(self, workspace):
        self.workspace = workspace

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
                    contract = {
                        "module": filename,
                        "dependencies": module.get("dependencies", []),
                        "exports": module.get("exports", []),
                        "required_imports": module.get("required_imports", []),
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