import json
import os
import shutil
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi.testclient import TestClient

import project_store
import ui.server as server
from ui.runner import RunManager


class TestServer(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="metaforge_server_test_")
        self.projects_dir = os.path.join(self.temp_dir, "projects")
        self.test_store = project_store.ProjectStore(self.projects_dir)

        self._orig_store = server.store
        self._orig_manager = server.manager
        self._orig_projects_dir = server.PROJECTS_DIR

        server.PROJECTS_DIR = self.projects_dir
        server.store = self.test_store
        server.manager = RunManager(self.test_store)

        # Do not spawn a real subprocess: create in store and return the id.
        def fake_start(idea, name):
            return self.test_store.create(name=name, idea=idea)

        server.manager.start = fake_start

        self.client = TestClient(server.app)

    def tearDown(self):
        server.store = self._orig_store
        server.manager = self._orig_manager
        server.PROJECTS_DIR = self._orig_projects_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # ----------------------------------------------------------------
    # Projects CRUD
    # ----------------------------------------------------------------

    def test_list_projects_empty(self):
        r = self.client.get("/api/projects")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])

    def test_create_and_get_project(self):
        r = self.client.post(
            "/api/projects",
            json={"name": "My Project", "idea": "A simple to do app"},
        )
        self.assertEqual(r.status_code, 200)
        project_id = r.json()["id"]
        self.assertTrue(project_id)

        r2 = self.client.get(f"/api/projects/{project_id}")
        self.assertEqual(r2.status_code, 200)
        meta = r2.json()
        self.assertEqual(meta["id"], project_id)
        self.assertEqual(meta["name"], "My Project")
        self.assertEqual(meta["idea"], "A simple to do app")

    def test_rename_project(self):
        project_id = self.test_store.create(name="Old", idea="i")
        r = self.client.patch(
            f"/api/projects/{project_id}",
            json={"name": "New"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"ok": True})
        self.assertEqual(self.test_store.get(project_id)["name"], "New")

    def test_delete_project(self):
        project_id = self.test_store.create(name="X", idea="i")
        r = self.client.delete(f"/api/projects/{project_id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"ok": True})
        self.assertIsNone(self.test_store.get(project_id))

    def test_get_nonexistent_returns_404(self):
        r = self.client.get("/api/projects/does-not-exist")
        self.assertEqual(r.status_code, 404)

    def test_rename_nonexistent_returns_404(self):
        r = self.client.patch(
            "/api/projects/does-not-exist",
            json={"name": "New"},
        )
        self.assertEqual(r.status_code, 404)

    def test_delete_nonexistent_returns_404(self):
        r = self.client.delete("/api/projects/does-not-exist")
        self.assertEqual(r.status_code, 404)

    # ----------------------------------------------------------------
    # Thinking log
    # ----------------------------------------------------------------

    def test_thinking_empty_returns_empty_list(self):
        project_id = self.test_store.create(name="X", idea="i")
        r = self.client.get(f"/api/projects/{project_id}/thinking")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])

    def test_thinking_returns_events(self):
        project_id = self.test_store.create(name="X", idea="i")
        self.test_store.append_event(project_id, {"v": 1, "type": "run_started"})
        self.test_store.append_event(project_id, {"v": 1, "type": "run_completed"})

        r = self.client.get(f"/api/projects/{project_id}/thinking")
        self.assertEqual(r.status_code, 200)
        events = r.json()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["type"], "run_started")
        self.assertEqual(events[1]["type"], "run_completed")

    # ----------------------------------------------------------------
    # Modules
    # ----------------------------------------------------------------

    def test_modules_empty_returns_empty_list(self):
        project_id = self.test_store.create(name="X", idea="i")
        r = self.client.get(f"/api/projects/{project_id}/modules")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])

    def test_modules_lists_files(self):
        project_id = self.test_store.create(name="X", idea="i")
        out_dir = os.path.join(self.projects_dir, project_id, "output")
        with open(os.path.join(out_dir, "a.py"), "w", encoding="utf-8") as f:
            f.write("print('a')\n")
        with open(os.path.join(out_dir, "b.py"), "w", encoding="utf-8") as f:
            f.write("print('b')\n")

        r = self.client.get(f"/api/projects/{project_id}/modules")
        self.assertEqual(r.status_code, 200)
        items = r.json()
        names = [i["name"] for i in items]
        self.assertEqual(names, ["a.py", "b.py"])
        self.assertTrue(all(i["size"] > 0 for i in items))

    def test_get_module_content(self):
        project_id = self.test_store.create(name="X", idea="i")
        out_dir = os.path.join(self.projects_dir, project_id, "output")
        with open(os.path.join(out_dir, "a.py"), "w", encoding="utf-8") as f:
            f.write("print('hello')\n")

        r = self.client.get(f"/api/projects/{project_id}/modules/a.py")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"name": "a.py", "content": "print('hello')\n"})

    def test_get_module_missing_returns_404(self):
        project_id = self.test_store.create(name="X", idea="i")
        r = self.client.get(f"/api/projects/{project_id}/modules/nope.py")
        self.assertEqual(r.status_code, 404)

    def test_path_traversal_blocked(self):
        project_id = self.test_store.create(name="X", idea="i")
        # URL-encoded "../etc/passwd" so httpx does not normalize it client-side.
        r = self.client.get(
            f"/api/projects/{project_id}/modules/%2E%2E%2Fetc%2Fpasswd"
        )
        # Should be 400 (rejected by _is_safe_filename) or 404 (normalized away).
        # Never 200.
        self.assertIn(r.status_code, (400, 404))

    # ----------------------------------------------------------------
    # WebSocket
    # ----------------------------------------------------------------

    @unittest.skip(
        "WebSocket streaming requires a real event loop and a running run; "
        "will be covered by the integration test in a later task."
    )
    def test_websocket_receives_run_started(self):
        pass


if __name__ == "__main__":
    unittest.main()