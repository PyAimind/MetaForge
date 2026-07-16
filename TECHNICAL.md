# MetaForge v2.0 – Technical Architecture

## Architecture Overview

MetaForge v2.0 is a multi-agent pipeline that transforms a natural language project idea into a tested, runnable codebase. The system is built around four specialised agents communicating asynchronously via a central message bus, with a shared workspace for state and logging. An LLM provider integration enables intelligent design and code generation.

Core components:

- **Supervisor** – orchestrates the entire workflow, manages state transitions, and handles error recovery.
- **Engineer** – designs the project structure and generates coding prompts for each module.
- **Coder** – writes the actual Python code (optionally using an LLM-powered generator).
- **Tester** – executes the generated code safely and returns structured test results.
- **MessageChannel** – thread-safe queue-based message bus connecting all agents.
- **WorkspaceManager** – persistent short-term memory backed by JSON files (phase, logs, structure, test results).
- **LLMProvider** – HTTP client for the DeepSeek API (or compatible OpenAI-compatible endpoint).

The system follows the **Supervisor-Worker** pattern: the Supervisor issues sequential commands, each agent processes them and responds asynchronously. All state is managed in-memory by the Supervisor and persisted to the workspace for diagnostics.

## Agent Roles

### Supervisor (`agents/supervisor.py`)
- Owns the project idea, overall status (`idle`, `designing`, `waiting_for_*`, `completed`, `error`), module list, current module index, and prompt cache.
- Drives the state machine:
  1. **designing** → sends `design_structure` to Engineer.
  2. **waiting_for_engineer** → receives structure, stores it in Workspace, requests prompts.
  3. Receives prompts, sends `code` command to Coder for current module.
  4. **waiting_for_coder** → receives filepath, sends `test` command to Tester.
  5. **waiting_for_tester** → processes test results; if passed, advances to next module; if failed, requests a fix from Engineer (with a per‑module retry limit).
- Handles fallback detection: if Coder reports `fallback` status, the Supervisor immediately sets `error` status and stops.

### Engineer (`agents/engineer.py`)
- Accepts three actions: `design_structure`, `generate_prompts`, `generate_single_prompt`.
- **Design Structure**: delegates to a `StructureDesignerLLM` (or a deterministic fallback template for known ideas). The result is a JSON structure with `project_name`, `description`, and `phases` containing modules with filenames, descriptions, dependencies, and purposes.
- **Generate Prompts**: iterates over all modules in the stored structure and calls `generate_prompt()` (from `project_design/prompt_generator.py`) to produce detailed coding prompts.
- **Generate Single Prompt**: used for fix requests; generates a fresh prompt for a specific module.
- Follows the Dependency Inversion Principle: the `designer` dependency is checked via duck typing (must have a callable `design` method).

### Coder (`agents/coder.py`)
- Receives `code` commands containing a module specification (filename, description, dependencies, purpose) and optionally a pre‑generated prompt string.
- Two code sources:
  - Direct `code` field provided in the payload (used for fixes or backward compatibility).
  - LLM‑generated code via a `CodeGeneratorLLM` (if no direct code or if direct code fails compilation).
- Applies a fallback detection: if the generated code matches exactly the `FALLBACK_CODE` placeholder, the Coder logs a warning and returns a `fallback` status instead of `success`.
- Writes the final code to `config.OUTPUT_DIR` and returns the filepath.

### Tester (`agents/tester.py`)
- Receives `test` commands with a `filepath`.
- Performs safety checks: path must be inside `OUTPUT_DIR`, file must exist.
- **CLI detection**: before execution, the file is compiled to catch syntax errors. If it is a recognised CLI entry point (`main.py`, `cli.py`, `app.py`) and contains interactive keywords (`input(`, `argparse`, `sys.argv`), it is automatically marked as `passed` (with a log entry) because runtime execution would time out.
- Otherwise, delegates to `CodeExecutor` to run the file in a subprocess with a timeout.
- Returns a structured result with `status`, `return_code`, `stdout`, `stderr`, `execution_time`.

## Communication Protocol

All inter‑agent communication uses immutable `Message` dataclasses and a `MessageChannel` that acts as a thread‑safe message bus.

### Message (`communication/message.py`)
- Frozen dataclass with fields: `sender`, `receiver`, `msg_type`, `phase`, `payload`.
- Two types: `CommandMsg` (instructions from Supervisor to workers) and `ResultMsg` (responses from workers to Supervisor).
- Serialisation: `to_dict()` and `from_dict()` for easy logging/persistence.

### MessageChannel (`communication/message_channel.py`)
- Manages per‑agent `queue.Queue` instances keyed by agent name (`config.AGENT_NAMES`).
- `send(message)` places the message into the receiver's queue.
- `receive(agent_name, timeout=None)` blocks until a message is available or a timeout occurs (raises `queue.Empty` for timeout, but the agents handle it gracefully).
- Supports `has_messages()` and `queue_size()` for diagnostics.

The Supervisor sends commands to itself (receiver="supervisor") to process the state machine; it also puts responses from workers back into the supervisor queue after inspection. Workers always send their results to "supervisor". This design decouples agents completely—they only know the channel and their own agent name.

## Dependency Injection

`main.py` acts as the **Composition Root** where all real dependencies are built and wired together.

- **LLMProvider**: reads API key from environment, wraps `requests.Session` with retry logic.
- **StructureDesignerLLM** and **CodeGeneratorLLM** receive the `LLMProvider` via constructor.
- **CodeExecutor**: a stateless executor for running generated Python files.
- **WorkspaceManager** and **MessageChannel** are plain Python objects with no external dependencies.
- Agents (`Supervisor`, `Engineer`, `Coder`, `Tester`) receive their required dependencies through their constructors (channel, workspace, and any specialised tooling like `designer`, `generator`, or `executor`). The Supervisor does not require an LLM dependency; it orchestrates only.

The `build_dependencies()` helper in `main.py` encapsulates the creation of `LLMProvider`, `StructureDesignerLLM`, `CodeGeneratorLLM`, and `CodeExecutor`. This makes the startup logic clean and testable.

## Fallback Mechanism

When the Coder cannot produce valid code (LLM returns empty, invalid, or placeholder code), it writes a minimal placeholder (`def placeholder(): pass`) and returns a `fallback` status instead of `success`.

### Flow:
1. **Coder** generates code. If the generated code is exactly the `FALLBACK_CODE` constant, it sets `final_status = "fallback"` and writes the placeholder file.
2. **Supervisor** in `_handle_waiting_for_coder` checks for `fallback` status. If detected, it logs an error and immediately transitions to `error` state, terminating the project.
3. **Per‑module fix attempt limit**: When the Tester reports a failure, the Supervisor increments a fix counter for that module. If the module fails more than 3 times, the Supervisor gives up and sets the project to `error`. On a successful test, the counter is reset.

This prevents infinite loops when the LLM repeatedly generates broken code and ensures that a truly failed module stops the pipeline quickly.

## CLI Detection

The Tester cannot execute interactive CLI programs because they block on `input()` or require command‑line arguments. To handle this, the Tester employs a two‑step validation:

1. **Syntax validation**: The file content is compiled with `compile()`. Any syntax or indentation error immediately returns a failed result.
2. **CLI detection** (only if syntax passes):
   - The filename must be one of `main.py`, `cli.py`, or `app.py`.
   - The file content must contain at least one of `input(`, `argparse`, or `sys.argv`.
   - If both conditions are met, the file is marked as `passed` with an appropriate log event. No subprocess execution occurs.
3. For all other files (library modules), normal execution via `CodeExecutor` happens.

This design ensures that entry points are never executed (avoiding hangs) while still verifying they are syntactically correct, and that library modules are fully tested at runtime.

## Diagnostic System

MetaForge includes a self‑diagnostic subsystem for deep pipeline inspection when tests fail.

### Components:
- **`DiagnosticReport`** (`diagnostics/diagnose.py`): a data class that collects check results, a final diagnosis, root cause analysis, and suggested fix. It can render a formatted text report.
- **Step Checkers** (`diagnostics/checks/step2.py` to `step6.py`): each implements a `check()` function that receives the live system objects (channel, workspace, supervisor, agents) and returns a populated `DiagnosticReport`. They inspect logs, workspace files, agent attributes, and output files without modifying state.
- **Dispatcher** (`run_diagnostics` in `diagnostics/diagnose.py`): lazy‑loads the appropriate step checker based on the step number and returns the report.

### How it is used:
The integration test (`tests/test_phase12_integration.py`) wraps every pipeline step check. On failure, it calls `run_diagnostics(step, ...)` to get a detailed report and prints it before exiting. This allows developers to quickly pinpoint the failing component.

## Known Technical Limitations

- **Single‑threaded execution**: All agents run in the same process with a cooperative step loop. True parallelism is not supported; the pipeline processes one message at a time per agent.
- **File I/O race conditions**: Workspace files are read and written by multiple components without file‑locking. Concurrent access (e.g., by external tools) could corrupt data.
- **LLM output dependency**: The quality of generated structures and code heavily depends on the LLM provider. Non‑deterministic responses may cause flaky builds.
- **Timeout handling**: The Tester's subprocess timeout is fixed at 10 seconds. Long‑running legitimate modules will fail.
- **No interactive debugging**: When a project fails, developers must rely on logs and the diagnostic system; there is no step‑by‑step debugger.
- **Limited error recovery**: The Supervisor can request code fixes up to 3 times per module, but it cannot repair structural design issues automatically.

## Future Roadmap

### v2.1
- **Streaming responses**: Use the LLM's streaming API for faster feedback on large code generation.
- **Parallel module processing**: Once a module is built and tested, the Supervisor could dispatch multiple independent modules to Coder/Tester concurrently.
- **Richer test assertions**: Allow the project structure to define expected test outputs (e.g., expected stdout) for Tester validation.
- **Improved diagnostics**: Add runtime performance metrics and memory‑usage checks.

### v3.0
- **Multi‑language support**: Generalise the Coder and Tester to support JavaScript, Rust, etc., via configurable executors.
- **Plugin architecture**: Allow third‑party agents (e.g., linter, security scanner) to be injected into the pipeline.
- **Web dashboard**: A real‑time UI showing pipeline status, live logs, and generated code diffs.
- **Self‑healing**: Use the LLM to automatically fix common errors (like missing imports) without full regeneration.