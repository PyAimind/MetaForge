import sys
import os
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from project_design.context_manager import ContextManager

def create_file(tmpdir, filename, content):
    path = os.path.join(tmpdir, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return path

def test_add_module_basic():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = ContextManager(tmp)
        code = "import os\nfrom math import sqrt\n\nclass Calculator:\n    def add(self, a, b):\n        return a + b\n\ndef multiply(a, b):\n    return a * b\n"
        create_file(tmp, "calculator.py", code)
        with open(os.path.join(tmp, "calculator.py"), 'r', encoding='utf-8') as f:
            file_code = f.read()
        ctx.add_module("calculator.py", file_code)
        mod = ctx.modules["calculator.py"]
        assert mod["classes"] == ["Calculator"]
        assert mod["functions"] == ["multiply"]
        assert mod["imports"] == ["os", "math"]
        assert mod["exports"] == ["Calculator", "multiply"]
        assert mod["dependencies"] == []

def test_add_module_empty_file():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = ContextManager(tmp)
        create_file(tmp, "empty.py", "")
        with open(os.path.join(tmp, "empty.py"), 'r', encoding='utf-8') as f:
            code = f.read()
        ctx.add_module("empty.py", code)
        mod = ctx.modules["empty.py"]
        for key in ("classes", "functions", "imports", "exports", "dependencies"):
            assert mod[key] == []

def test_add_module_syntax_error():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = ContextManager(tmp)
        create_file(tmp, "broken.py", "def : invalid syntax")
        with open(os.path.join(tmp, "broken.py"), 'r', encoding='utf-8') as f:
            code = f.read()
        try:
            ctx.add_module("broken.py", code)
        except Exception as e:
            assert False, f"add_module raised exception: {e}"
        assert "broken.py" not in ctx.modules

def test_add_module_overwrite():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = ContextManager(tmp)
        code1 = "def first(): pass"
        create_file(tmp, "mod.py", code1)
        with open(os.path.join(tmp, "mod.py"), 'r', encoding='utf-8') as f:
            ctx.add_module("mod.py", f.read())
        code2 = "def second(): pass"
        create_file(tmp, "mod.py", code2)
        with open(os.path.join(tmp, "mod.py"), 'r', encoding='utf-8') as f:
            ctx.add_module("mod.py", f.read())
        mod = ctx.modules["mod.py"]
        assert mod["functions"] == ["second"]

def test_add_module_unicode():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = ContextManager(tmp)
        code = "# coding: utf-8\ndef сумма(a, b): return a + b\n"
        create_file(tmp, "unicode.py", code)
        with open(os.path.join(tmp, "unicode.py"), 'r', encoding='utf-8') as f:
            ctx.add_module("unicode.py", f.read())
        mod = ctx.modules["unicode.py"]
        assert mod["functions"] == ["сумма"]

def test_get_context_empty():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = ContextManager(tmp)
        assert ctx.modules == {}

def test_get_context_for_module():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = ContextManager(tmp)
        code_a = "def fa(): pass"
        create_file(tmp, "a.py", code_a)
        with open(os.path.join(tmp, "a.py"), 'r', encoding='utf-8') as f:
            ctx.add_module("a.py", f.read())
        code_b = "def fb(): pass"
        create_file(tmp, "b.py", code_b)
        with open(os.path.join(tmp, "b.py"), 'r', encoding='utf-8') as f:
            ctx.add_module("b.py", f.read())
        assert "a.py" in ctx.modules
        assert "b.py" in ctx.modules
        assert len(ctx.modules) == 2

tests = [
    test_add_module_basic,
    test_add_module_empty_file,
    test_add_module_syntax_error,
    test_add_module_overwrite,
    test_add_module_unicode,
    test_get_context_empty,
    test_get_context_for_module,
]

for test in tests:
    try:
        test()
    except AssertionError as e:
        print(f"PHASE 14.2 FAILED: {e}")
        sys.exit(1)

print("PHASE 14.2 PASSED")