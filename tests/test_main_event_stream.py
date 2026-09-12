import os
import subprocess
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestMainEventStream(unittest.TestCase):
    """
    End-to-end checks for main.py's structured event stream.

    Running main.py requires a live LLM provider and (optionally) an interactive
    input(). Because of that, these tests are intentionally skipped unless a
    lightweight, non-LLM entrypoint is available. The core behavior of the
    emitter is fully covered by tests/test_event_emitter.py.

    To enable these tests in the future, provide a way to run main.py with:
      - a mock LLM provider (e.g. via an env var such as METAFORGE_MOCK_LLM=1)
      - a non-interactive idea source (e.g. METAFORGE_IDEA env var)
    """

    @unittest.skip(
        "main.py requires a live LLM provider and interactive input; "
        "enable once a mock entrypoint is available. "
        "Emitter logic is covered by tests/test_event_emitter.py."
    )
    def test_structured_disabled_produces_no_json_on_stderr(self):
        env = dict(os.environ)
        env.pop("METAFORGE_STRUCTURED", None)
        env["METAFORGE_IDEA"] = "a simple to do app"
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "main.py")],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        for line in result.stderr.splitlines():
            line = line.strip()
            if not line:
                continue
            self.assertFalse(
                line.startswith("{") and '"run_id"' in line,
                f"Unexpected structured event on stderr: {line!r}",
            )

    @unittest.skip(
        "main.py requires a live LLM provider and interactive input; "
        "enable once a mock entrypoint is available. "
        "Emitter logic is covered by tests/test_event_emitter.py."
    )
    def test_structured_enabled_produces_json_on_stderr(self):
        env = dict(os.environ)
        env["METAFORGE_STRUCTURED"] = "1"
        env["METAFORGE_IDEA"] = "a simple to do app"
        result = subprocess.run(
            [sys.executable, os.path.join(PROJECT_ROOT, "main.py")],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
        stderr_lines = [l for l in result.stderr.splitlines() if l.strip().startswith("{")]
        self.assertGreaterEqual(
            len(stderr_lines), 1,
            f"Expected at least one structured event on stderr. stderr was:\n{result.stderr}"
        )


if __name__ == "__main__":
    unittest.main()