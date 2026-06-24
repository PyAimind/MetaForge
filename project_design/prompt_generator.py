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

    # === Build the prompt ===
    prompt = f"Write a Python file named `{filename}`.\n"

    if description:
        prompt += f"{description}\n\n"
    else:
        prompt += "\n"

    # Dependencies
    if dependencies:
        prompt += f"### Dependencies\nThe module depends on: {dep_list}. Import and use only the public functions/classes from those files. Do not modify the dependency files.\n\n"
    else:
        prompt += "### Dependencies\nThis module has no dependencies.\n\n"

    # Implementation Requirements
    prompt += """### Implementation Requirements
- The public API (function signatures, class names) will be provided by the Engineer. Use exactly what is specified in the prompt.
- Every function must have type hints for parameters and return value.
- Keep each function under 30 lines. The whole file should be under 200 lines.
- Handle edge cases and invalid inputs explicitly.
- Use simple and modern Python.
"""

    # Testability
    prompt += """### Testability
- The module must be easily importable and testable.
- Do not include any `if __name__ == "__main__"` block.
"""

    # Strict Constraints
    prompt += """### Strict Constraints
- Use ONLY the Python standard library.
- Allowed modules: os, sys, json, queue, subprocess, tempfile, datetime.
- Do NOT import anything outside this list.
- The file must contain NO comments — only code.
- Deliver ONLY raw Python code. No explanations, no markdown fences.
- The first line of your response must be the Python code.
"""

    # Error Handling
    prompt += """### Error Handling
- If a required dependency is missing, raise a clear `ImportError`.
- For invalid inputs, raise `ValueError` with a descriptive message.
- Do not print anything. Use exceptions only.
"""

    return prompt

