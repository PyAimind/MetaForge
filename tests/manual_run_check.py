"""Manual end-to-end check for the MetaForge v4.0 backend.

Requires a real LLM API key in the environment.

Run: python tests/manual_run_check.py
"""

import os
import sys
import threading
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import httpx
import uvicorn

from ui.server import app


HOST = "127.0.0.1"
PORT = 8765


def _run_server() -> None:
    """Run uvicorn without signal handlers (safe inside a thread)."""
    config = uvicorn.Config(app, host=HOST, port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None
    server.run()


def _wait_for_server(base: str, timeout: float = 15.0) -> bool:
    """Poll until the server responds or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{base}/api/projects", timeout=1.0)
            if r.status_code == 200:
                return True
        except Exception:
            time.sleep(0.3)
    return False


def main() -> int:
    base = f"http://{HOST}:{PORT}"
    thread = threading.Thread(target=_run_server, daemon=True)
    thread.start()

    if not _wait_for_server(base, timeout=15.0):
        print("Server did not start within 15s.")
        return 1

    try:
        resp = httpx.post(
            f"{base}/api/projects",
            json={"name": "Manual Check", "idea": "A simple to do app"},
            timeout=10.0,
        )
        resp.raise_for_status()
        project_id = resp.json()["id"]
    except Exception as exc:
        print(f"Failed to start project: {exc}")
        return 1

    deadline = time.time() + 300
    status = "unknown"
    while time.time() < deadline:
        time.sleep(2.0)
        try:
            resp = httpx.get(f"{base}/api/projects/{project_id}", timeout=5.0)
            resp.raise_for_status()
            status = resp.json().get("status", "unknown")
        except Exception:
            continue
        if status in ("completed", "failed", "interrupted"):
            break

    print(f"Final status: {status}")

    # Best-effort cleanup: stop the subprocess if still running.
    try:
        from ui.server import manager as _mgr
        if _mgr.is_running(project_id):
            _mgr.stop(project_id)
    except Exception:
        pass

    return 0 if status == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())