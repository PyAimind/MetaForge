# MetaForge v3.2 – Technical Architecture

## Architecture Overview

MetaForge v3.2 is a multi-agent pipeline that transforms a natural language project idea into a tested, runnable multi-module Python codebase. The system is built around specialised agents that communicate through a central message bus using per-agent message queues, with a shared workspace for state and logging. An LLM provider integration enables intelligent design and code generation.

### New in v3.2

- **Semantic Analyzer** – a cross-module compatibility layer that inspects Python files against dependency contracts to detect misuse of external APIs, wrong argument counts, and missing methods. It is injected into the Supervisor and runs after the API Inspector.
- **Multi-Module Runtime Repair** – when a runtime acceptance failure is detected, the repair context now includes all generated modules, enabling the Engineer to produce a repair prompt that spans multiple files. The Coder can process a JSON response containing corrections for several modules in one repair cycle.
- **Isolated Acceptance-Test Environment** – the Tester executes acceptance commands inside a fresh `TemporaryDirectory`, preventing stale runtime state (e.g., `todos.json`) from contaminating later test runs.
- **Diagnostic Repair-Loop Investigation** – focused diagnostic tests track file hashes, modification times, and content transitions across repair cycles to distinguish source rollback from runtime state leakage.

### Core Components

- **Supervisor** – orchestrates the entire workflow, manages state transitions, and handles error recovery. It now optionally integrates an API Inspector and a Semantic Analyzer, and supports multi-module repair.
- **Engineer** – designs the project structure and generates contract-aware coding prompts. During repair, it can generate a multi-module repair prompt containing all relevant module sources and contracts.
- **Coder** – writes Python code using an LLM-powered generator. It reads `contracts.json`, injects contracts into prompts, and updates `generated` flags. In repair mode, it can parse a multi-module JSON response and write multiple corrected files.
- **Tester** – executes generated code safely and returns structured results. Its acceptance test now runs in an isolated temporary directory to avoid cross-run state contamination.
- **Debugger** – analyses test failures and produces structured diagnoses.
- **Contract Generator** – extracts public API contracts from the project structure and persists them as `contracts.json`.
- **API Inspector** – validates a generated Python file against its declared contract using AST analysis. (Unchanged in v3.2, but now complemented by the Semantic Analyzer.)
- **Semantic Analyzer** – new in v3.2, performs cross-module semantic checks using the actual dependency contracts.
- **MessageChannel** – thread-safe queue-based message bus.
- **WorkspaceManager** – persistent short-term memory backed by JSON files.
- **ContextManager** – collects structural information about generated modules.
- **KnowledgeBase** – stores lessons, successful patterns, and failures.
- **LLMProvider** – HTTP client for the DeepSeek API or compatible endpoint.

The system follows the **Supervisor-Worker** pattern: the Supervisor issues sequential commands, each agent processes them and responds through the message bus. Critical state is managed in-memory by the Supervisor and persisted to the workspace.

---

## Agent Roles (v3.2 updates)

### Supervisor (`agents/supervisor.py`)

- Owns the project idea, overall status, module list, current module index, prompt cache, and per-module fix counters.
- State machine:
  1. **designing** → sends `design_structure` to Engineer.
  2. **waiting_for_engineer** → receives structure, stores it, invokes ContractGenerator, requests prompts.
  3. Receives prompts, dispatches the first ready module to Coder.
  4. **waiting_for_coder** → receives filepath. Validation order is fixed:
     - **API Inspector** first (structural contract validation against the module’s own exports).
     - **Semantic Analyzer** second (cross-module semantic validation if dependencies exist).
     - On failure, blocks Tester, increments fix counter, triggers repair.
  5. **waiting_for_tester** → processes test results: on success, sets `validated` and advances; on failure/timeout, invokes Debugger and retries.
- When a runtime failure is reported, `_build_repair_context` now accepts `include_all_modules=True` and collects source/contract information for all generated modules into `ctx.all_modules`.

### Engineer (`agents/engineer.py`)

- Accepts `design_structure`, `generate_prompts`, `generate_single_prompt`.
- During repair, if the repair context contains `all_modules`, the Engineer builds a **multi-module repair prompt** that includes every module’s source code and contract, and instructs the LLM to return a JSON object mapping module filenames to corrected code.
- For single-module repairs, the previous behaviour remains unchanged.

### Coder (`agents/coder.py`)

- Before generation, loads the module’s contract from `contracts.json` and injects it into the generation prompt.
- In repair mode:
  - Uses the Engineer-provided prompt when available.
  - If `all_modules` is present, parses the LLM response as a JSON object, validates each returned module against the expected module set, and writes all valid corrections before handling the entry module.
- Updates `generated` flags after successful writes.

### Tester (`agents/tester.py`)

- Performs safety checks, CLI detection, and safe subprocess execution.
- `_run_acceptance_test` now executes the CLI acceptance sequence inside a `tempfile.TemporaryDirectory()` to isolate runtime state.
- Each `executor.execute()` call inside `_run_acceptance_test` receives `working_directory=test_dir`.
- Generated source files remain in `OUTPUT_DIR`; only runtime-relative data files are created inside the temporary test directory.

### Debugger (`agents/debugger.py`)

- Unchanged from v3.1.

### Contract Generator (`project_design/contract_generator.py`)

- Unchanged from v3.1.

### API Inspector (`agents/api_inspector.py`)

- Unchanged in v3.2. It still performs structural/API-level validation:
  - Parses the Python file with `ast`.
  - Collects top-level functions/classes.
  - Checks that exports exist with correct kinds.
  - Checks no unexpected public symbols.
- Runs before Tester and before the Semantic Analyzer.

### Semantic Analyzer (`agents/semantic_analyzer.py`) — New in v3.2

- Lives in `agents/`.
- Responsible for **cross-module semantic validation**:
  - Uses `agents/semantic_visitor.py` to collect imports, assignments, and function/method calls.
  - Uses `agents/semantic_validator.py` to validate each call against dependency contracts.
- Detects issues such as:
  - Missing functions/classes/methods.
  - Wrong number of positional arguments.
  - Unexpected keyword arguments.
- Called by the Supervisor after API Inspector and before Tester, only when the module has dependencies.
- Its result (`valid` bool + list of errors) is used by the Supervisor to block a module from testing and trigger repair.

**Difference from API Inspector:**

| Component          | Responsibility                                      |
|--------------------|-----------------------------------------------------|
| API Inspector      | Structural validation of a module’s own exports     |
| Semantic Analyzer  | Cross-module compatibility analysis against declared contracts of dependencies |

---

## Self-Repair Loop (v3.2 update)

The repair loop now includes additional validation layers and supports multi-module repair. The validation order is:

```text
Coder
  ↓
API Inspector (structural)
  ↓
Semantic Analyzer (cross-module, if dependencies exist)
  ↓
Tester (runtime)
  ↓
Runtime failure
  ↓
Debugger / diagnostic analysis
  ↓
Multi-module repair context (if runtime_failure)
  ↓
Engineer (multi-module prompt)
  ↓
Coder (JSON response parsing, multiple file writes)
  ↓
Validation again (API Inspector → Semantic Analyzer → Tester)
  ↓
Acceptance test runs in isolated runtime environment
```

- **API Inspector** runs before **Semantic Analyzer**; both run before Tester. Failures from either enter the same repair path as Tester failures.
- For `runtime_failure`, the Supervisor includes `all_modules` in the repair context, enabling the Engineer to instruct the LLM to fix multiple modules simultaneously.
- After successful repair and Tester pass, the Supervisor resets `fix_attempts` to `0` for that module.

---

## Repair Context (v3.2)

The `RepairContext` class (`project_design/repair_context.py`) remains the central data container for repair information.

**Key v3.2 addition:**

- `all_modules` – list of dicts, each containing `module_name`, `source_code`, and `contract` for every generated module. This is populated by the Supervisor only for `runtime_failure` when `include_all_modules=True`.

**Other fields:**

- `module_name`, `filepath`, `current_code`, `contract`, `api_errors`, `semantic_errors`, `runtime_error`, `debugger_analysis`, `previous_attempts`.

During repair, the Engineer uses `all_modules` to build a multi-module prompt, while the Coder uses it to validate which modules are allowed in the LLM’s JSON response.

---

## Multi-Module Runtime Repair

In v3.1, repair focused only on the module that reported the failure. This was insufficient for cross-module bugs where, for example, `cli.py` fails because `todo_manager.py` returns incompatible data.

In v3.2:

1. A runtime failure triggers `include_all_modules=True` in `_build_repair_context`.
2. The Supervisor collects source and contract for every generated module.
3. The Engineer builds a prompt that includes all module sources and contracts, instructing the LLM to return a JSON object with corrected files.
4. The Coder validates the JSON response, ensuring returned module names match the expected set, and writes all corrections.
5. The post-repair Tester executes the repaired code in a clean runtime environment.

This allows a single repair cycle to correct multiple files, addressing cross-module interface mismatches.

---

## Diagnostic Repair-Loop Investigation

During v3.2 testing, a post-repair failure appeared to suggest that the Coder had not persisted its repair. A dedicated diagnostic test was created to track file state across the repair loop.

**Methodology** (implemented in `tests/diagnostic_repair_loop_state_investigation.py`):

- Capture file existence, SHA-256 hash, size, modification time, and first lines at three checkpoints:
  - **Point A** – before repair.
  - **Point B** – immediately after Coder write.
  - **Point C** – immediately before post-repair Tester.
- Classify each file as OLD (buggy) or NEW (corrected) using known patterns.
- Compare hashes and patterns to determine if files were written and persisted.

**Key finding:**

- Point A → Point B: files transitioned from OLD to NEW.
- Point B → Point C: files remained NEW.
- Therefore, source-code rollback was **not** the root cause.

This diagnostic is a test-only investigation mechanism, not a production runtime feature.

---

## State Leakage / Runtime State Contamination

The confirmed root cause of the post-repair failure was **stale runtime state**, not source-code regression.

**Initial acceptance run:**

- The old buggy `todo_manager.py` stored plain strings.
- `cli.py` executed and created `todos.json` containing the old-format data (`["Test todo"]`).

**After Coder repair:**

- `todo_manager.py` and `cli.py` were corrected.
- But `todos.json` still contained the old data.

**Post-repair Tester:**

- Executed the corrected code.
- The corrected code loaded the stale `todos.json`.
- Because the data was incompatible with the new dict-based structure, the acceptance test failed again.

Thus, the failure was caused by **runtime state contamination**, not by Coder or repair pipeline defects.

---

## Tester Acceptance-Test Isolation

The final production fix addressed the stale-state issue by isolating the acceptance-test runtime environment.

In `agents/tester.py`, `_run_acceptance_test` now uses:

```python
with tempfile.TemporaryDirectory() as test_dir:
    ...
    self.executor.execute(cli_file, args=["--help"], timeout_seconds=10, working_directory=test_dir)
    self.executor.execute(cli_file, args=["add", "Test todo"], timeout_seconds=10, working_directory=test_dir)
    self.executor.execute(cli_file, args=["list"], timeout_seconds=10, working_directory=test_dir)
    # ...
```

**Acceptance sequence:**

1. `--help`
2. `add "Test todo"`
3. `list`
4. extract `todo_id`
5. `remove <todo_id>`
6. `list` again

All commands now run with `working_directory=test_dir`, so any runtime-relative files (e.g., `todos.json`) are created inside the temporary directory, not in `OUTPUT_DIR`.

- Generated source files remain in `OUTPUT_DIR`.
- Runtime state from the acceptance test is discarded after each run because `TemporaryDirectory` cleans up automatically.
- The source code itself is not copied into the temporary directory; only the working directory changes.

### CodeExecutor

`CodeExecutor` was not modified for this fix.  
It already supported a `working_directory` parameter in `execute()`.

**Responsibility split:**

- **CodeExecutor** – executes a file with the supplied working directory.
- **Tester** – defines the isolated runtime environment for acceptance testing.

### process_command

`Tester.process_command()` was intentionally not changed for the state-leakage fix.

There is still an earlier CLI `--help` execution in `process_command` that does not use the temporary directory. This is fine because it only checks syntax/help, not runtime data state.

The mandatory isolation was implemented inside `_run_acceptance_test` because that is where the actual acceptance commands run and where runtime state is created.

---

## Contract Lifecycle

The v3.1 contract lifecycle remains unchanged:

1. Engineer designs structure with explicit exports and `required_imports`.
2. ContractGenerator creates `contracts.json`.
3. Coder loads contract, implements it, sets `generated: true`.
4. API Inspector verifies structural compliance.
5. Semantic Analyzer verifies cross-module usage.
6. Tester runs the module.
7. Supervisor sets `validated: true` on success.

> **Note:** Signature-level enforcement (parameter types, return values) is **NOT** implemented in v3.2. It remains a limitation.

---

## End-to-End Validation

The v3.2 changes were validated with a real Todo project using the real pipeline and real LLM-powered generation.

**Generated modules:**

- `storage.py`
- `todo_manager.py`
- `cli.py`

Diagnostic output showed real multi-module repair prompts:

```text
MULTI-MODULE RUNTIME FAILURE REPAIR
```

and per-module repair targets:

```text
REPAIR TARGET: storage.py (attempt 2)
REPAIR TARGET: todo_manager.py (attempt 2)
```

**Final run:**

```text
status=completed
fix_attempts={'storage.py': 0, 'todo_manager.py': 0, 'cli.py': 0}
ACCEPTANCE TEST PASSED
```

This validates:

- LLM-based generation
- contract/API validation
- semantic analysis
- runtime execution
- multi-module repair
- isolated post-repair acceptance testing
- Supervisor completion

It does **not** prove correctness for arbitrary projects; it is a targeted validation of a known cross-module bug scenario.

---

## Known Technical Limitations (v3.2)

- Semantic analysis is not full behavioral verification. It checks call compatibility but does not trace data flow or runtime behavior.
- Signature/type/return-value contract enforcement is still absent. API Inspector validates structure, not exact parameter types or return values.
- Acceptance testing remains project/CLI dependent. The automated acceptance scenario works for simple CLI apps but may not cover all project types.
- Interactive programs that require `input()` are still difficult to test; they may be auto-passed or skipped.
- LLM prompt adherence is not guaranteed. The LLM may still ignore strict contract instructions, though the repair loop and validation layers catch many violations.
- Repair attempts are bounded. After a fixed number of failures per module, the Supervisor stops and marks the project as error.
- Generated architecture depends on LLM quality. The Engineer’s structure and API design are only as good as the LLM’s output.
- Runtime isolation currently applies only to the acceptance-test environment. Other execution paths may still share state if they do not use a temporary working directory.

---

## Future Roadmap

- ✅ **v1.0** – Simulated agents with mock responses
- ✅ **v2.0** – Full LLM-powered agents + Fallback + Diagnostics
- ✅ **v3.0-beta** – Context Manager, Debugger, Knowledge Base, Self-Repair Loop
- ✅ **v3.1** – Contract Generator, contract-aware Coder, API Inspector, Supervisor quality gate
- ✅ **v3.2** – Semantic Analysis, improved multi-module repair, diagnostic repair-loop investigation, isolated acceptance testing, real Todo end-to-end validation
- ⬜ **v4.0** – Web UI
- ⬜ **Future** – Signature-level contract enforcement (parameter & return type validation), broader behavioral testing, parallel agent execution
```
