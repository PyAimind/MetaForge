import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from project_design.prompt_generator import generate_prompt

info = {"filename": "auth.py", "description": "Handles login", "dependencies": ["db.py"]}
out = generate_prompt(info)
assert out.index("### Dependencies") < out.index("### Implementation Requirements")
assert out.index("### Implementation Requirements") < out.index("### Testability")
assert out.index("### Testability") < out.index("### Strict Constraints")
assert out.index("### Strict Constraints") < out.index("### Error Handling")
assert "Write a Python file named `auth.py`." in out
assert "Handles login" in out
assert "The module depends on: db.py." in out
assert "The public API (function signatures, class names) will be provided by the Engineer." in out
assert "Allowed modules: os, sys, json, queue, subprocess, tempfile, datetime." in out
assert "Do not print anything. Use exceptions only." in out

info2 = {"filename": "main.py", "description": "Entry point", "dependencies": []}
out2 = generate_prompt(info2)
assert "This module has no dependencies." in out2
assert "The module depends on:" not in out2

info3 = {"filename": "test.py", "description": "", "dependencies": []}
out3 = generate_prompt(info3)
assert out3.startswith("Write a Python file named `test.py`.\n\n")
assert "### Dependencies" in out3

info4 = {"filename": "test.py", "dependencies": []}
out4 = generate_prompt(info4)
assert "Write a Python file named `test.py`." in out4
assert "### Dependencies" in out4

out5a = generate_prompt({"filename": "a.py", "description": "x", "dependencies": []})
out5b = generate_prompt({"filename": "a.py", "description": "x", "dependencies": []})
assert out5a == out5b

try:
    generate_prompt({"description": "test", "dependencies": []})
    assert False
except ValueError as e:
    assert str(e) == "Invalid module_info: filename is missing or empty"

try:
    generate_prompt({"filename": "", "description": "test", "dependencies": []})
    assert False
except ValueError as e:
    assert str(e) == "Invalid module_info: filename is missing or empty"

for bad in [None, "string", 123]:
    try:
        generate_prompt(bad)
        assert False
    except ValueError as e:
        assert "expected a dictionary" in str(e)

try:
    generate_prompt({"filename": "a.py", "description": 123, "dependencies": []})
    assert False
except ValueError as e:
    assert "description must be a string" in str(e)

try:
    generate_prompt({"filename": "a.py", "description": "test", "dependencies": "not_a_list"})
    assert False
except ValueError as e:
    assert "must be a list" in str(e)

print("PHASE 5.2 PASSED")