import io
import json
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from communication.events import EventEmitter
from communication.message import Message
import main as main_module


class TestTimelineEvents(unittest.TestCase):

    def _make_channel(self):
        stream = io.StringIO()
        emitter = EventEmitter(run_id="r", structured=True, stream=stream)
        channel = main_module.DiagnosticMessageChannel(emitter=emitter)
        return channel, stream

    def _events(self, stream):
        return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]

    def _timeline_events(self, stream):
        return [e for e in self._events(stream) if e.get("type") == "timeline_entry"]

    def test_no_emitter_does_not_raise(self):
        channel = main_module.DiagnosticMessageChannel()
        msg = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg",
                      phase=1, payload={"action": "code", "filename": "x.py"})
        channel.send(msg)

    def test_design_structure_emits_understanding(self):
        channel, stream = self._make_channel()
        msg = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg",
                      phase=1, payload={"action": "design_structure"})
        channel.send(msg)
        events = self._timeline_events(stream)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["payload"]["title"], "Understanding your idea")
        self.assertEqual(events[0]["payload"]["color"], "blue")

    def test_generate_prompts_emits_planning(self):
        channel, stream = self._make_channel()
        msg = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg",
                      phase=1, payload={"action": "generate_prompts"})
        channel.send(msg)
        events = self._timeline_events(stream)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["payload"]["title"], "Planning the project")
        self.assertEqual(events[0]["payload"]["color"], "blue")

    def test_coder_command_emits_writing(self):
        channel, stream = self._make_channel()
        msg = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg",
                      phase=1, payload={"action": "code", "filename": "storage.py"})
        channel.send(msg)
        events = self._timeline_events(stream)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["payload"]["title"], "Writing storage.py")
        self.assertEqual(events[0]["payload"]["color"], "purple")
        self.assertEqual(events[0]["payload"]["icon"], "spinner")

    def test_coder_command_with_is_fix_emits_refining(self):
        channel, stream = self._make_channel()
        msg = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg",
                      phase=1, payload={"action": "code", "filename": "storage.py", "is_fix": True})
        channel.send(msg)
        events = self._timeline_events(stream)
        self.assertEqual(len(events), 0)

    def test_coder_success_emits_written(self):
        channel, stream = self._make_channel()
        msg = Message(sender="coder", receiver="supervisor", msg_type="ResultMsg",
                      phase=1, payload={"status": "success", "filepath": "/abs/path/storage.py"})
        channel.send(msg)
        events = self._timeline_events(stream)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["payload"]["title"], "storage.py written")
        self.assertEqual(events[0]["payload"]["color"], "purple")
        self.assertEqual(events[0]["payload"]["icon"], "check")

    def test_tester_command_emits_testing(self):
        channel, stream = self._make_channel()
        msg = Message(sender="supervisor", receiver="tester", msg_type="CommandMsg",
                      phase=2, payload={"action": "test", "filepath": "/abs/path/cli.py"})
        channel.send(msg)
        events = self._timeline_events(stream)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["payload"]["title"], "Testing cli.py")
        self.assertEqual(events[0]["payload"]["color"], "cyan")

    def test_tester_passed_emits_passed(self):
        channel, stream = self._make_channel()
        msg = Message(sender="tester", receiver="supervisor", msg_type="ResultMsg",
                      phase=2, payload={"status": "passed", "filepath": "/abs/path/cli.py"})
        channel.send(msg)
        events = self._timeline_events(stream)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["payload"]["title"], "cli.py passed")
        self.assertEqual(events[0]["payload"]["color"], "green")
        self.assertEqual(events[0]["payload"]["icon"], "check")

    def test_tester_failed_emits_failed(self):
        channel, stream = self._make_channel()
        msg = Message(sender="tester", receiver="supervisor", msg_type="ResultMsg",
                      phase=2, payload={"status": "failed", "filepath": "/abs/path/cli.py",
                                        "reason": "Syntax error at line 5"})
        channel.send(msg)
        events = self._timeline_events(stream)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["payload"]["title"], "cli.py failed")
        self.assertEqual(events[0]["payload"]["color"], "orange")
        self.assertEqual(events[0]["payload"]["icon"], "cross")
        self.assertIn("Syntax error", events[0]["payload"]["detail"])

    def test_tester_runtime_failure_emits_failed(self):
        channel, stream = self._make_channel()
        msg = Message(sender="tester", receiver="supervisor", msg_type="ResultMsg",
                      phase=2, payload={"status": "runtime_failure", "filepath": "/abs/path/cli.py",
                                        "reason": "ImportError"})
        channel.send(msg)
        events = self._timeline_events(stream)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["payload"]["title"], "cli.py failed")
        self.assertEqual(events[0]["payload"]["color"], "orange")

    def test_acceptance_tests_emit_verifying(self):
        channel, stream = self._make_channel()
        msg = Message(sender="supervisor", receiver="tester", msg_type="CommandMsg",
                      phase=3, payload={"action": "test", "acceptance_tests": [{}, {}, {}]})
        channel.send(msg)
        events = self._timeline_events(stream)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["payload"]["title"], "Running final verification")
        self.assertIn("3", events[0]["payload"]["detail"])
        self.assertEqual(events[0]["payload"]["color"], "cyan")

    def test_acceptance_passed_emits_verification_passed(self):
        channel, stream = self._make_channel()
        msg = Message(sender="tester", receiver="supervisor", msg_type="ResultMsg",
                      phase=3, payload={"status": "passed"})
        channel.send(msg)
        events = self._timeline_events(stream)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["payload"]["title"], "Verification passed")
        self.assertEqual(events[0]["payload"]["color"], "green")

    def test_acceptance_failed_emits_verification_failed(self):
        channel, stream = self._make_channel()
        msg = Message(sender="tester", receiver="supervisor", msg_type="ResultMsg",
                      phase=3, payload={"status": "failed"})
        channel.send(msg)
        events = self._timeline_events(stream)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["payload"]["title"], "Verification failed")
        self.assertEqual(events[0]["payload"]["color"], "orange")
        self.assertEqual(events[0]["payload"]["icon"], "cross")

    def test_repair_emits_refining(self):
        channel, stream = self._make_channel()
        msg = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg",
                      phase=1, payload={"action": "generate_single_prompt", "is_fix": True})
        channel.send(msg)
        events = self._timeline_events(stream)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["payload"]["title"], "Refining the solution")
        self.assertEqual(events[0]["payload"]["color"], "orange")
        self.assertEqual(events[0]["payload"]["icon"], "spinner")

    def test_irrelevant_message_emits_nothing(self):
        channel, stream = self._make_channel()
        msg = Message(sender="engineer", receiver="supervisor", msg_type="ResultMsg",
                      phase=1, payload={"status": "success", "structure": {"x": 1}})
        channel.send(msg)
        events = self._timeline_events(stream)
        self.assertEqual(len(events), 0)

    def test_emitter_failure_does_not_raise(self):
        class BrokenEmitter:
            def emit(self, *args, **kwargs):
                raise RuntimeError("boom")
        channel = main_module.DiagnosticMessageChannel(emitter=BrokenEmitter())
        msg = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg",
                      phase=1, payload={"action": "code", "filename": "x.py"})
        channel.send(msg)

    def test_message_still_delivered(self):
        channel, _ = self._make_channel()
        msg = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg",
                      phase=1, payload={"action": "code", "filename": "x.py"})
        channel.send(msg)
        received = channel.receive("coder", timeout=0.5)
        self.assertEqual(received.sender, "supervisor")
        self.assertEqual(received.payload["filename"], "x.py")

    def test_event_schema_has_required_fields(self):
        channel, stream = self._make_channel()
        msg = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg",
                      phase=1, payload={"action": "design_structure"})
        channel.send(msg)
        events = self._events(stream)
        self.assertEqual(len(events), 1)
        event = events[0]
        for field in ("v", "ts", "run_id", "type", "payload"):
            self.assertIn(field, event)
        self.assertEqual(event["v"], 1)
        self.assertEqual(event["type"], "timeline_entry")


if __name__ == "__main__":
    unittest.main()