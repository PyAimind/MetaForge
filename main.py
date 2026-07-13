import os
import sys
import time
from workspace.workspace_manager import WorkspaceManager
from communication.message_channel import MessageChannel
from llm_provider import LLMProvider
from project_design.structure_designer_llm import StructureDesignerLLM
from project_design.code_generator_llm import CodeGeneratorLLM
from project_design.code_executor import CodeExecutor
from agents.supervisor import Supervisor
from agents.engineer import Engineer
from agents.coder import Coder
from agents.tester import Tester
import config

LOOP_DELAY = 0.01

def build_dependencies():
    provider = LLMProvider()
    designer = StructureDesignerLLM(provider)
    generator = CodeGeneratorLLM(provider)
    executor = CodeExecutor()
    return designer, generator, executor

os.makedirs(config.WORKSPACE_DIR, exist_ok=True)
os.makedirs(config.OUTPUT_DIR, exist_ok=True)

try:
    wm = WorkspaceManager()
    channel = MessageChannel()
    designer, generator, executor = build_dependencies()
    supervisor = Supervisor(channel, wm)
    engineer = Engineer(channel, wm, designer)
    coder = Coder(channel, wm, generator)
    tester = Tester(channel, wm, executor)
    agents = [engineer, coder, tester]

    project_idea = input("Enter your project idea: ").strip()
    if not project_idea:
        print("Project idea cannot be empty.")
        sys.exit(1)

    try:
        supervisor.set_idea(project_idea)
        while True:
            keep_going = supervisor.step()
            for agent in agents:
                agent.step()
            if not keep_going and supervisor.status in ("completed", "error"):
                break
            time.sleep(LOOP_DELAY)
    except KeyboardInterrupt:
        print("Interrupted by user.")
        sys.exit(0)

    if supervisor.status == "completed":
        print("MetaForge project completed.")
    else:
        print("MetaForge project failed with error.")
    print(f"Output: {config.OUTPUT_DIR}")

except Exception as e:
    print(f"Startup error: {e}")
    sys.exit(1)