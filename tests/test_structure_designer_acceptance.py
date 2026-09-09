import json
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from project_design.structure_designer_llm import StructureDesignerLLM


class MockProvider:
    def __init__(self, raw_json: str):
        self.raw_json = raw_json
        self.calls = []

    def generate(self, messages, model, temperature):
        self.calls.append((messages, model, temperature))
        return self.raw_json


BASE_VALID_STRUCTURE = {
    "project_name": "TestProject",
    "description": "A test project",
    "phases": [
        {
            "phase_number": 1,
            "name": "Core",
            "modules": [
                {
                    "filename": "calculator.py",
                    "description": "Calculator module",
                    "dependencies": [],
                    "purpose": "math",
                    "exports": [],
                    "required_imports": []
                }
            ]
        }
    ]
}


class TestStructureDesignerAcceptance(unittest.TestCase):

    def _make_designer(self, overrides=None):
        structure = json.loads(json.dumps(BASE_VALID_STRUCTURE))
        if overrides:
            structure.update(overrides)
        raw = json.dumps(structure)
        provider = MockProvider(raw)
        return StructureDesignerLLM(provider)

    def test_missing_acceptance_tests(self):
        structure = json.loads(json.dumps(BASE_VALID_STRUCTURE))
        structure.pop("acceptance_tests", None)
        raw = json.dumps(structure)
        designer = StructureDesignerLLM(MockProvider(raw))
        result = designer.design("test idea")
        self.assertIn("acceptance_tests", result)
        self.assertEqual(result["acceptance_tests"], [])

    def test_valid_acceptance_tests(self):
        designer = self._make_designer({
            "acceptance_tests": [
                {
                    "description": "Addition works",
                    "entrypoint": "calculator.py",
                    "args": ["add", "2", "3"],
                    "expected_stdout_contains": ["5"],
                    "expected_return_code": 0,
                    "timeout_seconds": 10
                },
                {
                    "description": "Help works",
                    "entrypoint": "calculator.py",
                    "args": ["--help"],
                    "expected_stdout_contains": ["usage:"],
                    "expected_return_code": 0,
                    "timeout_seconds": 5
                }
            ]
        })
        result = designer.design("test idea")
        acceptance_tests = result["acceptance_tests"]
        self.assertEqual(len(acceptance_tests), 2)

        first, second = acceptance_tests[0], acceptance_tests[1]

        self.assertEqual(first["description"], "Addition works")
        self.assertEqual(first["entrypoint"], "calculator.py")
        self.assertEqual(first["args"], ["add", "2", "3"])
        self.assertEqual(first["expected_stdout_contains"], ["5"])
        self.assertEqual(first["expected_return_code"], 0)
        self.assertEqual(first["timeout_seconds"], 10)

        self.assertEqual(second["description"], "Help works")
        self.assertEqual(second["entrypoint"], "calculator.py")
        self.assertEqual(second["args"], ["--help"])
        self.assertEqual(second["expected_stdout_contains"], ["usage:"])
        self.assertEqual(second["expected_return_code"], 0)
        self.assertEqual(second["timeout_seconds"], 5)

    def test_invalid_entrypoint_discarded(self):
        designer = self._make_designer({
            "acceptance_tests": [
                {
                    "description": "Bad entrypoint",
                    "entrypoint": "missing.py",
                    "args": [],
                    "expected_stdout_contains": [],
                    "expected_return_code": 0,
                    "timeout_seconds": 10
                }
            ]
        })
        result = designer.design("test idea")
        self.assertEqual(result["acceptance_tests"], [])

    def test_invalid_args_discarded(self):
        designer = self._make_designer({
            "acceptance_tests": [
                {
                    "description": "Bad args",
                    "entrypoint": "calculator.py",
                    "args": "not-a-list",
                    "expected_stdout_contains": [],
                    "expected_return_code": 0,
                    "timeout_seconds": 10
                }
            ]
        })
        result = designer.design("test idea")
        self.assertEqual(result["acceptance_tests"], [])

    def test_invalid_timeout_discarded(self):
        designer = self._make_designer({
            "acceptance_tests": [
                {
                    "description": "Bad timeout",
                    "entrypoint": "calculator.py",
                    "args": [],
                    "expected_stdout_contains": [],
                    "expected_return_code": 0,
                    "timeout_seconds": 0
                }
            ]
        })
        result = designer.design("test idea")
        self.assertEqual(result["acceptance_tests"], [])

    def test_invalid_expected_return_code_bool_discarded(self):
        designer = self._make_designer({
            "acceptance_tests": [
                {
                    "description": "Bool return code",
                    "entrypoint": "calculator.py",
                    "args": [],
                    "expected_stdout_contains": [],
                    "expected_return_code": True,
                    "timeout_seconds": 10
                }
            ]
        })
        result = designer.design("test idea")
        self.assertEqual(result["acceptance_tests"], [])

    def test_malformed_test_object_discarded(self):
        designer = self._make_designer({
            "acceptance_tests": [
                "not-a-dict",
                None,
                42,
                {
                    "description": "Valid test",
                    "entrypoint": "calculator.py",
                    "args": [],
                    "expected_stdout_contains": [],
                    "expected_return_code": 0,
                    "timeout_seconds": 10
                }
            ]
        })
        result = designer.design("test idea")
        self.assertEqual(len(result["acceptance_tests"]), 1)
        self.assertEqual(result["acceptance_tests"][0]["description"], "Valid test")


if __name__ == "__main__":
    unittest.main()