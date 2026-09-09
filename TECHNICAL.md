# MetaForge v3.3 – Technical Architecture

## Architecture Overview

MetaForge v3.3 is a multi-agent pipeline that transforms a natural language project idea into a tested, runnable multi-module Python codebase. The system is built around specialised agents that communicate through a central message bus using per-agent message queues, with a shared workspace for state and logging. An LLM provider integration enables intelligent design and code generation.

### New in v3.3

- **Generic Acceptance Testing Engine** – Tester is no longer hardcoded for Todo. It executes a project-agnostic `acceptance_tests` specification produced by the Engineer/StructureDesigner.
- **Entrypoint-Aware Validation** – Modules with `type: "entrypoint"` (e.g., `cli.py`) skip API Inspector structural checks, while `library` modules continue to be validated strictly. All modules still pass through Tester and final acceptance.
- **Shared Runtime Isolation** – All acceptance tests for a project run inside a single temporary directory, preserving state across sequential commands within the batch while preventing leakage between runs.
- **Acceptance Criteria Injection** – Coder and repair prompts now include acceptance test requirements as mandatory behavioural contracts, improving alignment between generated code and expected behaviour.
- **Robust Acceptance Test Generation** – StructureDesignerLLM now applies deterministic rules for generating acceptance tests: help tests, required-argument error tests, and simple success tests, while avoiding fragile filesystem-dependent or optional-feature tests.
- **Multi-Project End-to-End Validation** – Validated with Todo App, Temperature Converter, Password Generator, Calculator, and partially with File Organizer.

### Core Components

- **Supervisor** – orchestrates the entire workflow, manages state transitions, and handles error recovery. It stores `acceptance_tests`, manages `acceptance_repair_pending`, and decides when to run final acceptance.
- **Engineer** – designs the project structure and generates contract-aware coding prompts. During repair, it can generate a multi-module repair prompt containing all relevant module sources and contracts.
- **Coder** – writes Python code using an LLM-powered generator. It reads `contracts.json`, injects contracts into prompts, and updates `generated` flags. In repair mode, it can parse multi-module JSON responses and write multiple corrected files.
- **Tester** – executes generated code safely and returns structured results. Its acceptance test executor is now generic and runs in a shared temporary directory per project.
- **Debugger** – analyses test failures and produces structured diagnoses.
- **Contract Generator** – extracts public API contracts from the project structure and persists them as `contracts.json`, now also preserving `type` metadata.
- **API Inspector** – validates a generated Python file against its declared contract using AST analysis. Skipped for entrypoint modules in v3.3.
- **Semantic Analyzer** – performs cross-module semantic checks using dependency contracts.
- **MessageChannel** – thread-safe queue-based message bus.
- **WorkspaceManager** – persistent short-term memory backed by JSON files.
- **ContextManager** – collects structural information about generated modules.
- **KnowledgeBase** – stores lessons, successful patterns, and failures.
- **LLMProvider** – HTTP client for the DeepSeek API or compatible endpoint.

The system follows the **Supervisor-Worker** pattern: the Supervisor issues sequential commands, each agent processes them and responds through the message bus. Critical state is managed in-memory by the Supervisor and persisted to the workspace.

---

## Agent Roles (v3.3 updates)

### Supervisor (`agents/supervisor.py`)

- Owns the project idea, overall status, module list, current module index, prompt cache, per-module fix counters, `acceptance_tests`, and `acceptance_repair_pending`.
- State machine:
  1. **designing** → sends `design_structure` to Engineer.
  2. **waiting_for_engineer** → receives structure, stores it, extracts `acceptance_tests`, invokes ContractGenerator, requests prompts.
  3. **waiting_for_coder** → receives filepath. Validation order depends on module type:
     - If `type == "entrypoint"`, skip API Inspector; otherwise run API Inspector first.
     - Semantic Analyzer second (cross-module semantic validation if dependencies exist).
     - On failure, blocks Tester, increments fix counter, triggers repair.
  4. **waiting_for_tester** → processes test results: on success, sets `validated` and advances; on failure/timeout, invokes Debugger and retries.
  5. After all modules pass, if `acceptance_tests` exists, sends them to Tester and enters **waiting_for_acceptance_tests**; if `acceptance_tests` is empty, logs an error and fails.
  6. **waiting_for_acceptance_tests** → if passed, mark project completed; if failed, increment `fix_attempts["__acceptance__"]`, build a project-level repair context, set `acceptance_repair_pending=True`, and request a repair from Engineer.
- During acceptance repair:
  - Placeholder module is selected based on the `entrypoint` of the first acceptance test (e.g., `cli.py`), not `modules[0]`.
  - After Coder success with `acceptance_repair_pending`, the same `acceptance_tests` are re-sent to Tester.
  - If Coder returns error during acceptance repair, Supervisor retries until max attempts, then transitions to `error`.

### Engineer (`agents/engineer.py`)

- Accepts `design_structure`, `generate_prompts`, `generate_single_prompt`.
- During repair, if the repair context contains `all_modules`, the Engineer builds a **multi-module repair prompt** that includes every module’s source code and contract, and instructs the LLM to return a JSON object mapping module filenames to corrected code.
- For single-module repairs, the previous behaviour remains unchanged.

### Coder (`agents/coder.py`)

- Before generation, loads the module’s contract from `contracts.json` and injects it into the generation prompt.
- For entrypoint modules, reads `acceptance_tests` from the workspace structure and includes them in `module_info`.
- In repair mode:
  - Uses the Engineer-provided prompt when available.
  - Includes acceptance tests and previous acceptance failure details in the repair prompt to guide the LLM.
  - If `all_modules` is present, parses the LLM response as a JSON object, validates each returned module against the expected module set, and writes all valid corrections.
- Updates `generated` flags after successful writes.

### Tester (`agents/tester.py`)

- No longer contains any Todo-specific logic. The old `_run_acceptance_test` has been removed.
- New method `_run_generic_acceptance_tests(acceptance_tests, output_dir)`:
  - Creates **one shared temporary directory** for the entire batch.
  - For each test, executes `entrypoint` with `args` and `working_directory=test_dir`.
  - Compares `return_code` and checks `expected_stdout_contains`.
  - Returns structured results including `passed`, `status`, `actual_stdout`, `stderr`, `return_code`, `error_reason`.
- `process_command` checks for `acceptance_tests` payload first; if present, runs the generic engine and bypasses legacy CLI detection.
- Per-module testing still works for library modules using the legacy path (which remains for now).

### Debugger (`agents/debugger.py`)

- Unchanged from previous versions.

### Contract Generator (`project_design/contract_generator.py`)

- Now reads the `type` field from each module in the project structure and stores it in `contracts.json`.
- All other contract fields (`exports`, `dependencies`, `required_imports`) are preserved.

### API Inspector (`agents/api_inspector.py`)

- Unchanged from v3.2.
- Still performs structural/API-level validation:
  - Parses the Python file with `ast`.
  - Collects top-level functions/classes.
  - Checks that exports exist with correct kinds.
  - Checks no unexpected public symbols.
- In v3.3, Supervisor does not invoke it for modules where `contract["type"] == "entrypoint"`.

### Semantic Analyzer (`agents/semantic_analyzer.py`)

- Unchanged from v3.2.
- Performs cross-module semantic validation using dependency contracts.
- Runs after API Inspector (if applicable) and before Tester, only when the module has dependencies.

---

## Self-Repair Loop (v3.3)

There are now two distinct repair loops:

1. **Module-level repair** – triggered by API Inspector, Semantic Analyzer, or per-module Tester failures. Similar to v3.2.
2. **Acceptance-level repair** – triggered when final acceptance tests fail.

### Module-level repair

```text
Coder
  ↓
API Inspector (if library) / Semantic Analyzer
  ↓
Tester (per module)
  ↓
Failure
  ↓
Debugger / diagnostic analysis
  ↓
Engineer (single or multi-module prompt)
  ↓
Coder (repair)
  ↓
Validation again
```

### Acceptance-level repair

```text
All modules pass
  ↓
Final Acceptance Tests
  ↓
Failure
  ↓
Supervisor sets acceptance_repair_pending
  ↓
Engineer repair prompt (project-level)
  ↓
Coder repair
  ↓
Same acceptance_tests re-sent to Tester
  ↓
If still failing, repeat until max attempts
```

- On acceptance failure, `fix_attempts["__acceptance__"]` is incremented.
- Placeholder module for repair is chosen from the entrypoint of the first acceptance test.
- The same `self.acceptance_tests` are reused after repair; no new tests are generated.
- If Coder returns error during acceptance repair, Supervisor retries; after 3 failed attempts, status becomes `error`.

---

## Repair Context (v3.3)

The `RepairContext` class remains the central data container for repair information.

### v3.3 additions

- `failure_type` – set to `"final_acceptance"` for acceptance-level failures.
- `acceptance_tests` – the full list of acceptance tests.
- `acceptance_failure_details` – structured results of failed acceptance tests (description, args, expected, actual, stderr, return code).

### Existing fields

- `module_name`
- `filepath`
- `current_code`
- `contract`
- `api_errors`
- `semantic_errors`
- `runtime_error`
- `debugger_analysis`
- `previous_attempts`
- `all_modules` (when multi-module repair is needed)

---

## Acceptance Test Generation

`StructureDesignerLLM` now produces `acceptance_tests` at the root level of the project structure.

### Prompt rules for acceptance tests

1. Always include a help test:

   ```json
   {
     "args": ["--help"],
     "expected_stdout_contains": ["usage"],
     "expected_return_code": 0
   }
   ```

2. For successful deterministic commands, use actual input data in `expected_stdout_contains`.
3. For random/unpredictable output, set `expected_stdout_contains` to `[]` and rely on `expected_return_code`.
4. Only generate a no-arguments error test if the CLI has required arguments:

   ```json
   {
     "args": [],
     "expected_stdout_contains": [],
     "expected_return_code": 2
   }
   ```

   Do not generate this test if all arguments have defaults.
5. Do not generate tests for optional flags (e.g., `--dry-run`) unless explicitly requested.
6. Do not generate tests for runtime errors (e.g., invalid directory) unless explicitly requested.
7. Avoid positional arguments unless the contract explicitly defines them.
8. Keep total tests between 2 and 4.

### Validation in code

- `acceptance_tests` must be a list of valid dicts.
- Invalid tests (missing entrypoint, invalid args, invalid timeout, etc.) are discarded.
- If no valid tests remain, `acceptance_tests` becomes an empty list, and later Supervisor will fail with `"No acceptance tests available"`.

---

## Tester Acceptance-Test Isolation

In v3.3, the generic acceptance executor uses one shared temporary directory for the entire test batch.

```python
with tempfile.TemporaryDirectory() as test_dir:
    for test in acceptance_tests:
        result = self.executor.execute(
            filepath,
            working_directory=test_dir,
            timeout_seconds=timeout_seconds,
            args=args,
        )
```

- All runtime-relative files (e.g., `todos.json`) are created inside `test_dir`.
- Source files remain in `OUTPUT_DIR`.
- The shared directory allows stateful tests (e.g., add followed by list) to work.
- The directory is automatically cleaned after the batch.

### CodeExecutor

`CodeExecutor` was not modified for this change.  
It already supported a `working_directory` parameter.

**Responsibility split:**

- **CodeExecutor** – executes a file with the supplied working directory.
- **Tester** – defines the isolated runtime environment for acceptance testing.

---

## Contract Lifecycle (v3.3)

1. Engineer/StructureDesigner designs structure with explicit exports, `type`, and `required_imports`.
2. StructureDesigner also produces `acceptance_tests` at the root level.
3. ContractGenerator creates `contracts.json` and now includes the `type` field.
4. Coder loads contract, implements it, sets `generated: true`.
5. API Inspector verifies structural compliance (skipped for entrypoint).
6. Semantic Analyzer verifies cross-module usage.
7. Tester runs the module.
8. Supervisor sets `validated: true` on success.
9. After all modules pass, final acceptance tests are executed; only if they pass is the project marked completed.

> **Note:** Signature-level enforcement (parameter types, return values) is **NOT** implemented in v3.3. It remains a limitation.

---

## End-to-End Validation

MetaForge v3.3 has been validated with multiple real CLI projects using the real LLM-powered pipeline.

**Validated projects:**

- **Todo App** — `storage.py`, `todo_manager.py`, `cli.py`
- **Temperature Converter** — `converter.py`, `cli.py`
- **Password Generator** — `generator.py`, `cli.py`
- **Calculator** — `calculator.py`, `cli.py`

Each project was generated, analyzed, repaired when necessary, and passed final acceptance tests.

**Final result for all validated projects:**

```text
status=completed
ACCEPTANCE TEST PASSED
```

File Organizer was also partially validated: generic CLI help and required-argument tests pass, but file-rename-specific acceptance tests are deferred because they require fixture/state setup not yet supported by the generic test engine.

---

## Known Technical Limitations (v3.3)

- Non-CLI projects (GUI, interactive, web) are not yet fully supported by the generic acceptance engine.
- File-system/stateful operations that require pre-existing fixtures are only partially covered. File Organizer currently validates CLI help and required-argument handling, but file-rename-specific tests are deferred.
- Acceptance tests are generic but not exhaustive; they focus on main success paths, help, and required-argument errors.
- The underlying LLM may occasionally ignore strict generation constraints.
- Semantic analysis depends on the quality and completeness of the generated project context.
- Contract and API validation cannot replace behavioural testing.
- The repair process is bounded by configured repair limits.
- Generated architecture and code quality still depend partly on the selected LLM.
- Runtime isolation currently applies only to the acceptance-test environment. Other execution paths may still share state if they do not use a temporary working directory.

---

## Future Roadmap

- ✅ **v1.0** – Simulated agents with mock responses
- ✅ **v2.0** – Full LLM-powered agents + Fallback + Diagnostics
- ✅ **v3.0-beta** – Context Manager, Debugger, Knowledge Base, Self-Repair Loop
- ✅ **v3.1** – Contract Generator, contract-aware Coder, API Inspector, Supervisor quality gate
- ✅ **v3.2** – Semantic Analysis, improved multi-module repair, diagnostic repair-loop investigation, isolated acceptance testing, real Todo end-to-end validation
- ✅ **v3.3** – Generic acceptance testing, entrypoint-aware validation, shared runtime isolation, acceptance criteria injection
- ⬜ **v4.0** – Web UI
- ⬜ **Future** – Signature-level contract enforcement (parameter & return type validation), fixture/setup support for acceptance tests, broader non-CLI project support, file-system test isolation improvements

