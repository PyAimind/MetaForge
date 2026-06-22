import sys
import os
import queue
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from communication.message_channel import MessageChannel
from communication.message import Message

channel = MessageChannel()
msg = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=2, payload={})
channel.send(msg)
received = channel.receive("coder")
assert received == msg
assert received.sender == "supervisor"
assert received.receiver == "coder"

assert not channel.has_messages("coder")
channel.send(msg)
assert channel.has_messages("coder")
assert channel.queue_size("coder") == 1
_ = channel.receive("coder")
assert channel.queue_size("coder") == 0

timeout_worked = False
try:
    channel.receive("coder", timeout=0.1)
    assert False
except queue.Empty:
    timeout_worked = True
assert timeout_worked

bad_msg = Message(sender="a", receiver="unknown_agent", msg_type="CommandMsg", phase=1, payload={})
try:
    channel.send(bad_msg)
    assert False
except ValueError as e:
    assert "Unknown receiver" in str(e)

try:
    channel.receive("unknown_agent")
    assert False
except ValueError as e:
    assert "Unknown agent" in str(e)

try:
    channel.has_messages("unknown_agent")
    assert False
except ValueError as e:
    assert "Unknown agent" in str(e)

try:
    channel.queue_size("unknown_agent")
    assert False
except ValueError as e:
    assert "Unknown agent" in str(e)

print("PHASE 2.2 PASSED")