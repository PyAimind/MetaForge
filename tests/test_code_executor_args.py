import os
import sys
import tempfile

# افزودن ریشهٔ پروژه به مسیر جستجوی پایتون
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from project_design.code_executor import CodeExecutor

with tempfile.TemporaryDirectory() as tmp:
    filepath = os.path.join(tmp, "args_test.py")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(
            "import sys\n"
            "if len(sys.argv) > 1:\n"
            "    print(sys.argv[1])\n"
            "else:\n"
            "    print('no args')\n"
        )

    executor = CodeExecutor()

    result_with_args = executor.execute(filepath, args=["hello"])
    assert result_with_args["return_code"] == 0
    assert result_with_args["stdout"].strip() == "hello"

    result_without_args = executor.execute(filepath)
    assert result_without_args["return_code"] == 0
    assert result_without_args["stdout"].strip() == "no args"

    print("PHASE 1 CODE EXECUTOR ARGS PASSED")