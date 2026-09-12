"""Subprocess runner for MetaForge v4.0.

Spawns main.py as a subprocess, reads structured JSON events from stderr,
persists them in the ProjectStore, and broadcasts them to subscribers.
"""

import collections
import json
import os
import queue
import subprocess
import sys
import threading
from typing import Optional


class RunManager:
    """Spawns and monitors a single MetaForge subprocess at a time."""

    def __init__(self, store):
        self.store = store
        self._lock = threading.Lock()
        self._proc: Optional[subprocess.Popen] = None
        self._project_id: Optional[str] = None
        self._starting: bool = False
        self._subscribers = collections.defaultdict(list)

    def is_running(self, project_id: str) -> bool:
        with self._lock:
            return self._proc is not None and self._project_id == project_id

    def subscribe(self, project_id: str) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._subscribers[project_id].append(q)
        return q

    def unsubscribe(self, project_id: str, q: queue.Queue) -> None:
        with self._lock:
            subs = self._subscribers.get(project_id)
            if subs and q in subs:
                subs.remove(q)

    def _broadcast(self, project_id: str, event: dict) -> None:
        with self._lock:
            subs = list(self._subscribers.get(project_id, []))
        for q in subs:
            try:
                q.put_nowait(event)
            except Exception:
                pass

    def _final_status(self, last_type: Optional[str]) -> str:
        if last_type == "run_completed":
            return "completed"
        if last_type == "run_interrupted":
            return "interrupted"
        if last_type == "run_failed":
            return "failed"
        return "failed"

    def _read_stream(self, project_id: str) -> None:
        try:
            proc = self._proc
            if proc is None or proc.stderr is None:
                return
            last_type: Optional[str] = None
            for line in proc.stderr:
                line = line.strip()
                if not line or not line.startswith("{"):
                    continue
                try:
                    event = json.loads(line)
                except Exception:
                    continue
                if not isinstance(event, dict):
                    continue
                last_type = event.get("type", last_type)
                self.store.append_event(project_id, event)
                self._broadcast(project_id, event)
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
            self.store.update_status(project_id, self._final_status(last_type))
        except Exception:
            try:
                self.store.update_status(project_id, "failed")
            except Exception:
                pass
        finally:
            with self._lock:
                self._proc = None
                self._project_id = None

    def start(self, idea: str, name: str) -> str:
        with self._lock:
            if self._proc is not None or self._starting:
                raise RuntimeError("A run is already in progress")
            self._starting = True

        project_id: Optional[str] = None
        try:
            project_id = self.store.create(name=name, idea=idea)
            if not project_id:
                raise RuntimeError("Failed to create project")
            self.store.update_status(project_id, "running")

            env = dict(os.environ)
            env["METAFORGE_STRUCTURED"] = "1"
            env["METAFORGE_IDEA"] = idea
            env["METAFORGE_PROJECT_ID"] = project_id

            proc = subprocess.Popen(
                [sys.executable, "main.py"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=env,
            )
        except Exception as e:
            with self._lock:
                self._starting = False
            if project_id:
                try:
                    self.store.update_status(project_id, "failed")
                except Exception:
                    pass
            raise RuntimeError(f"Failed to start subprocess: {e}")

        with self._lock:
            self._proc = proc
            self._project_id = project_id
            self._starting = False

        t = threading.Thread(
            target=self._read_stream, args=(project_id,), daemon=True
        )
        t.start()
        return project_id

    def stop(self, project_id: str) -> bool:
        with self._lock:
            if self._proc is None or self._project_id != project_id:
                return False
            proc = self._proc
        try:
            proc.terminate()
            return True
        except Exception:
            return False