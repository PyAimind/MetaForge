import ast
import os

class APIInspector:
    def __init__(self):
        pass

    def inspect(self, filepath: str, exports: list) -> dict:
        if not isinstance(filepath, str) or not filepath.strip() or not os.path.isfile(filepath):
            return {"valid": False, "errors": [f"File not found: {filepath}"]}
        if not isinstance(exports, list):
            return {"valid": False, "errors": ["exports must be a list"]}

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                source = f.read()
            tree = ast.parse(source, filename=filepath)
        except SyntaxError as e:
            return {"valid": False, "errors": [f"Syntax error in {filepath}: {e}"]}

        public_names = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith('_'):
                    public_names[node.name] = "function"
            elif isinstance(node, ast.ClassDef):
                if not node.name.startswith('_'):
                    public_names[node.name] = "class"

        imported_names = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    imported_names.add(alias.name)

        for name in list(public_names.keys()):
            if name in imported_names and name not in public_names:
                del public_names[name]

        clean_exports = []
        for exp in exports:
            if isinstance(exp, dict) and isinstance(exp.get("name"), str) and isinstance(exp.get("kind"), str):
                clean_exports.append(exp)

        expected_names = {exp["name"] for exp in clean_exports}
        errors = []

        for exp in sorted(clean_exports, key=lambda x: x["name"]):
            name = exp["name"]
            expected_kind = exp["kind"]
            if name not in public_names:
                errors.append(f"Missing export: {name}")
            elif public_names[name] != expected_kind:
                errors.append(f"Export '{name}' should be a {expected_kind} but is a {public_names[name]}")

        for name in sorted(public_names.keys()):
            if name not in expected_names:
                errors.append(f"Unexpected public symbol: {name}")

        errors.sort()
        return {"valid": len(errors) == 0, "errors": errors}