import json
import os
import shutil
import sys
import tempfile
import time
import unittest
import uuid

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from project_store import ProjectStore, VALID_STATUSES


class TestProjectStore(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="metaforge_projects_")
        self.base_dir = os.path.join(self.temp_dir, "projects")
        self.store = ProjectStore(self.base_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # --------------------------------------------------------------
    # create()
    # --------------------------------------------------------------

    def test_create_returns_uuid_string(self):
        project_id = self.store.create(name="Test", idea="An idea")
        self.assertIsInstance(project_id, str)
        self.assertGreater(len(project_id), 0)
        parsed = uuid.UUID(project_id)
        self.assertEqual(str(parsed), project_id)

    def test_create_creates_metadata_and_output_dir(self):
        project_id = self.store.create(name="Test", idea="An idea")
        project_dir = os.path.join(self.base_dir, project_id)
        metadata_path = os.path.join(project_dir, "metadata.json")
        output_dir = os.path.join(project_dir, "output")

        self.assertTrue(os.path.isfile(metadata_path))
        self.assertTrue(os.path.isdir(output_dir))

    def test_create_metadata_fields(self):
        project_id = self.store.create(name="My Project", idea="Build a todo app")
        metadata_path = os.path.join(self.base_dir, project_id, "metadata.json")
        with open(metadata_path, "r", encoding="utf-8") as f:
            meta = json.load(f)

        self.assertEqual(meta["id"], project_id)
        self.assertEqual(meta["name"], "My Project")
        self.assertEqual(meta["idea"], "Build a todo app")
        self.assertEqual(meta["status"], "pending")
        self.assertIsInstance(meta["created_at"], float)
        self.assertIsInstance(meta["updated_at"], float)
        self.assertAlmostEqual(meta["created_at"], meta["updated_at"], places=2)

    def test_create_with_empty_strings(self):
        project_id = self.store.create(name="", idea="")
        self.assertTrue(project_id)
        meta = self.store.get(project_id)
        self.assertEqual(meta["name"], "")
        self.assertEqual(meta["idea"], "")

    # --------------------------------------------------------------
    # list()
    # --------------------------------------------------------------

    def test_list_empty_base_dir(self):
        self.assertEqual(self.store.list(), [])

    def test_list_returns_all_projects(self):
        id1 = self.store.create(name="A", idea="idea A")
        time.sleep(0.01)
        id2 = self.store.create(name="B", idea="idea B")
        time.sleep(0.01)
        id3 = self.store.create(name="C", idea="idea C")

        projects = self.store.list()
        self.assertEqual(len(projects), 3)
        ids = {p["id"] for p in projects}
        self.assertEqual(ids, {id1, id2, id3})

    def test_list_sorted_by_created_at_desc(self):
        id1 = self.store.create(name="Oldest", idea="i1")
        time.sleep(0.02)
        id2 = self.store.create(name="Middle", idea="i2")
        time.sleep(0.02)
        id3 = self.store.create(name="Newest", idea="i3")

        projects = self.store.list()
        ids_in_order = [p["id"] for p in projects]
        self.assertEqual(ids_in_order, [id3, id2, id1])

    def test_list_skips_folders_without_metadata(self):
        valid_id = self.store.create(name="Valid", idea="i")

        orphan_dir = os.path.join(self.base_dir, "orphan-no-metadata")
        os.makedirs(orphan_dir, exist_ok=True)

        broken_dir = os.path.join(self.base_dir, "broken-metadata")
        os.makedirs(broken_dir, exist_ok=True)
        with open(os.path.join(broken_dir, "metadata.json"), "w", encoding="utf-8") as f:
            f.write("{ this is not valid json")

        listy_dir = os.path.join(self.base_dir, "listy-metadata")
        os.makedirs(listy_dir, exist_ok=True)
        with open(os.path.join(listy_dir, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(["not", "a", "dict"], f)

        projects = self.store.list()
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["id"], valid_id)

    # --------------------------------------------------------------
    # get()
    # --------------------------------------------------------------

    def test_get_existing_project(self):
        project_id = self.store.create(name="Test", idea="i")
        meta = self.store.get(project_id)
        self.assertIsNotNone(meta)
        self.assertEqual(meta["id"], project_id)

    def test_get_nonexistent_project(self):
        self.assertIsNone(self.store.get("does-not-exist"))
        self.assertIsNone(self.store.get(""))
        self.assertIsNone(self.store.get(None))

    # --------------------------------------------------------------
    # rename()
    # --------------------------------------------------------------

    def test_rename_updates_name_and_bumps_updated_at(self):
        project_id = self.store.create(name="Old Name", idea="i")
        original = self.store.get(project_id)
        time.sleep(0.02)
        result = self.store.rename(project_id, "New Name")

        self.assertTrue(result)
        meta = self.store.get(project_id)
        self.assertEqual(meta["name"], "New Name")
        self.assertGreater(meta["updated_at"], original["updated_at"])
        self.assertEqual(meta["created_at"], original["created_at"])

    def test_rename_nonexistent_project_returns_false(self):
        self.assertFalse(self.store.rename("does-not-exist", "X"))

    # --------------------------------------------------------------
    # delete()
    # --------------------------------------------------------------

    def test_delete_removes_entire_folder(self):
        project_id = self.store.create(name="Test", idea="i")
        project_dir = os.path.join(self.base_dir, project_id)
        self.assertTrue(os.path.isdir(project_dir))

        result = self.store.delete(project_id)
        self.assertTrue(result)
        self.assertFalse(os.path.exists(project_dir))
        self.assertIsNone(self.store.get(project_id))

    def test_delete_nonexistent_project_returns_false(self):
        self.assertFalse(self.store.delete("does-not-exist"))
        self.assertFalse(self.store.delete(""))

    # --------------------------------------------------------------
    # update_status()
    # --------------------------------------------------------------

    def test_update_status_valid(self):
        project_id = self.store.create(name="Test", idea="i")
        original = self.store.get(project_id)
        time.sleep(0.02)
        result = self.store.update_status(project_id, "running")
        self.assertTrue(result)

        meta = self.store.get(project_id)
        self.assertEqual(meta["status"], "running")
        self.assertGreater(meta["updated_at"], original["updated_at"])

    def test_update_status_all_valid_statuses(self):
        for status in VALID_STATUSES:
            project_id = self.store.create(name="Test", idea="i")
            self.assertTrue(self.store.update_status(project_id, status))
            self.assertEqual(self.store.get(project_id)["status"], status)

    def test_update_status_invalid_rejected(self):
        project_id = self.store.create(name="Test", idea="i")
        original = self.store.get(project_id)

        for bad in ("unknown", "", None, 123, "PENDING"):
            self.assertFalse(self.store.update_status(project_id, bad))
            meta = self.store.get(project_id)
            self.assertEqual(meta["status"], original["status"])
            self.assertEqual(meta["updated_at"], original["updated_at"])

    def test_update_status_nonexistent_project(self):
        self.assertFalse(self.store.update_status("does-not-exist", "running"))

    # --------------------------------------------------------------
    # append_event()
    # --------------------------------------------------------------

    def test_append_event_writes_json_line(self):
        project_id = self.store.create(name="Test", idea="i")
        event = {
            "v": 1,
            "ts": 1234.5,
            "run_id": "abc",
            "type": "run_started",
            "payload": {"idea": "hello"},
        }
        self.assertTrue(self.store.append_event(project_id, event))

        thinking_path = os.path.join(self.base_dir, project_id, "thinking.jsonl")
        self.assertTrue(os.path.isfile(thinking_path))
        with open(thinking_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertTrue(content.endswith("\n"))
        parsed = json.loads(content.strip())
        self.assertEqual(parsed, event)

    def test_append_event_multiple_appends(self):
        project_id = self.store.create(name="Test", idea="i")
        for i in range(3):
            self.store.append_event(project_id, {"i": i})

        thinking_path = os.path.join(self.base_dir, project_id, "thinking.jsonl")
        with open(thinking_path, "r", encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
        self.assertEqual(len(lines), 3)
        for i, line in enumerate(lines):
            self.assertEqual(json.loads(line), {"i": i})

    def test_append_event_preserves_non_ascii(self):
        project_id = self.store.create(name="Test", idea="i")
        event = {"idea": "تبدیل دما"}
        self.assertTrue(self.store.append_event(project_id, event))

        thinking_path = os.path.join(self.base_dir, project_id, "thinking.jsonl")
        with open(thinking_path, "r", encoding="utf-8") as f:
            raw = f.read()
        self.assertIn("تبدیل دما", raw)
        parsed = json.loads(raw.strip())
        self.assertEqual(parsed["idea"], "تبدیل دما")

    def test_append_event_nonexistent_project(self):
        self.assertFalse(self.store.append_event("does-not-exist", {"a": 1}))

    def test_append_event_invalid_event_type(self):
        project_id = self.store.create(name="Test", idea="i")
        self.assertFalse(self.store.append_event(project_id, "not a dict"))
        self.assertFalse(self.store.append_event(project_id, None))
        self.assertFalse(self.store.append_event(project_id, [1, 2, 3]))

    # --------------------------------------------------------------
    # copy_structure() / copy_contracts()
    # --------------------------------------------------------------

    def test_copy_structure_success(self):
        project_id = self.store.create(name="Test", idea="i")
        src = os.path.join(self.temp_dir, "structure_source.json")
        with open(src, "w", encoding="utf-8") as f:
            json.dump({"project_name": "Test"}, f)

        self.assertTrue(self.store.copy_structure(project_id, src))
        dest = os.path.join(self.base_dir, project_id, "structure.json")
        self.assertTrue(os.path.isfile(dest))
        with open(dest, "r", encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"project_name": "Test"})

    def test_copy_structure_missing_source(self):
        project_id = self.store.create(name="Test", idea="i")
        self.assertFalse(self.store.copy_structure(project_id, "/no/such/file.json"))

    def test_copy_structure_nonexistent_project(self):
        src = os.path.join(self.temp_dir, "src.json")
        with open(src, "w", encoding="utf-8") as f:
            f.write("{}")
        self.assertFalse(self.store.copy_structure("does-not-exist", src))

    def test_copy_contracts_success(self):
        project_id = self.store.create(name="Test", idea="i")
        src = os.path.join(self.temp_dir, "contracts_source.json")
        with open(src, "w", encoding="utf-8") as f:
            json.dump({"main.py": {"exports": []}}, f)

        self.assertTrue(self.store.copy_contracts(project_id, src))
        dest = os.path.join(self.base_dir, project_id, "contracts.json")
        self.assertTrue(os.path.isfile(dest))

    def test_copy_contracts_missing_source(self):
        project_id = self.store.create(name="Test", idea="i")
        self.assertFalse(self.store.copy_contracts(project_id, "/no/such/file.json"))

    # --------------------------------------------------------------
    # copy_output()
    # --------------------------------------------------------------

    def test_copy_output_success(self):
        project_id = self.store.create(name="Test", idea="i")

        src_dir = os.path.join(self.temp_dir, "output_src")
        os.makedirs(src_dir, exist_ok=True)
        with open(os.path.join(src_dir, "a.py"), "w", encoding="utf-8") as f:
            f.write("print('a')\n")
        with open(os.path.join(src_dir, "b.py"), "w", encoding="utf-8") as f:
            f.write("print('b')\n")

        self.assertTrue(self.store.copy_output(project_id, src_dir))

        dest_dir = os.path.join(self.base_dir, project_id, "output")
        self.assertTrue(os.path.isfile(os.path.join(dest_dir, "a.py")))
        self.assertTrue(os.path.isfile(os.path.join(dest_dir, "b.py")))
        with open(os.path.join(dest_dir, "a.py"), "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "print('a')\n")

    def test_copy_output_overwrites_existing(self):
        project_id = self.store.create(name="Test", idea="i")

        dest_dir = os.path.join(self.base_dir, project_id, "output")
        os.makedirs(dest_dir, exist_ok=True)
        with open(os.path.join(dest_dir, "a.py"), "w", encoding="utf-8") as f:
            f.write("OLD CONTENT\n")

        src_dir = os.path.join(self.temp_dir, "output_src2")
        os.makedirs(src_dir, exist_ok=True)
        with open(os.path.join(src_dir, "a.py"), "w", encoding="utf-8") as f:
            f.write("NEW CONTENT\n")

        self.assertTrue(self.store.copy_output(project_id, src_dir))
        with open(os.path.join(dest_dir, "a.py"), "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "NEW CONTENT\n")

    def test_copy_output_skips_subdirectories(self):
        project_id = self.store.create(name="Test", idea="i")

        src_dir = os.path.join(self.temp_dir, "output_src_subdir")
        os.makedirs(os.path.join(src_dir, "subdir"), exist_ok=True)
        with open(os.path.join(src_dir, "a.py"), "w", encoding="utf-8") as f:
            f.write("ok")
        with open(os.path.join(src_dir, "subdir", "b.py"), "w", encoding="utf-8") as f:
            f.write("not copied")

        self.assertTrue(self.store.copy_output(project_id, src_dir))

        dest_dir = os.path.join(self.base_dir, project_id, "output")
        self.assertTrue(os.path.isfile(os.path.join(dest_dir, "a.py")))
        self.assertFalse(os.path.exists(os.path.join(dest_dir, "subdir")))

    def test_copy_output_missing_source(self):
        project_id = self.store.create(name="Test", idea="i")
        self.assertFalse(self.store.copy_output(project_id, "/no/such/dir"))

    def test_copy_output_nonexistent_project(self):
        src_dir = os.path.join(self.temp_dir, "output_src3")
        os.makedirs(src_dir, exist_ok=True)
        self.assertFalse(self.store.copy_output("does-not-exist", src_dir))

    # --------------------------------------------------------------
    # Error resilience
    # --------------------------------------------------------------

    def test_all_methods_with_invalid_id(self):
        bad = "nonexistent-id"

        self.assertIsNone(self.store.get(bad))
        self.assertFalse(self.store.rename(bad, "X"))
        self.assertFalse(self.store.delete(bad))
        self.assertFalse(self.store.update_status(bad, "running"))
        self.assertFalse(self.store.append_event(bad, {"a": 1}))
        self.assertFalse(self.store.copy_structure(bad, "/no/such"))
        self.assertFalse(self.store.copy_contracts(bad, "/no/such"))
        self.assertFalse(self.store.copy_output(bad, "/no/such"))

    def test_all_methods_with_none_and_empty(self):
        for bad in (None, "", "   "):
            self.assertIsNone(self.store.get(bad))
            self.assertFalse(self.store.rename(bad, "X"))
            self.assertFalse(self.store.delete(bad))
            self.assertFalse(self.store.update_status(bad, "running"))
            self.assertFalse(self.store.append_event(bad, {"a": 1}))

    def test_constructor_does_not_raise_on_existing_dir(self):
        store2 = ProjectStore(self.base_dir)
        self.assertTrue(os.path.isdir(store2.base_dir))

    def test_constructor_creates_base_dir(self):
        new_base = os.path.join(self.temp_dir, "another_projects_dir")
        self.assertFalse(os.path.exists(new_base))
        ProjectStore(new_base)
        self.assertTrue(os.path.isdir(new_base))


if __name__ == "__main__":
    unittest.main()