import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from project_design.repair_context import RepairContext

ctx = RepairContext("greeter.py", "/tmp/greeter.py")
assert ctx.is_empty() == True

ctx.api_errors = ["Missing return type annotation"]
assert ctx.is_empty() == False

s = ctx.summary()
assert "Repair Target: greeter.py (/tmp/greeter.py)" in s
assert "Previous Attempts: 0" in s
assert "API Errors:" in s
assert "  - Missing return type annotation" in s
assert "Semantic Errors:" not in s

ctx.runtime_error = "AttributeError: 'str' object has no attribute 'name'"
ctx.debugger_analysis = {
    "diagnosis": "MissingAnnotation",
    "root_cause": "LLM ignored contract",
    "suggested_fix": "Add return type annotation",
    "confidence": 0.95
}

s = ctx.summary()
assert "Runtime Error:" in s
assert "AttributeError: 'str' object has no attribute 'name'" in s
assert "Debugger Analysis:" in s
assert "diagnosis:" in s
assert "MissingAnnotation" in s
assert "root_cause:" in s
assert "LLM ignored contract" in s
assert "suggested_fix:" in s
assert "Add return type annotation" in s
assert "confidence:" in s
assert "0.95" in s

ctx2 = RepairContext("test.py", "")
s2 = ctx2.summary()
assert s2.startswith("Repair Target: test.py")
assert "()" not in s2

ctx.current_code = "def greet(name):\n    return 'hi'\n"
s3 = ctx.summary()
assert "def greet(name)" not in s3

ctx.contract = {"exports": [{"name": "greet", "kind": "function"}]}
json.dumps(vars(ctx), ensure_ascii=False)

r = repr(ctx)
assert "greeter.py" in r
assert "filepath=" in r

print("PHASE 1 REPAIR CONTEXT PASSED")