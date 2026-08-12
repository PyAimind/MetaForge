import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from project_design.prompt_generator import generate_prompt

# 1. CLI module must contain the contract
cli_info = {
    "filename": "cli.py",
    "description": "CLI entry point",
    "dependencies": ["todo_manager.py"],
    "exports": [],
    "required_imports": [],
}
prompt = generate_prompt(cli_info)
assert "### CLI Output Contract (MANDATORY)" in prompt, "FAIL: CLI contract missing"
print("1. CLI module contains mandatory output contract: PASS")

# 2. Non-CLI module must not contain the contract
non_cli_info = {
    "filename": "todo_manager.py",
    "description": "Todo manager",
    "dependencies": ["storage.py"],
    "exports": [{"name": "add_todo", "kind": "function", "parameters": [], "returns": "None"}],
    "required_imports": [],
}
prompt2 = generate_prompt(non_cli_info)
assert "### CLI Output Contract (MANDATORY)" not in prompt2, "FAIL: Non-CLI module wrongly contains CLI contract"
print("2. Non-CLI module does not contain CLI contract: PASS")

# 3. Existing Implementation Requirements still present
assert "### Implementation Requirements" in prompt, "FAIL: Implementation Requirements missing"
print("3. Implementation Requirements section still present: PASS")

print("\nAll verification checks passed.")