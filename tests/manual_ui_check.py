"""Smoke test for the served UI shell static files."""

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
PORT = int(os.getenv("METAFORGE_TEST_PORT", "8765"))
BASE = f"http://{HOST}:{PORT}"


def _run_server() -> None:
    config = uvicorn.Config(app, host=HOST, port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None
    server.run()


def _wait(timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(BASE + "/", timeout=1.0)
            if r.status_code == 200:
                return True
        except Exception:
            time.sleep(0.3)
    return False


def main() -> int:
    thread = threading.Thread(target=_run_server, daemon=True)
    thread.start()

    if not _wait(10.0):
        print(f"Server did not start on port {PORT}.")
        return 1

    checks = [
        "/",
        "/static/css/theme.css",
        "/static/css/layout.css",
        "/static/css/components.css",
        "/static/js/app.js",
        "/static/js/api.js",
        "/static/js/galaxy.js",
        "/static/js/home.js",
        "/static/js/project.js",
        "/static/assets/logo.svg",
        "/static/assets/favicon.svg",
    ]
    for path in checks:
        r = httpx.get(BASE + path, timeout=5.0)
        if r.status_code != 200:
            print(f"FAIL: {path} -> {r.status_code}")
            return 1

    r = httpx.get(BASE + "/api/projects", timeout=5.0)
    if r.status_code != 200 or not isinstance(r.json(), list):
        print(f"FAIL: /api/projects -> {r.status_code}")
        return 1

    print("UI shell OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())