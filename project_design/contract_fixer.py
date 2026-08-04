import ast

def fix_contract(code: str, exports: list) -> str:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code

    top_level = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            top_level[node.name] = node

    for exp in exports:
        if not isinstance(exp, dict):
            continue
        name = exp.get("name")
        kind = exp.get("kind")
        if not name or kind not in ("function", "class"):
            continue
        node = top_level.get(name)
        if node is None:
            continue

        if kind == "function" and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _apply_function_contract(node, exp)
        elif kind == "class" and isinstance(node, ast.ClassDef):
            _apply_class_contract(node, exp)

    return ast.unparse(tree)


def _apply_function_contract(func_node, exp):
    _annotate_params(func_node.args.args, exp.get("parameters", []))
    _annotate_return(func_node, exp.get("returns"))


def _apply_class_contract(class_node, exp):
    methods = exp.get("methods")
    if isinstance(methods, list):
        for meth_spec in methods:
            if not isinstance(meth_spec, dict):
                continue
            m_name = meth_spec.get("name")
            if not m_name:
                continue
            for node in class_node.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == m_name:
                    _apply_function_contract(node, meth_spec)
                    break
    constructor = exp.get("constructor")
    if isinstance(constructor, dict):
        for node in class_node.body:
            if isinstance(node, ast.FunctionDef) and node.name == "__init__":
                c_params = constructor.get("parameters", [])
                _annotate_params(node.args.args, c_params)
                break


def _annotate_params(args, param_specs):
    spec_map = {}
    for p in param_specs:
        if isinstance(p, dict) and "name" in p and "type" in p:
            spec_map[p["name"]] = p["type"]
    for arg in args:
        if arg.annotation is None and arg.arg in spec_map:
            arg.annotation = ast.Name(id=spec_map[arg.arg], ctx=ast.Load())


def _annotate_return(func_node, returns_spec):
    if func_node.returns is None and isinstance(returns_spec, str) and returns_spec.strip():
        func_node.returns = ast.Name(id=returns_spec.strip(), ctx=ast.Load())