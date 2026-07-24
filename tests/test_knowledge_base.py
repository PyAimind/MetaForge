import sys
import os
import tempfile
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from memory.knowledge_base import KnowledgeBase

with tempfile.TemporaryDirectory() as tmp:
    kb_path = os.path.join(tmp, "kb.json")
    kb = KnowledgeBase(kb_path)

    assert kb.add_lesson("Test", "A test lesson", ["test"])
    results = kb.search(query="test")
    assert any(e["title"] == "Test" for e in results["lessons"])

    assert not kb.add_lesson("Test", "A test lesson", ["test"])
    assert len(kb.data["lessons"]) == 1

    assert kb.add_success("Ok", "worked", ["demo"])
    assert kb.add_failure("Fail", "broken", ["demo"])
    res = kb.search(tags=["demo"])
    assert any(e["title"] == "Ok" for e in res["successes"])
    assert any(e["title"] == "Fail" for e in res["failures"])

    kb.add_lesson("Python Web", "Web dev lesson", ["python", "web"])
    res_any = kb.search(tags=["python"], match="any")
    assert any(e["title"] == "Python Web" for e in res_any["lessons"])

    res_all = kb.search(tags=["python", "web"], match="all")
    assert any(e["title"] == "Python Web" for e in res_all["lessons"])
    res_all_none = kb.search(tags=["python", "mobile"], match="all")
    assert not any(e["title"] == "Python Web" for e in res_all_none["lessons"])

    kb2 = KnowledgeBase(os.path.join(tmp, "kb2.json"))
    empty_res = kb2.search()
    assert empty_res["lessons"] == []
    assert empty_res["successes"] == []
    assert empty_res["failures"] == []

    kb3 = KnowledgeBase(os.path.join(tmp, "kb3.json"))
    kb3.add_lesson("Old", "first", ["time"])
    time.sleep(0.02)
    kb3.add_lesson("New", "second", ["time"])
    sorted_lessons = kb3.search(tags=["time"])["lessons"]
    assert sorted_lessons[0]["title"] == "New"
    assert sorted_lessons[1]["title"] == "Old"

    persist_path = os.path.join(tmp, "persist.json")
    kb_persist = KnowledgeBase(persist_path)
    kb_persist.add_lesson("PersistMe", "persistence test", ["persist"])
    kb_reload = KnowledgeBase(persist_path)
    reload_results = kb_reload.search(query="PersistMe")
    assert any(e["title"] == "PersistMe" for e in reload_results["lessons"])

    corrupted_path = os.path.join(tmp, "corrupted.json")
    with open(corrupted_path, 'w') as f:
        f.write("not valid json{{{")
    kb_corrupt = KnowledgeBase(corrupted_path)
    assert kb_corrupt.data["lessons"] == []
    assert kb_corrupt.data["successes"] == []
    assert kb_corrupt.data["failures"] == []

    kb_case = KnowledgeBase(os.path.join(tmp, "case.json"))
    kb_case.add_lesson("CaseTest", "case insensitive", ["search"])
    case_results = kb_case.search(query="CASETEST")
    assert any(e["title"] == "CaseTest" for e in case_results["lessons"])

    empty_search = kb.search(query="nonexistent")
    assert empty_search["lessons"] == []
    assert empty_search["successes"] == []
    assert empty_search["failures"] == []

    kb_dup = KnowledgeBase(os.path.join(tmp, "dup.json"))
    assert kb_dup.add_lesson("Dup", "first desc", ["duplicate"])
    assert not kb_dup.add_lesson("Dup", "second desc", ["duplicate"])
    assert len(kb_dup.data["lessons"]) == 1

    print("PHASE 15.2 PASSED")