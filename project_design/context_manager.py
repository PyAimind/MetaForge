import ast

class ContextManager:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.modules = {}

    def add_module(self, filename, code):
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return
        classes = []
        functions = []
        imports = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, ast.FunctionDef):
                functions.append(node.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        exports = classes + functions
        module_info = {
            "classes": classes,
            "functions": functions,
            "imports": imports,
            "exports": exports,
            "dependencies": []
        }
        self.modules[filename] = module_info