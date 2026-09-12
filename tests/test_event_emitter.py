import io
import json
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from communication.events import EventEmitter


class TestEventEmitter(unittest.TestCase):

    def test_structured_true_writes_json_line(self):
        stream = io.StringIO()
        emitter = EventEmitter(run_id="run-1", structured=True, stream=stream)
        emitter.emit("run_started", {"idea": "hello"})

        output = stream.getvalue()
        self.assertTrue(output.endswith("\n"))
        line = output.strip()
        event = json.loads(line)
        self.assertEqual(event["type"], "run_started")
        self.assertEqual(event["payload"], {"idea": "hello"})

    def test_structured_false_writes_nothing(self):
        stream = io.StringIO()
        emitter = EventEmitter(run_id="run-1", structured=False, stream=stream)
        emitter.emit("run_started", {"idea": "hello"})
        emitter.emit("run_completed", {"total_runtime": 1.0, "iterations": 3})

        self.assertEqual(stream.getvalue(), "")

    def test_required_fields_present(self):
        stream = io.StringIO()
        emitter = EventEmitter(run_id="run-x", structured=True, stream=stream)
        emitter.emit("run_failed", {"reason": "boom", "total_runtime": 2.5})

        event = json.loads(stream.getvalue().strip())
        for field in ("v", "ts", "run_id", "type", "payload"):
            self.assertIn(field, event)
        self.assertIsInstance(event["v"], int)
        self.assertIsInstance(event["ts"], float)
        self.assertIsInstance(event["run_id"], str)
        self.assertIsInstance(event["type"], str)
        self.assertIsInstance(event["payload"], dict)

    def test_v_always_1(self):
        stream = io.StringIO()
        emitter = EventEmitter(run_id="run-x", structured=True, stream=stream)
        emitter.emit("run_started", {"idea": "a"})
        emitter.emit("run_completed", {"total_runtime": 1.0, "iterations": 1})

        lines = [l for l in stream.getvalue().splitlines() if l.strip()]
        self.assertEqual(len(lines), 2)
        for line in lines:
            event = json.loads(line)
            self.assertEqual(event["v"], 1)

    def test_run_id_consistent_within_emitter(self):
        stream = io.StringIO()
        emitter = EventEmitter(run_id="same-run", structured=True, stream=stream)
        emitter.emit("run_started", {"idea": "a"})
        emitter.emit("run_completed", {"total_runtime": 1.0, "iterations": 1})

        lines = [l for l in stream.getvalue().splitlines() if l.strip()]
        run_ids = {json.loads(l)["run_id"] for l in lines}
        self.assertEqual(run_ids, {"same-run"})
        self.assertEqual(emitter.run_id(), "same-run")

    def test_two_emitters_have_different_run_ids(self):
        stream1 = io.StringIO()
        stream2 = io.StringIO()
        e1 = EventEmitter(run_id="run-a", structured=True, stream=stream1)
        e2 = EventEmitter(run_id="run-b", structured=True, stream=stream2)
        e1.emit("run_started", {"idea": "a"})
        e2.emit("run_started", {"idea": "b"})

        event1 = json.loads(stream1.getvalue().strip())
        event2 = json.loads(stream2.getvalue().strip())
        self.assertNotEqual(event1["run_id"], event2["run_id"])

    def test_run_started_payload(self):
        stream = io.StringIO()
        emitter = EventEmitter(run_id="r", structured=True, stream=stream)
        emitter.emit("run_started", {"idea": "Build a todo app"})

        event = json.loads(stream.getvalue().strip())
        self.assertEqual(event["payload"], {"idea": "Build a todo app"})

    def test_run_completed_payload(self):
        stream = io.StringIO()
        emitter = EventEmitter(run_id="r", structured=True, stream=stream)
        emitter.emit("run_completed", {"total_runtime": 12.5, "iterations": 7})

        event = json.loads(stream.getvalue().strip())
        self.assertEqual(event["payload"]["total_runtime"], 12.5)
        self.assertEqual(event["payload"]["iterations"], 7)

    def test_run_failed_payload(self):
        stream = io.StringIO()
        emitter = EventEmitter(run_id="r", structured=True, stream=stream)
        emitter.emit("run_failed", {"reason": "supervisor_error", "total_runtime": 3.2})

        event = json.loads(stream.getvalue().strip())
        self.assertEqual(event["payload"]["reason"], "supervisor_error")
        self.assertEqual(event["payload"]["total_runtime"], 3.2)

    def test_run_interrupted_payload(self):
        stream = io.StringIO()
        emitter = EventEmitter(run_id="r", structured=True, stream=stream)
        emitter.emit("run_interrupted", {"total_runtime": 8.8})

        event = json.loads(stream.getvalue().strip())
        self.assertEqual(event["payload"], {"total_runtime": 8.8})

    def test_broken_stream_does_not_raise(self):
        class BrokenStream:
            def write(self, _):
                raise IOError("stream broken")
            def flush(self):
                raise IOError("stream broken")

        emitter = EventEmitter(run_id="r", structured=True, stream=BrokenStream())
        # Should not raise.
        emitter.emit("run_started", {"idea": "a"})
        emitter.emit("run_completed", {"total_runtime": 1.0, "iterations": 1})

    def test_default_stream_is_sys_stderr(self):
        original = sys.stderr
        captured = io.StringIO()
        try:
            sys.stderr = captured
            emitter = EventEmitter(run_id="r", structured=True)
            emitter.emit("run_started", {"idea": "x"})
        finally:
            sys.stderr = original

        line = captured.getvalue().strip()
        event = json.loads(line)
        self.assertEqual(event["type"], "run_started")

    def test_ensure_ascii_false(self):
        stream = io.StringIO()
        emitter = EventEmitter(run_id="r", structured=True, stream=stream)
        emitter.emit("run_started", {"idea": "تبدیل دما"})

        raw = stream.getvalue()
        self.assertIn("تبدیل دما", raw)
        event = json.loads(raw.strip())
        self.assertEqual(event["payload"]["idea"], "تبدیل دما")


if __name__ == "__main__":
    unittest.main()