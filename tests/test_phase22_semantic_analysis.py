import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.semantic_analyzer import SemanticAnalyzer

CONTRACT = {
    "storage.py": {
        "exports": [
            {
                "name": "Storage",
                "kind": "class",
                "constructor": {
                    "parameters": [
                        {"name": "path", "type": "str"}
                    ]
                },
                "methods": [
                    {
                        "name": "save",
                        "kind": "function",
                        "parameters": [
                            {"name": "todos", "type": "list"}
                        ],
                        "returns": "bool"
                    },
                    {
                        "name": "load",
                        "kind": "function",
                        "parameters": [],
                        "returns": "list"
                    }
                ]
            },
            {
                "name": "get_version",
                "kind": "function",
                "parameters": [],
                "returns": "str"
            }
        ]
    }
}

def write_file(tmpdir, filename, content):
    path = os.path.join(tmpdir, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return path

with tempfile.TemporaryDirectory() as tmpdir:
    analyzer = SemanticAnalyzer()

    p = write_file(tmpdir, "a.py", "from storage import Storage\ndb = Storage(\"data.json\")\ndb.save([])\ndb.load()\n")
    res = analyzer.analyze(p, CONTRACT)
    assert res["valid"] == True
    assert res["errors"] == []

    p = write_file(tmpdir, "b.py", "from storage import Storage\ndb = Storage(\"data.json\")\ndb.fake()\n")
    res = analyzer.analyze(p, CONTRACT)
    assert res["valid"] == False
    assert any(e.get("type") == "missing_method" and e.get("class") == "Storage" and e.get("function") == "fake" for e in res["errors"])

    p = write_file(tmpdir, "c.py", "from storage import Storage\ndb = Storage()\n")
    res = analyzer.analyze(p, CONTRACT)
    assert res["valid"] == False
    assert any(e.get("type") == "argument_count_mismatch" and e.get("class") == "Storage" and e.get("function") == "__init__" for e in res["errors"])

    p = write_file(tmpdir, "d.py", "from storage import Storage\ndb = Storage(\"data.json\")\ndb.save()\n")
    res = analyzer.analyze(p, CONTRACT)
    assert res["valid"] == False
    assert any(e.get("type") == "argument_count_mismatch" and e.get("class") == "Storage" and e.get("function") == "save" for e in res["errors"])

    p = write_file(tmpdir, "e.py", "from storage import Storage\ndb = Storage(\"data.json\")\ndb.save(todos=[], extra=1)\n")
    res = analyzer.analyze(p, CONTRACT)
    assert res["valid"] == False
    assert any(e.get("type") == "unexpected_keyword_argument" and "extra" in str(e.get("received", [])) for e in res["errors"])

    p = write_file(tmpdir, "f.py", "import storage\ndb = storage.Storage(\"data.json\")\ndb.load()\n")
    res = analyzer.analyze(p, CONTRACT)
    assert res["valid"] == True

    p = write_file(tmpdir, "g.py", "from storage import get_version\nget_version()\n")
    res = analyzer.analyze(p, CONTRACT)
    assert res["valid"] == True

    p = write_file(tmpdir, "h.py", "def broken(\n")
    res = analyzer.analyze(p, CONTRACT)
    assert res["valid"] == False
    assert any(e.get("type") == "syntax_error" for e in res["errors"])

    p = write_file(tmpdir, "i.py", "import storage as st\nfrom storage import Storage as DB\ndb = st.Storage(\"data.json\")\ndb2 = DB(\"data.json\")\ndb.save([])\ndb2.load()\n")
    res = analyzer.analyze(p, CONTRACT)
    assert res["valid"] == True

    print("PHASE 22 PASSED")