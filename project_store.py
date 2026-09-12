"""
Persistent project storage for MetaForge v4.0.

Each project is stored under:

    projects/<project_id>/
        metadata.json
        structure.json      (optional, copied later)
        contracts.json      (optional, copied later)
        thinking.jsonl      (appended over time)
        output/             (module files)

This module has no dependencies on MetaForge agents, config, or the UI.
It is intentionally minimal and never raises exceptions from its public API.
"""

import json
import os
import shutil
import time
import uuid
from typing import Optional


VALID_STATUSES = ("pending", "running", "completed", "failed", "interrupted")


class ProjectStore:
    """
    Simple, filesystem-backed store for MetaForge projects.

    All public methods are non-raising: they return True/False, a value, or
    None to indicate failure. This makes it safe to call from the UI and the
    runner without try/except around every call.

    A project is considered to exist only if its metadata.json is present
    and readable. Folders without metadata are ignored by list() and
    treated as non-existent by every public method.
    """

    def __init__(self, base_dir: str) -> None:
        self.base_dir = base_dir
        try:
            os.makedirs(self.base_dir, exist_ok=True)
        except Exception:
            # If we can't create the base directory, the store will simply
            # behave as if no projects exist. Do not raise.
            pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _project_dir(self, project_id: str) -> str:
        return os.path.join(self.base_dir, project_id)

    def _metadata_path(self, project_id: str) -> str:
        return os.path.join(self._project_dir(project_id), "metadata.json")

    def _read_metadata(self, project_id: str) -> Optional[dict]:
        path = self._metadata_path(project_id)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return None
            return data
        except Exception:
            return None

    def _write_metadata(self, project_id: str, metadata: dict) -> bool:
        path = self._metadata_path(project_id)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def _exists(self, project_id: str) -> bool:
        """
        A project exists only if its metadata.json is present and readable.
        This prevents orphan folders (created but never fully written) from
        being treated as valid projects.
        """
        if not isinstance(project_id, str) or not project_id.strip():
            return False
        return os.path.isfile(self._metadata_path(project_id))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(self, name: str, idea: str) -> str:
        """
        Create a new project with a fresh UUID v4.

        Writes metadata.json with status="pending" and creates output/.
        Returns the project_id. On failure, returns "".
        """
        try:
            project_id = str(uuid.uuid4())
            project_dir = self._project_dir(project_id)
            output_dir = os.path.join(project_dir, "output")
            os.makedirs(output_dir, exist_ok=True)

            now = time.time()
            metadata = {
                "id": project_id,
                "name": str(name) if name is not None else "",
                "idea": str(idea) if idea is not None else "",
                "status": "pending",
                "created_at": now,
                "updated_at": now,
            }
            if not self._write_metadata(project_id, metadata):
                # Roll back the partially created directory so we don't
                # leave an orphan folder behind.
                shutil.rmtree(project_dir, ignore_errors=True)
                return ""
            return project_id
        except Exception:
            return ""

    def list(self) -> list[dict]:
        """
        Return metadata dicts for all projects, sorted by created_at desc.
        Skips folders without a valid metadata.json. Never raises.
        """
        results: list[dict] = []
        try:
            if not os.path.isdir(self.base_dir):
                return []
            for entry in os.listdir(self.base_dir):
                project_id = entry
                meta = self._read_metadata(project_id)
                if meta is None:
                    continue
                # Ensure required fields are present; otherwise skip.
                if "id" not in meta or "created_at" not in meta:
                    continue
                results.append(meta)
        except Exception:
            return []

        try:
            results.sort(key=lambda m: m.get("created_at", 0.0), reverse=True)
        except Exception:
            pass
        return results

    def get(self, project_id: str) -> Optional[dict]:
        """Return metadata for a project, or None if not found."""
        if not self._exists(project_id):
            return None
        return self._read_metadata(project_id)

    def rename(self, project_id: str, new_name: str) -> bool:
        """Update the 'name' field and bump updated_at. Returns False if not found."""
        meta = self.get(project_id)
        if meta is None:
            return False
        meta["name"] = str(new_name) if new_name is not None else ""
        meta["updated_at"] = time.time()
        return self._write_metadata(project_id, meta)

    def delete(self, project_id: str) -> bool:
        """
        Delete the entire project folder.

        Safe to call on a running project: this only removes the directory.
        The caller is responsible for stopping the run first.
        """
        if not self._exists(project_id):
            return False
        try:
            shutil.rmtree(self._project_dir(project_id))
            return True
        except Exception:
            return False

    def update_status(self, project_id: str, status: str) -> bool:
        """Update 'status' and bump updated_at. Returns False if invalid or not found."""
        if status not in VALID_STATUSES:
            return False
        meta = self.get(project_id)
        if meta is None:
            return False
        meta["status"] = status
        meta["updated_at"] = time.time()
        return self._write_metadata(project_id, meta)

    def append_event(self, project_id: str, event: dict) -> bool:
        """
        Append a single JSON event as one line to thinking.jsonl.
        Never raises. Returns True on success, False otherwise.
        """
        if not self._exists(project_id):
            return False
        if not isinstance(event, dict):
            return False
        path = os.path.join(self._project_dir(project_id), "thinking.jsonl")
        try:
            line = json.dumps(event, ensure_ascii=False)
        except Exception:
            return False
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            return True
        except Exception:
            return False

    def copy_structure(self, project_id: str, structure_path: str) -> bool:
        """Copy structure_path into <project>/structure.json."""
        if not self._exists(project_id):
            return False
        if not isinstance(structure_path, str) or not os.path.isfile(structure_path):
            return False
        dest = os.path.join(self._project_dir(project_id), "structure.json")
        try:
            shutil.copy2(structure_path, dest)
            return True
        except Exception:
            return False

    def copy_contracts(self, project_id: str, contracts_path: str) -> bool:
        """Copy contracts_path into <project>/contracts.json."""
        if not self._exists(project_id):
            return False
        if not isinstance(contracts_path, str) or not os.path.isfile(contracts_path):
            return False
        dest = os.path.join(self._project_dir(project_id), "contracts.json")
        try:
            shutil.copy2(contracts_path, dest)
            return True
        except Exception:
            return False

    def copy_output(self, project_id: str, output_dir: str) -> bool:
        """
        Copy all regular files from output_dir into <project>/output/.
        Existing files with the same name are overwritten.
        Returns False if project or source does not exist.
        """
        if not self._exists(project_id):
            return False
        if not isinstance(output_dir, str) or not os.path.isdir(output_dir):
            return False
        dest_dir = os.path.join(self._project_dir(project_id), "output")
        try:
            os.makedirs(dest_dir, exist_ok=True)
            for name in os.listdir(output_dir):
                src = os.path.join(output_dir, name)
                if not os.path.isfile(src):
                    continue
                dst = os.path.join(dest_dir, name)
                shutil.copy2(src, dst)
            return True
        except Exception:
            return False