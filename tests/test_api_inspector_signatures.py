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

    p = write_file(tmpdir, "a.py", "def greet(name: str) -> str:\n    return f\"Hello {name}\"\n")
    res = inspector.inspect(p, [{"name":"greet","kind":"function","parameters":[{"name":"name","type":"str"}],"returns":"str"}])
    assert res["valid"] is True

    p = write_file(tmpdir, "b.py", "def greet():\n    pass")
    res = inspector.inspect(p, [{"name":"greet","kind":"function","parameters":[{"name":"name","type":"str"}],"returns":None}])
    assert res["valid"] is False
    assert any("parameter mismatch" in err for err in res["errors"])

    p = write_file(tmpdir, "c.py", "def greet(name: str):\n    return \"Hello\"\n")
    res = inspector.inspect(p, [{"name":"greet","kind":"function","parameters":[{"name":"name","type":"str"}],"returns":"str"}])
    assert res["valid"] is False
    assert any("missing return type annotation" in err for err in res["errors"])

    content_d = "class Calculator:\n    def __init__(self, precision: int):\n        self.precision = precision\n    def add(self, a: float, b: float) -> float:\n        return a + b\n"
    p = write_file(tmpdir, "d.py", content_d)
    exports_d = [{
        "name":"Calculator","kind":"class",
        "constructor":{"parameters":[{"name":"precision","type":"int"}]},
        "methods":[
            {"name":"add","kind":"function","parameters":[{"name":"a","type":"float"},{"name":"b","type":"float"}],"returns":"float"}
        ]
    }]
    res = inspector.inspect(p, exports_d)
    assert res["valid"] is True

    content_e = "class Calculator:\n    def __init__(self, precision: int):\n        self.precision = precision\n"
    p = write_file(tmpdir, "e.py", content_e)
    res = inspector.inspect(p, exports_d)
    assert res["valid"] is False
    assert any("missing method: add" in err for err in res["errors"])

    content_f = "class Calculator:\n    def __init__(self, other_param: int):\n        self.p = other_param\n"
    p = write_file(tmpdir, "f.py", content_f)
    res = inspector.inspect(p, exports_d)
    assert res["valid"] is False
    assert any("constructor parameter mismatch" in err for err in res["errors"])

    content_g = "class Fetcher:\n    async def fetch(self, url: str) -> str:\n        return \"data\"\n"
    p = write_file(tmpdir, "g.py", content_g)
    exports_g = [{
        "name":"Fetcher","kind":"class",
        "methods":[
            {"name":"fetch","kind":"function","parameters":[{"name":"url","type":"str"}],"returns":"str"}
        ]
    }]
    res = inspector.inspect(p, exports_g)
    assert res["valid"] is True

    p = write_file(tmpdir, "h.py", "def greet(name):\n    return \"Hi\"\n")
    res = inspector.inspect(p, [{"name":"greet","kind":"function"}])
    assert res["valid"] is True

    print("PHASE 20.3 PASSED")