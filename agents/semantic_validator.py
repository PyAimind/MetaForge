import ast
import os
from agents.semantic_visitor import SemanticVisitor
from agents.semantic_validator import SemanticValidator

class SemanticAnalyzer:
    def __init__(self):
        pass

    def analyze(self, filepath: str, dependency_contracts: dict) -> dict:
        if not isinstance(filepath, str) or not filepath.strip() or not os.path.isfile(filepath):
            return {"valid": False, "errors": [{"type": "file_not_found", "line": None}]}
        if not isinstance(dependency_contracts, dict):
            return {"valid": False, "errors": [{"type": "invalid_input", "line": None}]}

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                source = f.read()
            tree = ast.parse(source, filename=filepath)
        except SyntaxError as e:
            return {"valid": False, "errors": [{"type": "syntax_error", "line": e.lineno, "detail": str(e)}]}

        dependency_modules = set(dependency_contracts.keys())
        visitor = SemanticVisitor(dependency_modules)
        visitor.visit(tree)

        errors = []
        validator = SemanticValidator()
        for call in visitor.calls:
            errors.extend(
                validator.validate_call(
                    call,
                    visitor.imports,
                    visitor.symbols,
                    dependency_contracts
                )
            )

        errors.sort(key=lambda e: e.get("line", 0) or 0)
        return {"valid": len(errors) == 0, "errors": errors}