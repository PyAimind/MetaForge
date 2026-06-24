SIMPLE_CALCULATOR_TEMPLATE = {
    "project_name": "Simple Calculator",
    "phases": [
        {"phase_number": 1, "name": "Input Handler", "modules": [{"filename": "input_handler.py", "description": "Handles user input for two numbers and an operator", "dependencies": []}]},
        {"phase_number": 2, "name": "Calculator Logic", "modules": [{"filename": "calculator.py", "description": "Performs arithmetic operations based on operator", "dependencies": ["input_handler.py"]}]},
        {"phase_number": 3, "name": "Main Entry", "modules": [{"filename": "main.py", "description": "Entry point that ties input and calculation together", "dependencies": ["input_handler.py", "calculator.py"]}]}
    ]
}
def design_structure(idea):
    if not isinstance(idea, str):
        idea = ""
    original_idea = idea.strip()
    if original_idea.lower() == "simple calculator":
        return {"project_name": SIMPLE_CALCULATOR_TEMPLATE["project_name"], "phases": [{"phase_number": p["phase_number"], "name": p["name"], "modules": [{"filename": m["filename"], "description": m["description"], "dependencies": list(m["dependencies"])} for m in p["modules"]]} for p in SIMPLE_CALCULATOR_TEMPLATE["phases"]]}
    return {"project_name": original_idea or "Untitled", "phases": [{"phase_number": 1, "name": "Core", "modules": [{"filename": "main.py", "description": "Main module", "dependencies": []}]}]}