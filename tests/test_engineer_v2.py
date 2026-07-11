import sys
import os
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from workspace.workspace_manager import WorkspaceManager
from communication.message import Message
from communication.message_channel import MessageChannel
from agents.engineer import Engineer

class MockDesigner:
    def __init__(self):
        self.call_count = 0
        self.last_idea = None
        self.valid_structure = {
            "project_name": "TestProject",
            "description": "A test",
            "phases": [
                {
                    "phase_number": 1,
                    "name": "Core",
                    "modules": [
                        {
                            "filename": "main.py",
                            "description": "Main module",
                            "dependencies": [],
                            "purpose": "main"
                        }
                    ]
                }
            ]
        }

    def design(self, idea):
        self.call_count += 1
        self.last_idea = idea
        return self.valid_structure

class FailingMockDesigner:
    def design(self, idea):
        raise RuntimeError("Simulated design failure")

with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    config.OUTPUT_DIR = os.path.join(tmp, "output")

    try:
        try:
            Engineer(None, None, None)
            assert False
        except TypeError:
            pass

        ch = MessageChannel()
        try:
            Engineer(ch, None, MockDesigner())
            assert False
        except TypeError:
            pass

        wm = WorkspaceManager()
        try:
            Engineer(ch, wm, "not_a_designer")
            assert False
        except TypeError:
            pass

        wm2 = WorkspaceManager()
        ch2 = MessageChannel()
        mock_designer = MockDesigner()
        engineer = Engineer(ch2, wm2, mock_designer)

        orig_write = wm2.write_structure
        orig_log = wm2.log_event
        write_calls = []
        log_calls = []
        try:
            def tracked_write(s):
                write_calls.append(s)
                orig_write(s)
            def tracked_log(msg, phase=0):
                log_calls.append(msg)
                orig_log(msg, phase)
            wm2.write_structure = tracked_write
            wm2.log_event = tracked_log

            msg = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=1,
                          payload={"action": "design_structure", "idea": "Test Project"})
            result = engineer.process_command(msg)

            assert result.sender == "engineer"
            assert result.receiver == "supervisor"
            assert result.msg_type == "ResultMsg"
            assert result.payload["status"] == "success"
            assert "structure" in result.payload
            assert result.payload["structure"] == mock_designer.valid_structure
            assert mock_designer.call_count == 1
            assert mock_designer.last_idea == "Test Project"
            assert len(write_calls) == 1
            assert write_calls[0] == mock_designer.valid_structure
            assert any("Engineer designed structure" in m for m in log_calls)
            assert wm2.read_structure() == mock_designer.valid_structure
        finally:
            wm2.write_structure = orig_write
            wm2.log_event = orig_log

        wm3 = WorkspaceManager()
        ch3 = MessageChannel()
        failing_designer = FailingMockDesigner()
        engineer2 = Engineer(ch3, wm3, failing_designer)

        orig_log3 = wm3.log_event
        log_calls3 = []
        try:
            def tracked_log3(msg, phase=0):
                log_calls3.append(msg)
                orig_log3(msg, phase)
            wm3.log_event = tracked_log3

            msg2 = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=1,
                           payload={"action": "design_structure", "idea": "X"})
            result2 = engineer2.process_command(msg2)

            assert result2.sender == "engineer"
            assert result2.msg_type == "ResultMsg"
            assert result2.payload["status"] == "error"
            assert "Failed to design structure" in result2.payload["reason"]
            assert any("Simulated design failure" in m for m in log_calls3)
        finally:
            wm3.log_event = orig_log3

        wm4 = WorkspaceManager()
        ch4 = MessageChannel()
        mock2 = MockDesigner()
        engineer3 = Engineer(ch4, wm4, mock2)

        msg_step = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=1,
                           payload={"action": "design_structure", "idea": "Step"})
        ch4.send(msg_step)
        assert engineer3.step()
        resp = ch4.receive("supervisor", timeout=0.5)
        assert resp.msg_type == "ResultMsg"
        assert resp.payload["status"] == "success"
        assert resp.sender == "engineer"
        assert resp.receiver == "supervisor"

        assert not engineer3.step()

        wm5 = WorkspaceManager()
        ch5 = MessageChannel()
        engineer4 = Engineer(ch5, wm5, MockDesigner())
        struct = {
            "project_name": "Demo",
            "description": "desc",
            "phases": [
                {
                    "phase_number": 1,
                    "name": "P1",
                    "modules": [
                        {"filename": "a.py", "description": "A", "dependencies": [], "purpose": "a"},
                        {"filename": "b.py", "description": "B", "dependencies": [], "purpose": "b"}
                    ]
                }
            ]
        }
        wm5.write_structure(struct)

        msg_prompts = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=1,
                              payload={"action": "generate_prompts"})
        res_prompts = engineer4.process_command(msg_prompts)
        assert res_prompts.payload["status"] == "success"
        prompts = res_prompts.payload["prompts"]
        assert isinstance(prompts, dict)
        assert len(prompts) == 2
        assert "a.py" in prompts
        assert "b.py" in prompts
        assert isinstance(prompts["a.py"], str) and len(prompts["a.py"]) > 0
        assert isinstance(prompts["b.py"], str) and len(prompts["b.py"]) > 0

        msg_single = Message(sender="supervisor", receiver="engineer", msg_type="CommandMsg", phase=1,
                             payload={"action": "generate_single_prompt",
                                      "module_info": {"filename": "mod.py", "description": "desc", "dependencies": []}})
        res_single = engineer4.process_command(msg_single)
        assert res_single.payload["status"] == "success"
        single_prompts = res_single.payload["prompts"]
        assert isinstance(single_prompts, dict)
        assert len(single_prompts) == 1
        assert "fixed_module.py" in single_prompts
        assert isinstance(single_prompts["fixed_module.py"], str) and len(single_prompts["fixed_module.py"]) > 10

        print("PHASE 9.3 PASSED")
    except AssertionError as e:
        print(f"PHASE 9.3 FAILED: {e}")
    except Exception as e:
        print(f"PHASE 9.3 FAILED: {e}")