import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from project_design.structure_designer_llm import StructureDesignerLLM, DEFAULT_TEMPLATE

class MockProvider:
    def __init__(self, response):
        self.response = response
        self.called_with = {}

    def generate(self, messages, model, temperature):
        self.called_with = {"messages": messages, "model": model, "temperature": temperature}
        return self.response

valid_json = '{"project_name": "Test", "description": "A test", "phases": [{"phase_number": 1, "name": "Phase1", "modules": [{"filename": "main.py", "description": "Main module", "dependencies": [], "purpose": "main"}]}]}'

designer = StructureDesignerLLM(MockProvider(valid_json))
result = designer.design("Test Project")
assert result["project_name"] == "Test"
assert len(result["phases"]) == 1
assert result["phases"][0]["modules"][0]["filename"] == "main.py"

assert designer.design("") == DEFAULT_TEMPLATE

designer = StructureDesignerLLM(MockProvider("not json"))
assert designer.design("any") == DEFAULT_TEMPLATE

designer = StructureDesignerLLM(MockProvider('{"project_name": "X", "description": "Y"}'))
assert designer.design("any") == DEFAULT_TEMPLATE

designer = StructureDesignerLLM(MockProvider('{"project_name": "X", "description": "Y", "phases": [{"phase_number": 1, "name": "P", "modules": [{"filename": "../../etc/passwd.py", "description": "D", "dependencies": [], "purpose": "p"}]}]}'))
assert designer.design("any") == DEFAULT_TEMPLATE

designer = StructureDesignerLLM(MockProvider('{"project_name": "X", "description": "Y", "phases": [{"phase_number": 1, "name": "P", "modules": [{"filename": "dup.py", "description": "D1", "dependencies": [], "purpose": "p1"}, {"filename": "dup.py", "description": "D2", "dependencies": [], "purpose": "p2"}]}]}'))
assert designer.design("any") == DEFAULT_TEMPLATE

designer = StructureDesignerLLM(MockProvider('{"project_name": "X", "description": "Y", "phases": [{"phase_number": 1, "name": "P", "modules": [{"filename": "self.py", "description": "D", "dependencies": ["self.py"], "purpose": "p"}]}]}'))
assert designer.design("any") == DEFAULT_TEMPLATE

designer = StructureDesignerLLM(MockProvider('{"project_name": "X", "description": "Y", "phases": [{"phase_number": 2, "name": "P", "modules": [{"filename": "main.py", "description": "D", "dependencies": [], "purpose": "p"}]}]}'))
assert designer.design("any") == DEFAULT_TEMPLATE

designer = StructureDesignerLLM(MockProvider('{"project_name": "X", "description": "Y", "phases": [1, 2]}'))
assert designer.design("any") == DEFAULT_TEMPLATE

provider = MockProvider(valid_json)
designer = StructureDesignerLLM(provider)
designer.design("Any Idea")
assert provider.called_with["temperature"] == 0.2
assert provider.called_with["model"] == os.getenv("LLM_ENGINEER_MODEL", "deepseek/deepseek-chat-v3.1")
assert isinstance(provider.called_with["messages"], list) and len(provider.called_with["messages"]) == 2

designer = StructureDesignerLLM(MockProvider('{"project_name": "X", "description": "Y", "phases": [{"phase_number": 1, "name": "P1", "modules": [{"filename": "a.py", "description": "D", "dependencies": [], "purpose": "p"}]}, {"phase_number": 1, "name": "P2", "modules": [{"filename": "b.py", "description": "D", "dependencies": [], "purpose": "p"}]}]}'))
assert designer.design("any") == DEFAULT_TEMPLATE

designer = StructureDesignerLLM(MockProvider('{"project_name": "X", "description": "Y", "phases": [{"phase_number": 1, "name": "P", "modules": ["not a dict"]}]}'))
assert designer.design("any") == DEFAULT_TEMPLATE

print("PHASE 9.2 PASSED")