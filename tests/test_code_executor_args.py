import sys
import os
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from project_design.code_executor import CodeExecutor

def write_file(tmpdir, filename, content):
    path = os.path.join(tmpdir, filename)
    with open(path, 'w') as f:
        f.write(content)
    return path

with tempfile.TemporaryDirectory() as tmp:
    executor = CodeExecutor()
    p = write_file(tmp, "hello.py", "print('hello')")
    r = executor.execute(p)
    assert r["status"] == "passed" and "hello" in r["stdout"]

    p = write_file(tmp, "cli.py", "import sys\nif '--help' in sys.argv:\n    print('Usage: cli.py [--help]')\n    sys.exit(0)\n")
    r = executor.execute(p, args=["--help"])
    assert r["status"] == "passed" and "Usage" in r["stdout"]

    p = write_file(tmp, "argv.py", "import sys; print(len(sys.argv))")
    r = executor.execute(p)
    assert "1" in r["stdout"]
    r = executor.execute(p, args=["A", "B"])
    assert "3" in r["stdout"]

    print("TEST PASSED")