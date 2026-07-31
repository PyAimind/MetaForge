import os
import sys
import json
import tempfile
import ast
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from workspace.workspace_manager import WorkspaceManager
from communication.message_channel import MessageChannel
from agents.supervisor import Supervisor
from agents.engineer import Engineer
from agents.coder import Coder
from agents.tester import Tester
from agents.api_inspector import APIInspector
from project_design.structure_designer_llm import StructureDesignerLLM
from project_design.code_generator_llm import CodeGeneratorLLM

class MockLLMProvider:
    def __init__(self, structure_response, code_response):
        self.structure_response = structure_response
        self.code_response = code_response
        self.calls = 0

    def generate(self, messages, model, temperature):
        self.calls += 1
        if self.calls == 1:
            return self.structure_response
        return self.code_response

class MockExecutor:
    def execute(self, filepath, working_directory=None, timeout_seconds=10, args=None):
        return {"status": "passed", "return_code": 0, "stdout": "", "stderr": "", "execution_time": 0.1}
    def classify_error(self, stderr):
        return "unknown"

structure_json = json.dumps({
    "project_name": "Todo",
    "description": "A simple todo list app",
    "phases": [
        {
            "phase_number": 1,
            "name": "Core",
            "modules": [
                {
                    "filename": "storage.py",
                    "description": "Persistent storage for todo items",
                    "dependencies": [],
                    "purpose": "store and load todos",
                    "exports": [
                        {
                            "name": "Storage",
                            "kind": "class",
                            "constructor": {"parameters": [{"name": "path", "type": "str"}]},
                            "methods": [
                                {"name": "save", "kind": "function", "parameters": [{"name": "todos", "type": "list"}], "returns": "bool"},
                                {"name": "load", "kind": "function", "parameters": [], "returns": "list"}
                            ]
                        }
                    ],
                    "required_imports": []
                }
            ]
        }
    ]
})

storage_code = "import json\nimport os\n\nclass Storage:\n    def __init__(self, path: str):\n        self.path = path\n\n    def save(self, todos: list) -> bool:\n        try:\n            with open(self.path, 'w') as f:\n                json.dump(todos, f)\n            return True\n        except Exception:\n            return False\n\n    def load(self) -> list:\n        try:\n            if os.path.exists(self.path):\n                with open(self.path, 'r') as f:\n                    return json.load(f)\n            return []\n        except Exception:\n            return []\n"

with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")
    os.makedirs(config.WORKSPACE_DIR, exist_ok=True)
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    wm = WorkspaceManager()
    channel = MessageChannel()
    mock_provider = MockLLMProvider(structure_json, storage_code)
    designer = StructureDesignerLLM(mock_provider)
    code_generator = CodeGeneratorLLM(mock_provider)
    mock_executor = MockExecutor()

    engineer = Engineer(channel, wm, designer)
    coder = Coder(channel, wm, code_generator, context_manager=None)
    tester = Tester(channel, wm, mock_executor)
    api_inspector = APIInspector()
    supervisor = Supervisor(channel, wm, debugger=None, api_inspector=api_inspector)

    agents = [engineer, coder, tester]
    supervisor.set_idea("Create a storage module with class-based API")

    iterations = 0
    max_iterations = 200
    while supervisor.status not in ("completed", "error") and iterations < max_iterations:
        supervisor.step()
        for agent in agents:
            agent.step()
        iterations += 1

    if supervisor.status != "completed":
        print("\n=== SUPERVISOR FAILED ===")
        print("STATUS:", supervisor.status)
        print("FIX ATTEMPTS:", supervisor.fix_attempts)

        log_path = config.LOG_FILE
        if os.path.exists(log_path):
            with open(log_path) as f:
                log_data = json.load(f)
                for entry in log_data[-10:]:
                    print(f"  [{entry['timestamp']}] {entry['event']}")

        contracts_path = os.path.join(config.WORKSPACE_DIR, "contracts.json")
        if os.path.exists(contracts_path):
            print("\n=== CONTRACTS ===")
            with open(contracts_path) as f:
                print(json.dumps(json.load(f), indent=2))

        raise AssertionError("Pipeline failed - see diagnostics above")

    contracts_path = os.path.join(config.WORKSPACE_DIR, "contracts.json")
    assert os.path.isfile(contracts_path)
    with open(contracts_path, 'r') as f:
        contracts = json.load(f)
    assert "storage.py" in contracts
    assert contracts["storage.py"]["generated"] == True
    assert contracts["storage.py"]["validated"] == True

    storage_file = os.path.join(config.OUTPUT_DIR, "storage.py")
    assert os.path.isfile(storage_file)
    with open(storage_file, 'r') as f:
        code = f.read()
    compile(code, 'storage.py', 'exec')

    tree = ast.parse(code)
    classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    assert "Storage" in classes
    storage_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Storage":
            storage_class = node
            break
    assert storage_class is not None
    methods = [n.name for n in storage_class.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert "save" in methods and "load" in methods

    print("PHASE 20.5 PASSED")