import os
import sys
import subprocess
import time

class CodeExecutor:
    def __init__(self):
        pass

    def execute(self, filepath: str, working_directory: str = None, timeout_seconds: int = 10) -> dict:
        if not isinstance(filepath, str) or not filepath.strip() or not os.path.isfile(filepath):
            return {"status": "error", "return_code": -1, "stdout": "", "stderr": "", "execution_time": 0.0}

        if working_directory is None:
            working_directory = os.path.dirname(os.path.abspath(filepath))

        start_time = time.time()
        try:
            result = subprocess.run(
                [sys.executable, filepath],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=working_directory,
                shell=False
            )
            elapsed = time.time() - start_time
            status = "passed" if result.returncode == 0 else "failed"
            return {
                "status": status,
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "execution_time": elapsed
            }
        except subprocess.TimeoutExpired as e:
            elapsed = time.time() - start_time
            stdout = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
            stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
            return {
                "status": "timeout",
                "return_code": -1,
                "stdout": stdout,
                "stderr": stderr,
                "execution_time": elapsed
            }
        except Exception:
            elapsed = time.time() - start_time
            return {
                "status": "error",
                "return_code": -1,
                "stdout": "",
                "stderr": "",
                "execution_time": elapsed
            }