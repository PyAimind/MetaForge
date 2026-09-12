"""FastAPI HTTP and WebSocket backend for MetaForge v4.0."""

import asyncio
import json
import os
import queue
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from project_store import ProjectStore
from ui.runner import RunManager


PROJECTS_DIR = os.getenv("METAFORGE_PROJECTS_DIR", "projects")
store = ProjectStore(PROJECTS_DIR)
manager = RunManager(store)
app = FastAPI(title="MetaForge v4.0 API")


class CreateProjectRequest(BaseModel):
    name: str
    idea: str


class RenameProjectRequest(BaseModel):
    name: str


def _thinking_path(project_id: str) -> Path:
    """Return the path to the project's thinking.jsonl file."""
    return Path(PROJECTS_DIR) / project_id / "thinking.jsonl"


def _output_dir(project_id: str) -> Path:
    """Return the path to the project's output directory."""
    return Path(PROJECTS_DIR) / project_id / "output"


def _is_safe_filename(name: str) -> bool:
    """Reject filenames that could escape the output directory."""
    if not name or not isinstance(name, str):
        return False
    if "/" in name or "\\" in name or ".." in name:
        return False
    return True


def _read_events(project_id: str) -> list:
    """Read and parse all valid JSON events from thinking.jsonl."""
    path = _thinking_path(project_id)
    if not path.is_file():
        return []
    events = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return events


@app.post("/api/projects")
async def create_project(req: CreateProjectRequest):
    """Start a new MetaForge run and return its project id."""
    try:
        project_id = manager.start(idea=req.idea, name=req.name)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"id": project_id}


@app.get("/api/projects")
async def list_projects():
    """Return all stored projects, newest first."""
    return list(store.list())


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    """Return metadata for a single project."""
    meta = store.get(project_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return meta


@app.patch("/api/projects/{project_id}")
async def rename_project(project_id: str, req: RenameProjectRequest):
    """Rename a project."""
    ok = store.rename(project_id, req.name)
    if not ok:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"ok": True}


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    """Stop the run if active, then delete the project."""
    if manager.is_running(project_id):
        manager.stop(project_id)
    ok = store.delete(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"ok": True}


@app.get("/api/projects/{project_id}/thinking")
async def get_thinking(project_id: str):
    """Return the full thinking log for a project."""
    if store.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return _read_events(project_id)


@app.get("/api/projects/{project_id}/modules")
async def list_modules(project_id: str):
    """List generated module files with their sizes."""
    if store.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    out_dir = _output_dir(project_id)
    if not out_dir.is_dir():
        return []
    items = []
    for entry in out_dir.iterdir():
        if entry.is_file():
            try:
                items.append({"name": entry.name, "size": entry.stat().st_size})
            except Exception:
                continue
    items.sort(key=lambda x: x["name"])
    return items


@app.get("/api/projects/{project_id}/modules/{filename}")
async def get_module(project_id: str, filename: str):
    """Return the content of a generated module file."""
    if store.get(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not _is_safe_filename(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = _output_dir(project_id) / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Module not found")
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to read module")
    return {"name": filename, "content": content}


@app.websocket("/ws/run/{project_id}")
async def ws_run(websocket: WebSocket, project_id: str):
    """Stream events for a project: existing history, then live events."""
    await websocket.accept()
    if store.get(project_id) is None:
        await websocket.close(code=1008)
        return

    q = manager.subscribe(project_id)
    try:
        for event in _read_events(project_id):
            await websocket.send_json(event)

        loop = asyncio.get_running_loop()
        while True:
            try:
                event = await loop.run_in_executor(None, q.get, True, 0.05)
                await websocket.send_json(event)
            except queue.Empty:
                await asyncio.sleep(0.02)
                continue
            except WebSocketDisconnect:
                break
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        manager.unsubscribe(project_id, q)