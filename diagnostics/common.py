import os
import json
import config

def read_json_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def check_file_exists(filepath):
    return os.path.exists(filepath)

def read_log_entries():
    entries = read_json_file(config.LOG_FILE)
    return entries if isinstance(entries, list) else []

def read_test_results():
    results = read_json_file(config.TEST_RESULTS_FILE)
    return results if isinstance(results, list) else []

def read_workspace_structure():
    return read_json_file(config.STRUCTURE_FILE)

def read_text_file(filepath):
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return None