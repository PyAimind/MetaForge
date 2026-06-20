import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
try:
    assert config.WORKSPACE_DIR.endswith("workspace")
    assert config.PHASE_FILE.endswith("current_phase.json")
    assert config.LOG_FILE.endswith("build_log.json")
    assert config.STRUCTURE_FILE.endswith("project_structure.json")
    assert config.TEST_RESULTS_FILE.endswith("test_results.json")
    assert config.OUTPUT_DIR.endswith("output")
    assert config.AGENT_NAMES == ["supervisor", "engineer", "coder", "tester"]
    assert config.PHASE_FILE.startswith(config.WORKSPACE_DIR)
    assert config.LOG_FILE.startswith(config.WORKSPACE_DIR)
    assert config.STRUCTURE_FILE.startswith(config.WORKSPACE_DIR)
    assert config.TEST_RESULTS_FILE.startswith(config.WORKSPACE_DIR)
    print("PHASE 1.1 PASSED")
except AssertionError as e:
    print("PHASE 1.1 FAILED")
    print(e)
    