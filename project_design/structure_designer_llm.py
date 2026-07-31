import json
import os

DEFAULT_TEMPLATE = {
    "project_name": "Untitled",
    "description": "Default project structure due to LLM fallback",
    "phases": [
        {
            "phase_number": 1,
            "name": "Core",
            "modules": [
                {
                    "filename": "main.py",
                    "description": "Main entry point",
                    "dependencies": [],
                    "purpose": "main_entry",
                    "exports": [],
                    "required_imports": []
                }
            ]
        }
    ]
}

class StructureDesignerLLM:
    def __init__(self, provider):
        self.provider = provider

    def design(self, idea: str) -> dict:
        if not idea or not idea.strip():
            return json.loads(json.dumps(DEFAULT_TEMPLATE))
        model = os.getenv("LLM_ENGINEER_MODEL", "deepseek/deepseek-chat-v3.1")
        system_prompt = (
            "You are an expert software architect. Follow SOLID principles, high cohesion, low coupling. "
            "Design a minimal project structure for the given idea. Do not invent unnecessary modules. "
            "Prefer simplicity over abstraction. Generate only the files required to implement the idea. "
            "Return ONLY a valid JSON object with this exact structure:\n"
            '{"project_name": "...", "description": "...", "phases": [{"phase_number": 1, "name": "...", '
            '"modules": [{"filename": "...", "description": "...", "dependencies": [...], "purpose": "..."}]}]}\n'
            "Filenames must end with .py, be relative, unique, and not contain path separators. "
            "Dependencies must reference existing filenames. Ensure all fields are non-empty strings.\n"
            "\n"
            "For EVERY module, you MUST also include:\n"
            "\n"
            '· "exports": a list of public functions/classes this module provides.\n'
            '  - For each function, include: "name", "kind" ("function"), "parameters" (list of {name, type}), "returns" (type string or null).\n'
            '  - For each class, include: "name", "kind" ("class"), "constructor" (object with "parameters" list) when a custom init is required, and "methods" (list of method signatures, each with "name", "kind" ("function"), "parameters", "returns").\n'
            '· "required_imports": a list of required imports from dependencies (each with "module" and "names").\n'
            "\n"
            'Example: {"filename":"greeter.py","exports":[{"name":"greet","kind":"function","parameters":[{"name":"name","type":"str"}],"returns":"str"}],"required_imports":[]}\n'
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Idea: {idea.strip()}"}
        ]
        try:
            raw = self.provider.generate(messages, model=model, temperature=0.2)
        except Exception:
            return json.loads(json.dumps(DEFAULT_TEMPLATE))
        try:
            start = raw.find('{')
            end = raw.rfind('}')
            if start == -1 or end == -1:
                raise ValueError("No JSON braces found")
            json_str = raw[start:end+1]
            structure = json.loads(json_str)
            if not isinstance(structure, dict):
                raise ValueError("Parsed result is not a dict")
            if not isinstance(structure.get("project_name"), str) or not structure["project_name"].strip():
                raise ValueError("project_name missing or empty")
            if not isinstance(structure.get("description"), str) or not structure["description"].strip():
                raise ValueError("description missing or empty")
            phases = structure.get("phases")
            if not isinstance(phases, list) or len(phases) == 0:
                raise ValueError("phases must be non-empty list")
            all_filenames = set()
            for phase in phases:
                if not isinstance(phase, dict):
                    raise ValueError("phase is not a dict")
                modules = phase.get("modules", [])
                for mod in modules:
                    if not isinstance(mod, dict):
                        raise ValueError("module is not a dict")
                    fname = mod.get("filename")
                    if not isinstance(fname, str) or not fname.strip():
                        raise ValueError("filename must be non-empty string")
                    if not fname.endswith(".py"):
                        raise ValueError("filename must end with .py")
                    if os.path.isabs(fname) or '..' in fname:
                        raise ValueError("filename is absolute or contains '..'")
                    if '/' in fname or '\\' in fname:
                        raise ValueError("filename must not contain path separators")
                    if fname in all_filenames:
                        raise ValueError("duplicate filename")
                    all_filenames.add(fname)
            if not all_filenames:
                raise ValueError("no valid filenames found")
            for i, phase in enumerate(phases):
                if not isinstance(phase, dict):
                    raise ValueError("phase is not a dict")
                phase_num = phase.get("phase_number")
                if not isinstance(phase_num, int):
                    raise ValueError("phase_number must be an integer")
                if phase_num != i + 1:
                    raise ValueError(f"phase_number must be {i+1}")
                if not isinstance(phase.get("name"), str) or not phase["name"].strip():
                    raise ValueError("phase name missing")
                modules = phase.get("modules")
                if not isinstance(modules, list) or len(modules) == 0:
                    raise ValueError("modules list empty")
                for mod in modules:
                    if not isinstance(mod, dict):
                        raise ValueError("module is not a dict")
                    fname = mod.get("filename")
                    if not isinstance(mod.get("description"), str) or not mod["description"].strip():
                        raise ValueError("module description missing or empty")
                    deps = mod.get("dependencies", [])
                    if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
                        raise ValueError("dependencies must be a list of strings")
                    for dep in deps:
                        if dep not in all_filenames:
                            raise ValueError(f"dependency {dep} not in project filenames")
                        if dep == fname:
                            raise ValueError("module cannot depend on itself")
                    purpose = mod.get("purpose")
                    if not isinstance(purpose, str) or not purpose.strip():
                        raise ValueError("purpose must be a non-empty string")
                    exports = mod.get("exports")
                    if not isinstance(exports, list):
                        exports = []
                    else:
                        valid_exports = []
                        for exp in exports:
                            if not isinstance(exp, dict):
                                continue
                            name = exp.get("name")
                            kind = exp.get("kind")
                            parameters = exp.get("parameters")
                            returns = exp.get("returns")
                            if not isinstance(name, str) or not name.strip():
                                continue
                            if kind not in ("function", "class"):
                                continue
                            if not isinstance(parameters, list):
                                continue
                            valid_params = []
                            for p in parameters:
                                if isinstance(p, dict) and isinstance(p.get("name"), str) and isinstance(p.get("type"), str):
                                    valid_params.append(p)
                            parameters = valid_params
                            if not isinstance(returns, str):
                                returns = "None"
                            entry = {
                                "name": name,
                                "kind": kind,
                                "parameters": parameters,
                                "returns": returns
                            }
                            if "constructor" in exp and isinstance(exp["constructor"], dict):
                                entry["constructor"] = exp["constructor"]
                            if "methods" in exp and isinstance(exp["methods"], list):
                                entry["methods"] = exp["methods"]
                            valid_exports.append(entry)
                        exports = valid_exports
                    mod["exports"] = exports
                    required_imports = mod.get("required_imports")
                    if not isinstance(required_imports, list):
                        required_imports = []
                    else:
                        valid_imports = []
                        for imp in required_imports:
                            if not isinstance(imp, dict):
                                continue
                            module_name = imp.get("module")
                            names = imp.get("names")
                            if not isinstance(module_name, str) or not module_name.strip():
                                continue
                            if not isinstance(names, list) or not names or not all(isinstance(n, str) for n in names):
                                continue
                            valid_imports.append({
                                "module": module_name,
                                "names": names
                            })
                        required_imports = valid_imports
                    mod["required_imports"] = required_imports
            return json.loads(json.dumps(structure))
        except Exception:
            return json.loads(json.dumps(DEFAULT_TEMPLATE))