import os
import json
from llm_provider import LLMProvider

FALLBACK_CODE = "def placeholder():\n    pass"

class CodeGeneratorLLM:
    def __init__(self, provider):
        if provider is None or not callable(getattr(provider, 'generate', None)):
            raise TypeError("provider must have a callable 'generate' method")
        self.provider = provider

    def generate(self, module_info: dict) -> str:
        if not isinstance(module_info, dict):
            print("CodeGeneratorLLM: invalid module_info, using fallback")
            return FALLBACK_CODE
        filename = module_info.get("filename")
        if not isinstance(filename, str) or not filename.strip():
            filename = "untitled.py"
        else:
            filename = filename.strip()
        description = module_info.get("description")
        if not isinstance(description, str) or not description.strip():
            print("CodeGeneratorLLM: missing description, using fallback")
            return FALLBACK_CODE
        description = description.strip()
        dependencies = module_info.get("dependencies", [])
        if not isinstance(dependencies, list):
            dependencies = []
        purpose = module_info.get("purpose", "")
        if not isinstance(purpose, str):
            purpose = ""
        model = os.getenv("LLM_CODER_MODEL", "deepseek/deepseek-chat-v3.1")
        system_prompt = (
            "You are an expert Python developer. Write clean, modern Python code for a single module.\n\n"
            "CRITICAL RULES FOR TESTABILITY:\n\n"
            "1. The generated Python file MUST run from command line and exit without waiting for user input.\n"
            "2. DO NOT use the input() function.\n"
            "3. If you need to demonstrate behavior, use a if __name__ == \"__main__\": block with hardcoded sample data.\n"
            "4. Only call methods that actually exist on the imported modules. Check the dependency list.\n"
            "5. The code must be valid, compilable Python with no syntax errors.\n"
            "6. Return ONLY the raw Python code. No comments, no markdown fences, no explanations.\n"
        )
        exports = module_info.get("exports", [])
        required_imports = module_info.get("required_imports", [])
        user_message = (
            f"Filename: {filename}\n"
            f"Description: {description}\n"
            f"Purpose: {purpose}\n"
            f"Dependencies: {', '.join(dependencies) if dependencies else 'None'}\n\n"
            "Module Contract:\n"
            f"Exports:\n{json.dumps(exports, indent=2)}\n\n"
            f"Required Imports:\n{json.dumps(required_imports, indent=2)}\n\n"
            "Write the module.\n"
            "FORBIDDEN PATTERNS – API VALIDATION WILL FAIL if you do any of the following:\n"
            "- RENAMING a required export. Export names are immutable API identifiers. If the contract says 'greet', the file MUST contain exactly `def greet(...)`. `def generate_greeting(...)` is invalid.\n"
            "- INVENTING aliases or wrapper functions for required exports.\n"
            "- ADDING `if __name__ == '__main__':` blocks. Generated modules must be importable libraries only.\n"
            "- ADDING extra public symbols not present in the contract.\n"
            "- CHANGING a function into a class or a class into functions unless the contract explicitly requires it.\n"
            "\n"
        )
        project_context = module_info.get("project_context", {})
        generated_modules = project_context.get("generated_modules", {})
        if generated_modules and dependencies:
            context_lines = []
            for mod_name, contract in generated_modules.items():
                if mod_name not in dependencies:
                    continue
                exp_list = contract.get("exports", [])
                if not exp_list:
                    continue
                if not context_lines:
                    context_lines.append("\n### Already‑generated modules (use these exact APIs)")
                context_lines.append(f"\n  Module: {mod_name}")
                for exp in exp_list:
                    name = exp.get("name", "?")
                    kind = exp.get("kind", "function")
                    if kind == "function":
                        params = exp.get("parameters") or []
                        params_str = ", ".join(
                            f"{p.get('name','?')}: {p.get('type','?')}"
                            for p in params if isinstance(p, dict)
                        )
                        returns = exp.get("returns") or "None"
                        context_lines.append(f"    - {name}({params_str}) -> {returns}")
                    elif kind == "class":
                        context_lines.append(f"    - class {name}")
                        constructor = exp.get("constructor")
                        if isinstance(constructor, dict):
                            c_params = constructor.get("parameters") or []
                            c_params_str = ", ".join(
                                f"{p.get('name','?')}: {p.get('type','?')}"
                                for p in c_params if isinstance(p, dict)
                            )
                            context_lines.append(f"        Constructor: __init__({c_params_str})")
                        methods = exp.get("methods") or []
                        for meth in methods:
                            if isinstance(meth, dict):
                                m_name = meth.get("name", "?")
                                m_params = meth.get("parameters") or []
                                m_params_str = ", ".join(
                                    f"{p.get('name','?')}: {p.get('type','?')}"
                                    for p in m_params if isinstance(p, dict)
                                )
                                m_returns = meth.get("returns") or "None"
                                context_lines.append(f"        Method: {m_name}({m_params_str}) -> {m_returns}")
            if context_lines:
                user_message += "\n".join(context_lines)
                user_message += "\n"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        try:
            raw = self.provider.generate(messages, model=model, max_tokens=2000, temperature=0.2)
            if not isinstance(raw, str):
                print("CodeGeneratorLLM: invalid response from LLM, using fallback")
                return FALLBACK_CODE
        except Exception as e:
            print(f"CodeGeneratorLLM: LLM call failed: {type(e).__name__}: {e}")
            return FALLBACK_CODE
        code = raw.strip()
        lines = code.split('\n')
        if lines and lines[0].strip().startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        code = '\n'.join(lines).strip()
        if not code:
            print("CodeGeneratorLLM: empty code from LLM, using fallback")
            return FALLBACK_CODE
        try:
            compile(code, filename, 'exec')
            if len(code.strip()) < 10:
                print("CodeGeneratorLLM: generated code too short, using fallback")
                return FALLBACK_CODE
            return code
        except Exception:
            print("CodeGeneratorLLM: LLM code invalid, using fallback")
            return FALLBACK_CODE