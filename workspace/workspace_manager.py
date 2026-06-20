import json
import os
from datetime import datetime
import config

class WorkspaceManager:
    def __init__(self):
        os.makedirs(config.WORKSPACE_DIR, exist_ok=True)
        self._init_files()

    def _init_files(self):
        defaults = {
            config.PHASE_FILE: {"current_phase": 0, "current_module": "", "status": "idle"},
            config.LOG_FILE: [],
            config.STRUCTURE_FILE: {"project_name": "", "phases": []},
            config.TEST_RESULTS_FILE: []
        }
        for filepath, content in defaults.items():
            if not os.path.exists(filepath):
                try:
                    with open(filepath, 'w') as f:
                        json.dump(content, f)
                except OSError:
                    self.log_event(f"Failed to create file: {filepath}")

    def read_phase(self):
        try:
            with open(config.PHASE_FILE, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.log_event("Phase file missing or corrupt, resetting")
            return {"current_phase": 0, "current_module": "", "status": "idle"}

    def update_phase(self, phase, module="", status="idle"):
        data = {"current_phase": phase, "current_module": module, "status": status}
        with open(config.PHASE_FILE, 'w') as f:
            json.dump(data, f)

    def log_event(self, event, phase=0):
        try:
            with open(config.LOG_FILE, 'r') as f:
                log = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            log = []
        log.append({"timestamp": datetime.now().isoformat(), "event": event, "phase": phase})
        with open(config.LOG_FILE, 'w') as f:
            json.dump(log, f)

    def read_structure(self):
        try:
            with open(config.STRUCTURE_FILE, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"project_name": "", "phases": []}

    def write_structure(self, structure):
        with open(config.STRUCTURE_FILE, 'w') as f:
            json.dump(structure, f)

    def save_test_result(self, phase, status, details=""):
        entry = {"phase": phase, "status": status, "details": details, "timestamp": datetime.now().isoformat()}
        try:
            with open(config.TEST_RESULTS_FILE, 'r') as f:
                results = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            results = []
        results.append(entry)
        with open(config.TEST_RESULTS_FILE, 'w') as f:
            json.dump(results, f)

    def read_test_results(self):
        try:
            with open(config.TEST_RESULTS_FILE, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []