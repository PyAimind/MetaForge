import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.api_inspector import APIInspector

def write_file(tmpdir, filename, content):
    path = os.path.join(tmpdir, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return path

with tempfile.TemporaryDirectory() as tmpdir:
    inspector = APIInspector()

    p = write_file(tmpdir, "perfect.py", "def greet(name: str) -> str:\n    return f\"Hello {name}\"\n")
    res = inspector.inspect(p, [{"name":"greet","kind":"function"}])
    assert res == {"valid": True, "errors": []}

    p = write_file(tmpdir, "missing.py", "def hello():\n    pass")
    res = inspector.inspect(p, [{"name":"greet","kind":"function"}])
    assert res["valid"] == False
    assert "Missing export: greet" in res["errors"]

    p = write_file(tmpdir, "mismatch.py", "class Greet:\n    pass")
    res = inspector.inspect(p, [{"name":"Greet","kind":"function"}])
    assert res["valid"] == False
    assert "Export 'Greet' should be a function but is a class" in res["errors"]

    p = write_file(tmpdir, "extra.py", "def greet():\n    pass\ndef extra():\n    pass")
    res = inspector.inspect(p, [{"name":"greet","kind":"function"}])
    assert res["valid"] == False
    assert "Unexpected public symbol: extra" in res["errors"]

    p = write_file(tmpdir, "syntax_error.py", "def greet(\n")
    res = inspector.inspect(p, [{"name":"greet","kind":"function"}])
    assert res["valid"] == False
    assert any("Syntax error" in err for err in res["errors"])

    p = write_file(tmpdir, "empty_exports.py", "def greet():\n    pass")
    res = inspector.inspect(p, [])
    assert res["valid"] == False
    assert "Unexpected public symbol: greet" in res["errors"]

    res = inspector.inspect(os.path.join(tmpdir, "nofile.py"), [{"name":"greet","kind":"function"}])
    assert res["valid"] == False
    assert any("File not found" in err for err in res["errors"])

    content = "def greet():\n    pass\ndef _helper():\n    pass\nclass _Internal:\n    pass\n"
    p = write_file(tmpdir, "private.py", content)
    res = inspector.inspect(p, [{"name":"greet","kind":"function"}])
    assert res == {"valid": True, "errors": []}

    p = write_file(tmpdir, "async_def.py", "async def fetch():\n    pass")
    res = inspector.inspect(p, [{"name":"fetch","kind":"function"}])
    assert res == {"valid": True, "errors": []}

    print("PHASE 19.2 PASSED")