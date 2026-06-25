import os
import time
from workspace.workspace_manager import WorkspaceManager
from communication.message_channel import MessageChannel
from agents.supervisor import Supervisor
from agents.engineer import Engineer
from agents.coder import Coder
from agents.tester import Tester
import config

os.makedirs(config.WORKSPACE_DIR, exist_ok=True)
os.makedirs(config.OUTPUT_DIR, exist_ok=True)
wm = WorkspaceManager()
channel = MessageChannel()
supervisor = Supervisor(channel, wm)
engineer = Engineer(channel, wm)
coder = Coder(channel, wm)
tester = Tester(channel, wm)
project_idea = "Simple Calculator"
supervisor.set_idea(project_idea)
while True:
    keep_going = supervisor.step()
    engineer.step()
    coder.step()
    tester.step()
    if not keep_going and supervisor.status in ("completed", "error"):
        break
    time.sleep(0.01)
if supervisor.status == "completed":
    print("MetaForge project completed.")
else:
    print("MetaForge project failed with error.")
print(f"Output: {config.OUTPUT_DIR}")