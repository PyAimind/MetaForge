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

try:
    with tempfile.TemporaryDirectory() as tmpdir:
        executor = CodeExecutor()
        p = write_file(tmpdir, "success.py", "print('hello')")
        r = executor.execute(p)
        assert r["status"] == "passed"
        assert r["return_code"] == 0
        assert "hello" in r["stdout"]
        assert r["execution_time"] > 0
        p = write_file(tmpdir, "fail.py", "import sys; sys.exit(1)")
        r = executor.execute(p)
        assert r["status"] == "failed"
        assert r["return_code"] == 1
        p = write_file(tmpdir, "slow.py", "import time; time.sleep(5)")
        r = executor.execute(p, timeout_seconds=1)
        assert r["status"] == "timeout"
        assert r["return_code"] == -1
        r = executor.execute(os.path.join(tmpdir, "nonexistent.py"))
        assert r["status"] == "error"
        assert r["return_code"] == -1
        r = executor.execute(None)
        assert r["status"] == "error"
        r = executor.execute("")
        assert r["status"] == "error"
        p = write_file(tmpdir, "dirtest.py", "import os; print(os.getcwd())")
        r = executor.execute(p, working_directory=tmpdir)
        assert r["status"] == "passed"
        assert os.path.abspath(tmpdir) in r["stdout"]
        expected_keys = {"status", "return_code", "stdout", "stderr", "execution_time"}
        assert set(r.keys()) == expected_keys
        print("PHASE 11.2 PASSED")
except AssertionError:
    print("PHASE 11.2 FAILED")
except Exception as e:
    print("PHASE 11.2 FAILED")