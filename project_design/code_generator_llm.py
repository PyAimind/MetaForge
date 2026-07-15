import os
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
        user_message = (
            f"Filename: {filename}\n"
            f"Description: {description}\n"
            f"Purpose: {purpose}\n"
            f"Dependencies: {', '.join(dependencies) if dependencies else 'None'}\n"
            "Write the module."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        try:
            raw = self.provider.generate(messages, model=model, temperature=0.2)
            if not isinstance(raw, str):
                print("CodeGeneratorLLM: invalid response from LLM, using fallback")
                return FALLBACK_CODE
        except Exception:
            print("CodeGeneratorLLM: LLM call failed, using fallback")
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
            if len(code.strip()) < 50:
                print("CodeGeneratorLLM: generated code too short, using fallback")
                return FALLBACK_CODE
            return code
        except Exception:
            print("CodeGeneratorLLM: LLM code invalid, using fallback")
            return FALLBACK_CODE