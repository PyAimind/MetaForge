import os
WORKSPACE_DIR = os.path.join(os.path.dirname(__file__), "workspace")
PHASE_FILE = os.path.join(WORKSPACE_DIR, "current_phase.json")
LOG_FILE = os.path.join(WORKSPACE_DIR, "build_log.json")
STRUCTURE_FILE = os.path.join(WORKSPACE_DIR, "project_structure.json")
TEST_RESULTS_FILE = os.path.join(WORKSPACE_DIR, "test_results.json")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
AGENT_NAMES = ["supervisor", "engineer", "coder", "tester"]
LLM_READ_TIMEOUT = 120
LLM_RETRY_ATTEMPTS = 2
LLM_RETRY_DELAY = 2