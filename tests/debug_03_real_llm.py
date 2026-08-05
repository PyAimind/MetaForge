import os
import sys
import json
import tempfile
import ast
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT_DIR, '.env'))

print("=== ENV CHECK ===")
print("Root dir:", ROOT_DIR)
print("API Key found:", bool(os.getenv("DEEPSEEK_API_KEY")))
key = os.getenv("DEEPSEEK_API_KEY", "")
print("Key length:", len(key))
print("Base URL:", os.getenv("LLM_BASE_URL", "not set"))

sys.path.insert(0, ROOT_DIR)
import config
from llm_provider import LLMProvider
from project_design.code_generator_llm import CodeGeneratorLLM

class SpyProvider:
    def __init__(self, real_provider):
        self.real_provider = real_provider
        self.last_messages = None
        self.last_raw_response = None

    def generate(self, messages, model, max_tokens=2000, temperature=0.7):
        self.last_messages = messages
        raw = self.real_provider.generate(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature
        )
        self.last_raw_response = raw
        return raw

real_provider = LLMProvider()
health_messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Reply with exactly OK"}
]
try:
    health_response = real_provider.generate(
        messages=health_messages,
        model=os.getenv("LLM_CODER_MODEL", "deepseek/deepseek-chat-v3.1"),
        max_tokens=10,
        temperature=0.0
    )
    print("Health check response:", health_response.strip())
    print(f"Remaining requests: {real_provider.max_requests - real_provider.request_count}")
except Exception as e:
    print(f"FATAL: Health check failed: {e}")
    sys.exit(1)

spy = SpyProvider(real_provider)
cg = CodeGeneratorLLM(spy)

with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")
    os.makedirs(config.WORKSPACE_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    module_info = {
        "filename": "greeter.py",
        "description": "Generates greeting messages",
        "purpose": "greeting",
        "dependencies": [],
        "exports": [
            {
                "name": "greet",
                "kind": "function",
                "parameters": [{"name": "name", "type": "str"}],
                "returns": "str"
            }
        ],
        "required_imports": [],
        "debugger_diagnosis": {},
        "project_context": {}
    }

    code = cg.generate(module_info)

    os.makedirs("debug_output", exist_ok=True)
    if spy.last_messages:
        user_msg = spy.last_messages[1]["content"]
        with open("debug_output/debug_03_prompt.txt", "w", encoding="utf-8") as f:
            f.write(user_msg)
    with open("debug_output/debug_03_generated_code.py", "w", encoding="utf-8") as f:
        f.write(code)
    if spy.last_raw_response is not None:
        with open("debug_output/debug_03_raw_llm_response.txt", "w", encoding="utf-8") as f:
            f.write(spy.last_raw_response)

    if code.strip() == "def placeholder():\n    pass":
        print("WARNING: FALLBACK CODE GENERATED – LLM call likely failed or returned invalid code")
        sys.exit(1)

    print("=== GENERATED CODE ===")
    print(code)
    print("======================")

    exact = "def greet(name: str) -> str:"
    no_annotation = "def greet(name):"
    print(f"Contains exact signature '{exact}': {'YES' if exact in code else 'NO'}")
    print(f"Contains no-annotation signature '{no_annotation}': {'YES' if no_annotation in code else 'NO'}")

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        print(f"Syntax error in generated code: {e}")
    else:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "greet":
                ret_ann = ast.unparse(node.returns) if node.returns else "None"
                print(f"Return annotation: {ret_ann}")
                if node.args.args:
                    first_param = node.args.args[0]
                    param_ann = ast.unparse(first_param.annotation) if first_param.annotation else "None"
                    print(f"Parameter 'name' annotation: {param_ann}")
                break
        else:
            print("Function 'greet' not found in generated code.")

    print(f"Total code length: {len(code)}")