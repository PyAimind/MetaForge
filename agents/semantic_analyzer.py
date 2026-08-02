import ast
import os
from agents.semantic_visitor import SemanticVisitor

class SemanticAnalyzer:
    def __init__(self):
        pass

    def _get_export(self, contract, name):
        for exp in contract.get("exports", []):
            if isinstance(exp, dict) and exp.get("name") == name:
                return exp
        return None

    def _validate_args(self, params, args, keywords):
        errors = []
        expected_count = len(params)
        actual_count = len(args)
        if expected_count != actual_count:
            errors.append((expected_count, actual_count))
        param_names = {p.get("name") for p in params if isinstance(p, dict)}
        for kw in keywords:
            if kw not in param_names:
                errors.append(("unexpected_keyword", kw))
        return errors

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

        for call in visitor.calls:
            line = call["line"]
            func_name = call["func_name"]
            base = call["base"]
            is_attr = call["is_attribute"]
            args = call["args"]
            keywords = call["keywords"]

            if not is_attr:
                if func_name not in visitor.imports:
                    continue
                imp = visitor.imports[func_name]
                module_key = imp["module"]
                contract = dependency_contracts.get(module_key, {})
                lookup_name = imp["original_name"] if imp["original_name"] else func_name
                exp = self._get_export(contract, lookup_name)
                if exp is None:
                    errors.append({
                        "type": "missing_export",
                        "module": module_key,
                        "function": lookup_name,
                        "line": line
                    })
                    continue
                kind = exp.get("kind")
                if kind == "class":
                    constructor = exp.get("constructor")
                    if isinstance(constructor, dict):
                        params = constructor.get("parameters", [])
                        if isinstance(params, list):
                            validations = self._validate_args(params, args, keywords)
                            for v in validations:
                                if v[0] == "unexpected_keyword":
                                    errors.append({
                                        "type": "unexpected_keyword_argument",
                                        "module": module_key,
                                        "class": lookup_name,
                                        "function": "__init__",
                                        "detail": v[1],
                                        "line": line
                                    })
                                else:
                                    errors.append({
                                        "type": "constructor_mismatch",
                                        "module": module_key,
                                        "class": lookup_name,
                                        "expected": [p.get("name", "?") for p in params if isinstance(p, dict)],
                                        "received": args,
                                        "line": line
                                    })
                elif kind == "function":
                    params = exp.get("parameters", [])
                    if isinstance(params, list):
                        validations = self._validate_args(params, args, keywords)
                        for v in validations:
                            if v[0] == "unexpected_keyword":
                                errors.append({
                                    "type": "unexpected_keyword_argument",
                                    "module": module_key,
                                    "function": lookup_name,
                                    "detail": v[1],
                                    "line": line
                                })
                            else:
                                errors.append({
                                    "type": "argument_count_mismatch",
                                    "module": module_key,
                                    "function": lookup_name,
                                    "expected": [p.get("name", "?") for p in params if isinstance(p, dict)],
                                    "received": args,
                                    "line": line
                                })
            else:
                if base is None:
                    continue
                attr = func_name.split(".")[-1] if func_name else ""
                if base in visitor.imports:
                    imp = visitor.imports[base]
                    module_key = imp["module"]
                    contract = dependency_contracts.get(module_key, {})
                    orig = imp["original_name"]
                    if orig is None:
                        exp = self._get_export(contract, attr)
                        if exp is None:
                            errors.append({
                                "type": "missing_export",
                                "module": module_key,
                                "function": attr,
                                "line": line
                            })
                            continue
                        kind = exp.get("kind")
                        if kind == "class":
                            constructor = exp.get("constructor")
                            if isinstance(constructor, dict):
                                params = constructor.get("parameters", [])
                                if isinstance(params, list):
                                    validations = self._validate_args(params, args, keywords)
                                    for v in validations:
                                        if v[0] == "unexpected_keyword":
                                            errors.append({
                                                "type": "unexpected_keyword_argument",
                                                "module": module_key,
                                                "class": attr,
                                                "function": "__init__",
                                                "detail": v[1],
                                                "line": line
                                            })
                                        else:
                                            errors.append({
                                                "type": "constructor_mismatch",
                                                "module": module_key,
                                                "class": attr,
                                                "expected": [p.get("name", "?") for p in params if isinstance(p, dict)],
                                                "received": args,
                                                "line": line
                                            })
                        elif kind == "function":
                            params = exp.get("parameters", [])
                            if isinstance(params, list):
                                validations = self._validate_args(params, args, keywords)
                                for v in validations:
                                    if v[0] == "unexpected_keyword":
                                        errors.append({
                                            "type": "unexpected_keyword_argument",
                                            "module": module_key,
                                            "function": attr,
                                            "detail": v[1],
                                            "line": line
                                        })
                                    else:
                                        errors.append({
                                            "type": "argument_count_mismatch",
                                            "module": module_key,
                                            "function": attr,
                                            "expected": [p.get("name", "?") for p in params if isinstance(p, dict)],
                                            "received": args,
                                            "line": line
                                        })
                    else:
                        class_exp = self._get_export(contract, orig)
                        if class_exp is None or class_exp.get("kind") != "class":
                            continue
                        methods = class_exp.get("methods", [])
                        if not isinstance(methods, list):
                            continue
                        method = None
                        for m in methods:
                            if isinstance(m, dict) and m.get("name") == attr:
                                method = m
                                break
                        if method is None:
                            errors.append({
                                "type": "missing_method",
                                "module": module_key,
                                "class": orig,
                                "function": attr,
                                "line": line
                            })
                            continue
                        m_params = method.get("parameters", [])
                        if not isinstance(m_params, list):
                            m_params = []
                        validations = self._validate_args(m_params, args, keywords)
                        for v in validations:
                            if v[0] == "unexpected_keyword":
                                errors.append({
                                    "type": "unexpected_keyword_argument",
                                    "module": module_key,
                                    "class": orig,
                                    "function": attr,
                                    "detail": v[1],
                                    "line": line
                                })
                            else:
                                errors.append({
                                    "type": "argument_count_mismatch",
                                    "module": module_key,
                                    "class": orig,
                                    "function": attr,
                                    "expected": [p.get("name", "?") for p in m_params if isinstance(p, dict)],
                                    "received": args,
                                    "line": line
                                })
                elif base in visitor.symbols:
                    sym = visitor.symbols[base]
                    module_key = sym["module"]
                    contract = dependency_contracts.get(module_key, {})
                    class_exp = self._get_export(contract, sym["type"])
                    if class_exp is None or class_exp.get("kind") != "class":
                        continue
                    methods = class_exp.get("methods", [])
                    if not isinstance(methods, list):
                        continue
                    method = None
                    for m in methods:
                        if isinstance(m, dict) and m.get("name") == attr:
                            method = m
                            break
                    if method is None:
                        errors.append({
                            "type": "missing_method",
                            "module": module_key,
                            "class": sym["type"],
                            "function": attr,
                            "line": line
                        })
                        continue
                    m_params = method.get("parameters", [])
                    if not isinstance(m_params, list):
                        m_params = []
                    validations = self._validate_args(m_params, args, keywords)
                    for v in validations:
                        if v[0] == "unexpected_keyword":
                            errors.append({
                                "type": "unexpected_keyword_argument",
                                "module": module_key,
                                "class": sym["type"],
                                "function": attr,
                                "detail": v[1],
                                "line": line
                            })
                        else:
                            errors.append({
                                "type": "argument_count_mismatch",
                                "module": module_key,
                                "class": sym["type"],
                                "function": attr,
                                "expected": [p.get("name", "?") for p in m_params if isinstance(p, dict)],
                                "received": args,
                                "line": line
                            })

        errors.sort(key=lambda e: e.get("line", 0) or 0)
        return {"valid": len(errors) == 0, "errors": errors}