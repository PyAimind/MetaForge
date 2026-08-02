import ast

class SemanticVisitor(ast.NodeVisitor):
    def __init__(self, dependency_modules: set):
        self.dependency_modules = dependency_modules
        self.imports = {}
        self.symbols = {}
        self.calls = []

    def visit_Import(self, node):
        for alias in node.names:
            module_basename = alias.name + ".py"
            if module_basename in self.dependency_modules:
                local_name = alias.asname if alias.asname else alias.name
                self.imports[local_name] = {"module": module_basename, "original_name": None}

    def visit_ImportFrom(self, node):
        if node.module is None:
            return
        module_basename = node.module + ".py"
        if module_basename not in self.dependency_modules:
            return
        for alias in node.names:
            local_name = alias.asname if alias.asname else alias.name
            original_name = alias.name
            self.imports[local_name] = {"module": module_basename, "original_name": original_name}

    def visit_Assign(self, node):
        if not isinstance(node.value, ast.Call):
            return
        func = node.value.func
        if isinstance(func, ast.Name):
            name = func.id
            if name not in self.imports:
                return
            imp = self.imports[name]
            class_name = imp["original_name"] if imp["original_name"] else name
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.symbols[target.id] = {
                        "type": class_name,
                        "module": imp["module"],
                        "line": node.lineno
                    }
                elif isinstance(target, ast.Tuple):
                    for elt in target.elts:
                        if isinstance(elt, ast.Name):
                            self.symbols[elt.id] = {
                                "type": class_name,
                                "module": imp["module"],
                                "line": node.lineno
                            }
        elif isinstance(func, ast.Attribute):
            base = func.value
            attr = func.attr
            if isinstance(base, ast.Name) and base.id in self.imports:
                imp = self.imports[base.id]
                if imp["original_name"] is None:
                    class_name = attr
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            self.symbols[target.id] = {
                                "type": class_name,
                                "module": imp["module"],
                                "line": node.lineno
                            }
                        elif isinstance(target, ast.Tuple):
                            for elt in target.elts:
                                if isinstance(elt, ast.Name):
                                    self.symbols[elt.id] = {
                                        "type": class_name,
                                        "module": imp["module"],
                                        "line": node.lineno
                                    }

    def visit_Call(self, node):
        call_info = {
            "line": node.lineno,
            "func_name": None,
            "base": None,
            "is_attribute": False,
            "args": [ast.unparse(arg) for arg in node.args],
            "keywords": {kw.arg: ast.unparse(kw.value) for kw in node.keywords if kw.arg}
        }
        if isinstance(node.func, ast.Name):
            call_info["func_name"] = node.func.id
        elif isinstance(node.func, ast.Attribute):
            call_info["is_attribute"] = True
            call_info["func_name"] = ast.unparse(node.func)
            if isinstance(node.func.value, ast.Name):
                call_info["base"] = node.func.value.id
        self.calls.append(call_info)