import os
import json
import time
import config
class WorkspaceManager:
    def __init__(self):
        self.workspace_dir = config.WORKSPACE_DIR
        os.makedirs(self.workspace_dir, exist_ok=True)
        self._init_files()

    def _init_files(self):
        defaults = {
            config.PHASE_FILE: {"current_phase": 0, "current_module": "", "status": "idle"},
            config.LOG_FILE: [],
            config.STRUCTURE_FILE: {
                "project_name": "",
                "phases": [],
                "acceptance_tests": []
            },
            config.TEST_RESULTS_FILE: []
        }
        for filepath, content in defaults.items():
            if not os.path.exists(filepath):
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(content, f, indent=2)
                except OSError:
                    pass

    def read_phase(self):
        try:
            with open(config.PHASE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"current_phase": 0, "current_module": "", "status": "idle"}

    def update_phase(self, phase, module="", status="idle"):
        data = {"current_phase": phase, "current_module": module, "status": status}
        with open(config.PHASE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def log_event(self, event, phase=0):
        try:
            with open(config.LOG_FILE, 'r', encoding='utf-8') as f:
                log = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            log = []
        log.append({"timestamp": time.time(), "event": event, "phase": phase})
        with open(config.LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(log, f, indent=2)

    def read_structure(self):
        try:
            with open(config.STRUCTURE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"project_name": "", "phases": [], "acceptance_tests": []}

    def write_structure(self, structure):
        with open(config.STRUCTURE_FILE, 'w', encoding='utf-8') as f:
            json.dump(structure, f, indent=2)

    def read_test_results(self):
        try:
            with open(config.TEST_RESULTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_test_result(self, phase, status, details):
        try:
            with open(config.TEST_RESULTS_FILE, 'r', encoding='utf-8') as f:
                results = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            results = []
        results.append({"phase": phase, "status": status, "details": details, "timestamp": time.time()})
        with open(config.TEST_RESULTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)