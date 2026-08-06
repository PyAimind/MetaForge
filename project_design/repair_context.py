class RepairContext:
    def __init__(self, module_name: str, filepath: str = ""):
        self.module_name = module_name
        self.filepath = filepath
        self.current_code = None
        self.contract = None
        self.api_errors = []
        self.semantic_errors = []
        self.runtime_error = None
        self.debugger_analysis = None
        self.previous_attempts = 0

    def is_empty(self) -> bool:
        return (
            not self.api_errors
            and not self.semantic_errors
            and self.runtime_error is None
            and self.debugger_analysis is None
        )

    def summary(self) -> str:
        if self.filepath:
            lines = [f"Repair Target: {self.module_name} ({self.filepath})"]
        else:
            lines = [f"Repair Target: {self.module_name}"]
        lines.append(f"Previous Attempts: {self.previous_attempts}")
        if self.api_errors:
            lines.append("API Errors:")
            for err in self.api_errors:
                lines.append(f"  - {err}")
        if self.semantic_errors:
            lines.append("Semantic Errors:")
            for err in self.semantic_errors:
                lines.append(f"  - {err}")
        if self.runtime_error is not None:
            lines.append("Runtime Error:")
            lines.append(f"  {self.runtime_error}")
        if self.debugger_analysis is not None:
            lines.append("Debugger Analysis:")
            for key in ("diagnosis", "root_cause", "suggested_fix", "confidence"):
                if key in self.debugger_analysis:
                    lines.append(f"  {key}: {self.debugger_analysis[key]}")
        return "\n".join(lines)

    def __repr__(self):
        return f"RepairContext('{self.module_name}', filepath='{self.filepath}')"