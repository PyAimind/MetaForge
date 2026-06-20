import sys
import os
import json
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from workspace.workspace_manager import WorkspaceManager
with tempfile.TemporaryDirectory() as tmp:
    config.WORKSPACE_DIR = os.path.join(tmp, "workspace")
    config.PHASE_FILE = os.path.join(config.WORKSPACE_DIR, "current_phase.json")
    config.LOG_FILE = os.path.join(config.WORKSPACE_DIR, "build_log.json")
    config.STRUCTURE_FILE = os.path.join(config.WORKSPACE_DIR, "project_structure.json")
    config.TEST_RESULTS_FILE = os.path.join(config.WORKSPACE_DIR, "test_results.json")
    wm = WorkspaceManager()
    try:
        assert os.path.isdir(config.WORKSPACE_DIR)
        assert os.path.exists(config.PHASE_FILE)
        assert os.path.exists(config.LOG_FILE)
        assert os.path.exists(config.STRUCTURE_FILE)
        assert os.path.exists(config.TEST_RESULTS_FILE)
        assert wm.read_phase() == {"current_phase": 0, "current_module": "", "status": "idle"}
        assert wm.read_structure() == {"project_name": "", "phases": []}
        assert wm.read_test_results() == []
        with open(config.LOG_FILE) as f:
            assert json.load(f) == []
        wm.update_phase(1, "test", "running")
        assert wm.read_phase() == {"current_phase": 1, "current_module": "test", "status": "running"}
        wm.log_event("integration_test", 1)
        with open(config.LOG_FILE) as f:
            log = json.load(f)
        assert len(log) == 1 and log[0]["event"] == "integration_test"
        wm.save_test_result(1, "pass", "details")
        results = wm.read_test_results()
        assert len(results) == 1 and results[0]["status"] == "pass"
        print("PHASE 1.3 INTEGRATION PASSED")
    except AssertionError as e:
        print("PHASE 1.3 INTEGRATION FAILED")
        print(e)