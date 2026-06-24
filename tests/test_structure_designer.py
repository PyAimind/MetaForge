import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from project_design.structure_designer import design_structure

r = design_structure("Simple Calculator")
assert r["project_name"] == "Simple Calculator"
assert len(r["phases"]) == 3
assert set(r.keys()) == {"project_name", "phases"}
p0 = r["phases"][0]
assert p0["name"] == "Input Handler"
assert len(p0["modules"]) == 1
m0 = p0["modules"][0]
assert m0["filename"] == "input_handler.py"
assert m0["dependencies"] == []
p1 = r["phases"][1]
assert p1["name"] == "Calculator Logic"
assert len(p1["modules"]) == 1
m1 = p1["modules"][0]
assert m1["filename"] == "calculator.py"
assert m1["dependencies"] == ["input_handler.py"]
p2 = r["phases"][2]
assert p2["name"] == "Main Entry"
assert len(p2["modules"]) == 1
m2 = p2["modules"][0]
assert m2["filename"] == "main.py"
assert m2["dependencies"] == ["input_handler.py", "calculator.py"]

r2 = design_structure("Simple Calculator")
r2["project_name"] = "CHANGED"
r2["phases"][0]["name"] = "HACKED"
r2["phases"][0]["modules"][0]["dependencies"].append("evil.py")
r3 = design_structure("Simple Calculator")
assert r3["project_name"] == "Simple Calculator"
assert r3["phases"][0]["name"] == "Input Handler"
assert r3["phases"][0]["modules"][0]["dependencies"] == []

r4 = design_structure("  simple calculator  ")
assert r4["project_name"] == "Simple Calculator"
assert len(r4["phases"]) == 3

r5 = design_structure("")
assert r5["project_name"] == "Untitled"
assert len(r5["phases"]) == 1
assert r5["phases"][0]["modules"][0]["filename"] == "main.py"
assert r5["phases"][0]["modules"][0]["dependencies"] == []

r6 = design_structure(None)
assert r6["project_name"] == "Untitled"

r7 = design_structure("Complex Web App")
assert r7["project_name"] == "Complex Web App"
assert len(r7["phases"]) == 1

print("PHASE 5.1 PASSED")