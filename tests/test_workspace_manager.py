import sys
import os
import json
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from workspace.workspace_manager import WorkspaceManager
with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = tmp
    config.PHASE_FILE = os.path.join(tmp, "current_phase.json")
    config.LOG_FILE = os.path.join(tmp, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(tmp, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(tmp, "test_results.json")
    wm = WorkspaceManager()
    try:
        assert os.path.isdir(config.WORKSPACE_DIR)
        phase = wm.read_phase()
        assert phase == {"current_phase": 0, "current_module": "", "status": "idle"}
        assert wm.read_structure() == {"project_name": "", "phases": []}
        assert wm.read_test_results() == []
        wm.update_phase(2, "calculator", "building")
        assert wm.read_phase()["current_phase"] == 2
        wm.log_event("test_event", 2)
        with open(config.LOG_FILE) as f:
            log = json.load(f)
        assert len(log) == 1 and log[0]["event"] == "test_event"
        len_before = len(log)
        with open(config.PHASE_FILE, 'w') as f:
            f.write("not a json")
        recovered = wm.read_phase()
        assert recovered == {"current_phase": 0, "current_module": "", "status": "idle"}
        with open(config.LOG_FILE) as f:
            log_after = json.load(f)
        assert log_after[-1]["event"] == "Phase file missing or corrupt, resetting"
        os.remove(config.LOG_FILE)
        wm.log_event("recovery_test", 1)
        assert os.path.exists(config.LOG_FILE)
        with open(config.LOG_FILE) as f:
            recovery_log = json.load(f)
        assert len(recovery_log) == 1 and recovery_log[0]["event"] == "recovery_test"
        wm.write_structure({"project_name": "test", "phases": [1,2]})
        assert wm.read_structure()["project_name"] == "test"
        wm.save_test_result(2, "passed", "ok")
        results = wm.read_test_results()
        assert len(results) == 1 and results[0]["status"] == "passed"
        print("PHASE 1.2 PASSED")
    except AssertionError as e:
        print("PHASE 1.2 FAILED")
        print(e)