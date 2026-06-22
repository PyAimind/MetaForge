import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from communication.message import Message
msg = Message(sender="supervisor", receiver="coder", msg_type="CommandMsg", phase=1, payload={"task": "build"})
assert msg.sender == "supervisor"
assert msg.receiver == "coder"
assert msg.msg_type == "CommandMsg"
assert msg.phase == 1
assert msg.payload == {"task": "build"}
try:
    msg.sender = "engineer"
    assert False
except AttributeError:
    pass
d = msg.to_dict()
assert d == {"sender": "supervisor", "receiver": "coder", "msg_type": "CommandMsg", "phase": 1, "payload": {"task": "build"}}
msg2 = Message.from_dict(d)
assert msg == msg2
bad_data = {"sender": "a", "receiver": "b", "msg_type": "CommandMsg", "payload": {}}
try:
    Message.from_dict(bad_data)
    assert False
except TypeError:
    pass
print("PHASE 2.1 PASSED")