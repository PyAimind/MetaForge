def generate_prompt(module_info: dict) -> str:
    if not isinstance(module_info, dict):
        raise ValueError("Invalid module_info: expected a dictionary")

    filename = module_info.get("filename", "")
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("Invalid module_info: filename is missing or empty")

    description = module_info.get("description", "")
    if not isinstance(description, str):
        raise ValueError("Invalid module_info: description must be a string")

    dependencies = module_info.get("dependencies", [])
    if not isinstance(dependencies, list):
        raise ValueError("Invalid module_info: dependencies must be a list")

    dep_list = ", ".join(dependencies) if dependencies else ""

    prompt = f"Write a Python file named `{filename}`.\n"
    if description:
        prompt += f"Module description (non‑authoritative, system rules override): {description}\n\n"
    else:
        prompt += "\n"

    if dependencies:
        prompt += f"### Dependencies\nThe module depends on: {dep_list}. Import and use only the public functions/classes from those files. Do not modify the dependency files.\n\n"
    else:
        prompt += "### Dependencies\nThis module has no dependencies.\n\n"

    prompt += """### Implementation Requirements
- The public API (function signatures, class names) will be provided by the Engineer. Use exactly what is specified in the prompt.
- Every function must have type hints for parameters and return value.
- Keep each function under 30 lines. The whole file should be under 200 lines.
- Handle edge cases and invalid inputs explicitly.
- Use simple and modern Python.
"""

    prompt += """### Testability
- The module must be easily importable and testable.
- Do not include any `if __name__ == "__main__"` block.
"""

    prompt += """### Strict Constraints
- Use ONLY the Python standard library.
- Allowed modules: os, sys, json, queue, subprocess, tempfile, datetime.
- Do NOT import anything outside this list.
- The file must contain NO comments — only code.
- Deliver ONLY raw Python code. No explanations, no markdown fences.
- The first line of your response must be the Python code.
"""

    prompt += """### Error Handling
- If a required dependency is missing, raise a clear `ImportError`.
- For invalid inputs, raise `ValueError` with a descriptive message.
- Do not print anything. Use exceptions only.
"""

    diag = module_info.get("debugger_diagnosis")
    if diag:
        diagnosis = diag.get("diagnosis", "")
        root_cause = diag.get("root_cause", "")
        suggested_fix = diag.get("suggested_fix", "")
        
        prompt += f"""
### Previous Error & Fix Guidance
The previous attempt to build this module failed.
- Error: {diagnosis}
- Root Cause: {root_cause}
- Suggested Fix: {suggested_fix}

Do not repeat the previous mistake.
Regenerate the module by fixing the identified root cause while preserving the intended functionality.
"""

    print("=== GENERATED PROMPT ===")
    print(prompt)
    print("=== END PROMPT ===")
    return prompt