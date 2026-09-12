"""
Structured event stream for MetaForge.

Emits JSON Lines events to a stream (default: sys.stderr) so that external
consumers (e.g. the v4.0 UI) can observe the run in real time without parsing
human-readable stdout output.

This module is intentionally minimal and dependency-free. It does not import
config.py and does not touch any MetaForge agent or supervisor.
"""

import json
import sys
import threading
import time
from typing import Optional


class EventEmitter:
    """
    Emits structured JSON Lines events for a single MetaForge run.

    When `structured` is False, `emit()` is a no-op so the CLI experience is
    unchanged. When True, each call writes exactly one JSON object followed
    by a newline to `stream`.

    Events follow schema version 1:
        {
            "v": 1,
            "ts": <float>,
            "run_id": "<uuid>",
            "type": "<event_type>",
            "payload": { ... }
        }

    Thread-safety: a single lock serializes writes. Writes are followed by
    a flush so consumers reading from a pipe see events immediately.

    Failure policy: any exception during write/flush is swallowed silently.
    The emitter never crashes the run and never writes to stdout.
    """

    SCHEMA_VERSION = 1

    def __init__(
        self,
        run_id: str,
        structured: bool,
        stream: Optional[object] = None,
    ) -> None:
        # Do not default to sys.stderr at definition time: if the caller
        # replaces sys.stderr later, we must not hold a stale reference.
        if stream is None:
            stream = sys.stderr
        self._run_id: str = run_id
        self._structured: bool = bool(structured)
        self._stream = stream
        self._lock = threading.Lock()

    def run_id(self) -> str:
        """Return the run identifier used by this emitter."""
        return self._run_id

    def emit(self, event_type: str, payload: dict) -> None:
        """
        Emit a single event.

        Does nothing if the emitter is not in structured mode.
        Never raises: any error while writing is swallowed silently.
        """
        if not self._structured:
            return

        event = {
            "v": self.SCHEMA_VERSION,
            "ts": time.time(),
            "run_id": self._run_id,
            "type": event_type,
            "payload": payload,
        }

        try:
            line = json.dumps(event, ensure_ascii=False)
        except Exception:
            return

        try:
            with self._lock:
                self._stream.write(line + "\n")
                self._stream.flush()
        except Exception:
            # Silent failure: do not crash the run, do not print anything.
            return