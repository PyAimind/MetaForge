import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from project_design.contract_fixer import fix_contract

code = "def greet(name):\n    return f'Hello, {name}!'\n"
exports = [
    {
        "name": "greet",
        "kind": "function",
        "parameters": [{"name": "name", "type": "str"}],
        "returns": "str"
    }
]

fixed_code = fix_contract(code, exports)
print("DEBUG fixed_code:", repr(fixed_code))
compile(fixed_code, '<test>', 'exec')
assert "def greet(name: str) -> str:" in fixed_code
assert "return f'Hello, {name}!'\n" in fixed_code

print("PHASE 22 CONTRACT FIXER PASSED")