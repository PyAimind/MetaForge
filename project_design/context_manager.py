import copy

class ContextManager:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.modules = {}

    def add_module(self, filename: str, code: str = None):
        import json
        import os
        import config

        contracts_path = os.path.join(config.WORKSPACE_DIR, "contracts.json")
        if not os.path.isfile(contracts_path):
            return

        try:
            with open(contracts_path, 'r', encoding='utf-8') as f:
                contracts = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError):
            return

        basename = os.path.basename(filename)
        if basename in contracts:
            self.modules[basename] = contracts[basename]

    def get_context_for_module(self, module_filename: str) -> dict:
        import os
        basename = os.path.basename(module_filename)
        return {
            name: copy.deepcopy(contract)
            for name, contract in self.modules.items()
            if name != basename
        }