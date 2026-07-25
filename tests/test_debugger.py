import sys
import os
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.debugger import Debugger
from memory.knowledge_base import KnowledgeBase

errors = []

with tempfile.TemporaryDirectory() as tmp:
    dbg = Debugger()
    try:
        res = dbg.analyze_error("main.py", 'Traceback (most recent call last):\n  File "main.py", line 12, in <module>\n    print(\n         ^\nSyntaxError: unexpected EOF while parsing', "", 1)
        assert res["diagnosis"] == "SyntaxError"
        assert res["confidence"] == 0.99
        assert "line 12" in res["root_cause"]
    except AssertionError as e:
        errors.append(f"[TEST1] SyntaxError detection: {e}")

    dbg2 = Debugger()
    try:
        res = dbg2.analyze_error("test.py", "ModuleNotFoundError: No module named 'calculator'", "", 1)
        assert res["diagnosis"] == "ImportError"
        assert res["confidence"] == 0.95
        assert "calculator" in res["root_cause"] and "calculator" in res["suggested_fix"]
    except AssertionError as e:
        errors.append(f"[TEST2] ImportError detection: {e}")

    dbg3 = Debugger()
    try:
        res = dbg3.analyze_error("test.py", "NameError: name 'x' is not defined", "", 1)
        assert res["diagnosis"] == "NameError"
        assert "x" in res["root_cause"]
    except AssertionError as e:
        errors.append(f"[TEST3] NameError detection: {e}")

    dbg4 = Debugger()
    try:
        res = dbg4.analyze_error("test.py", "", "", -1)
        assert res["diagnosis"] == "TimeoutError"
        assert res["confidence"] == 0.6
    except AssertionError as e:
        errors.append(f"[TEST4] TimeoutError detection: {e}")

    dbg5 = Debugger()
    try:
        res = dbg5.analyze_error("test.py", 'Traceback (most recent call last):\n  File "main.py", line 5, in <module>\n    result = 1 / 0\nZeroDivisionError: division by zero', "", 1)
        assert res["diagnosis"] == "RuntimeError"
        assert res["confidence"] == 0.7
    except AssertionError as e:
        errors.append(f"[TEST5] RuntimeError detection: {e}")

    dbg6 = Debugger()
    try:
        res = dbg6.analyze_error("test.py", "Some completely unrecognizable error message", "", 0)
        assert res["diagnosis"] == "UnknownError"
        assert res["confidence"] == 0.3
    except AssertionError as e:
        errors.append(f"[TEST6] UnknownError detection: {e}")

    kb_path = os.path.join(tmp, "kb.json")
    kb = KnowledgeBase(kb_path)
    kb.add_failure("RuntimeError The code crashed at runtime", "Use local variables instead of global ones.", ["runtime"])
    dbg7 = Debugger(knowledge_base=kb)
    try:
        res = dbg7.analyze_error("test.py", "some error", "", 1)
        assert res["diagnosis"] == "RuntimeError"
        assert "In a previous similar case" in res["suggested_fix"]
        assert res["confidence"] > 0.7
    except AssertionError as e:
        errors.append(f"[TEST7] KnowledgeBase enrichment: {e}")

if errors:
    print("PHASE 16.2 FAILED")
    for err in errors:
        print(err)
else:
    print("PHASE 16.2 PASSED")