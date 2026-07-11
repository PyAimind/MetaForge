
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from project_design.code_generator_llm import CodeGeneratorLLM, FALLBACK_CODE

class MockProvider:
    def __init__(self, response):
        self.response = response
    def generate(self, messages, model, temperature):
        return self.response

class FailingProvider:
    def generate(self, messages, model, temperature):
        raise RuntimeError("boom")

try:
    try:
        CodeGeneratorLLM(None)
        assert False
    except TypeError:
        pass
    try:
        CodeGeneratorLLM("not_a_provider")
        assert False
    except TypeError:
        pass
    CodeGeneratorLLM(MockProvider("x"))
    generator = CodeGeneratorLLM(MockProvider("def hello():\n    return 'world'"))
    valid_module_info = {"filename": "test.py", "description": "A test module", "dependencies": [], "purpose": "testing"}
    code = generator.generate(valid_module_info)
    assert code == "def hello():\n    return 'world'"
    compile(code, "test.py", "exec")
    assert generator.generate(None) == FALLBACK_CODE
    assert generator.generate({}) == FALLBACK_CODE
    generator2 = CodeGeneratorLLM(MockProvider(""))
    assert generator2.generate(valid_module_info) == FALLBACK_CODE
    generator3 = CodeGeneratorLLM(MockProvider("def : invalid syntax"))
    assert generator3.generate(valid_module_info) == FALLBACK_CODE
    generator4 = CodeGeneratorLLM(MockProvider(None))
    assert generator4.generate(valid_module_info) == FALLBACK_CODE
    generator5 = CodeGeneratorLLM(MockProvider("```python\ndef hello():\n    return 'world'\n```"))
    code5 = generator5.generate(valid_module_info)
    assert code5 == "def hello():\n    return 'world'"
    gen_fn = CodeGeneratorLLM(MockProvider("x = 1"))
    mod_fn = {"filename": 123, "description": "test", "dependencies": [], "purpose": "test"}
    assert gen_fn.generate(mod_fn) == "x = 1"
    gen_deps = CodeGeneratorLLM(MockProvider("x = 1"))
    mod_deps = {"filename": "t.py", "description": "test", "dependencies": "os", "purpose": "test"}
    code_deps = gen_deps.generate(mod_deps)
    compile(code_deps, "t.py", "exec")
    gen_purpose = CodeGeneratorLLM(MockProvider("x = 1"))
    mod_purpose = {"filename": "t.py", "description": "test", "dependencies": [], "purpose": 123}
    code_purpose = gen_purpose.generate(mod_purpose)
    compile(code_purpose, "t.py", "exec")
    gen_fence = CodeGeneratorLLM(MockProvider("```\ndef hello():\n    return 'world'\n```"))
    code_fence = gen_fence.generate(valid_module_info)
    assert code_fence == "def hello():\n    return 'world'"
    fail_gen = CodeGeneratorLLM(FailingProvider())
    assert fail_gen.generate(valid_module_info) == FALLBACK_CODE
    print("PHASE 10.2 PASSED")
except AssertionError as e:
    print(f"PHASE 10.2 FAILED: {e}")