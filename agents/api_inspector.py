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
        public_nodes = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith('_'):
                    public_names[node.name] = "function"
                    public_nodes[node.name] = node
            elif isinstance(node, ast.ClassDef):
                if not node.name.startswith('_'):
                    public_names[node.name] = "class"
                    public_nodes[node.name] = node

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
                public_nodes.pop(name, None)

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

        for exp in clean_exports:
            name = exp["name"]
            kind = exp["kind"]
            if name not in public_nodes:
                continue
            node = public_nodes[name]
            if kind == "function":
                params = exp.get("parameters")
                if params and isinstance(params, list):
                    actual_params = [arg.arg for arg in node.args.args]
                    expected_params = [p["name"] for p in params if isinstance(p, dict) and "name" in p]
                    if actual_params != expected_params:
                        errors.append(f"Export '{name}' parameter mismatch: expected {expected_params}, got {actual_params}")
                returns = exp.get("returns")
                if returns and isinstance(returns, str) and returns.strip() and returns.strip().lower() != "none":
                    if node.returns is None:
                        errors.append(f"Export '{name}' missing return type annotation")
            elif kind == "class":
                constructor = exp.get("constructor")
                if isinstance(constructor, dict) and isinstance(constructor.get("parameters"), list):
                    init_node = None
                    for child in ast.iter_child_nodes(node):
                        if isinstance(child, ast.FunctionDef) and child.name == "__init__":
                            init_node = child
                            break
                    if init_node is None:
                        errors.append(f"Export '{name}' missing constructor __init__")
                    else:
                        actual_params = [arg.arg for arg in init_node.args.args if arg.arg != "self"]
                        expected_params = [p["name"] for p in constructor["parameters"] if isinstance(p, dict) and "name" in p]
                        if actual_params != expected_params:
                            errors.append(f"Export '{name}' constructor parameter mismatch: expected {expected_params}, got {actual_params}")
                methods = exp.get("methods")
                if isinstance(methods, list):
                    for meth in methods:
                        if not isinstance(meth, dict):
                            continue
                        meth_name = meth.get("name")
                        if not meth_name:
                            continue
                        meth_node = None
                        for child in ast.iter_child_nodes(node):
                            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == meth_name:
                                meth_node = child
                                break
                        if meth_node is None:
                            errors.append(f"Export '{name}' missing method: {meth_name}")
                            continue
                        meth_params = meth.get("parameters")
                        if isinstance(meth_params, list):
                            actual_params = [arg.arg for arg in meth_node.args.args if arg.arg != "self"]
                            expected_params = [p["name"] for p in meth_params if isinstance(p, dict) and "name" in p]
                            if actual_params != expected_params:
                                errors.append(f"Export '{name}' method '{meth_name}' parameter mismatch: expected {expected_params}, got {actual_params}")
                        meth_returns = meth.get("returns")
                        if meth_returns and isinstance(meth_returns, str) and meth_returns.strip() and meth_returns.strip().lower() != "none":
                            if meth_node.returns is None:
                                errors.append(f"Export '{name}' method '{meth_name}' missing return type annotation")

        errors.sort()
        return {"valid": len(errors) == 0, "errors": errors}