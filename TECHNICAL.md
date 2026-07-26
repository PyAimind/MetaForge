# MetaForge v3.0 – Technical Architecture

## Architecture Overview

MetaForge v3.0 is a multi-agent pipeline that transforms a natural language project idea into a tested, runnable multi-module Python codebase. The system is built around specialised agents that communicate asynchronously via a central message bus, with a shared workspace for state and logging. An LLM provider integration enables intelligent design and code generation.

Core components:

- **Supervisor** – orchestrates the entire workflow, manages state transitions, and handles error recovery through a structured self-repair loop.
- **Engineer** – designs the project structure and generates coding prompts for each module.
- **Coder** – writes the actual Python code using an LLM-powered generator, now context-aware.
- **Tester** – executes the generated code safely and returns structured test results.
- **Debugger** – analyses test failures and produces structured diagnoses (new in v3.0).
- **MessageChannel** – thread-safe queue-based message bus connecting all agents.
- **WorkspaceManager** – persistent short-term memory backed by JSON files (phase, logs, structure, test results).
- **ContextManager** – collects structural information about generated modules and provides it to the Coder (new in v3.0).
- **KnowledgeBase** – stores lessons, successful patterns, and failures across runs (new in v3.0).
- **LLMProvider** – HTTP client for the DeepSeek API (or compatible OpenAI-compatible endpoint).

The system follows the **Supervisor-Worker** pattern: the Supervisor issues sequential commands, each agent processes them and responds asynchronously. All critical state is managed in-memory by the Supervisor and persisted to the workspace for diagnostics and recovery.

## Agent Roles

### Supervisor (`agents/supervisor.py`)
- Owns the project idea, overall status (`idle`, `designing`, `waiting_for_*`, `completed`, `error`), module list, current module index, prompt cache, and per-module fix counters.
- Drives the state machine:
  1. **designing** → sends `design_structure` to Engineer.
  2. **waiting_for_engineer** → receives structure, stores it, requests prompts.
  3. Receives prompts, sends `code` command to Coder for the current module.
  4. **waiting_for_coder** → receives filepath, sends `test` command to Tester.
  5. **waiting_for_tester** → processes test results.
- On test failure or timeout:
  - Invokes the Debugger to obtain a structured diagnosis.
  - Attaches the diagnosis to the fix request sent to the Engineer.
  - Enforces a maximum of 3 fix attempts per module before stopping the project.
- On Coder fallback status: immediately transitions to `error` and stops the pipeline.

### Engineer (`agents/engineer.py`)
- Accepts three actions: `design_structure`, `generate_prompts`, `generate_single_prompt`.
- **Design Structure**: delegates to a `StructureDesignerLLM` (or deterministic fallback). Returns a JSON structure with phases and modules.
- **Generate Prompts / Generate Single Prompt**: produces detailed coding prompts. When a Debugger diagnosis is present, the prompt is enriched with the diagnosis, root cause, and suggested fix.
- Follows Dependency Inversion: the designer dependency is injected and validated via duck typing.

### Coder (`agents/coder.py`)
- Receives `code` commands containing a module specification.
- Before generation, queries the ContextManager for information about already-generated modules and injects that context into the generation prompt.
- Uses a `CodeGeneratorLLM` (or falls back to a safe placeholder).
- After successful generation, registers the new module with the ContextManager so subsequent modules can see it.
- Returns `fallback` status when the generated code matches the placeholder constant, allowing the Supervisor to stop cleanly.

### Tester (`agents/tester.py`)
- Receives `test` commands with a filepath.
- Performs safety checks (path inside OUTPUT_DIR, file existence).
- **CLI detection**: if the file is a recognised entry point (`main.py`, `cli.py`, `app.py`) and contains interactive keywords (`input(`, `argparse`, `sys.argv`), it is marked as passed without execution to avoid hangs.
- Otherwise delegates to `CodeExecutor` for safe subprocess execution with timeout.
- Returns structured results (`status`, `return_code`, `stdout`, `stderr`, `execution_time`).

### Debugger (`agents/debugger.py`) — New in v3.0
- Receives error information (`filepath`, `stderr`, `stdout`, `return_code`).
- Classifies common error types using regex patterns (SyntaxError, ImportError / ModuleNotFoundError, NameError, Timeout, RuntimeError, Unknown).
- Produces a structured diagnosis dictionary containing:
  - `diagnosis` – short error type label
  - `root_cause` – detailed explanation
  - `suggested_fix` – actionable recommendation for the Engineer
  - `confidence` – float between 0.0 and 1.0
- Optionally consults the KnowledgeBase (failures layer first) to enrich the suggested fix with historical lessons.
- Returns an empty dict on failure so the Supervisor can still continue with a generic fix request.

## New in v3.0 – Context Manager

**Location:** `project_design/context_manager.py`

The Context Manager solves a major limitation of earlier versions: the Coder generated each module in isolation and therefore frequently produced duplicated logic or incorrect imports.

### Responsibilities
- Parses generated Python files using the `ast` module (top-level only).
- Extracts classes, functions, imports, and exports for every module.
- Maintains an in-memory registry of all modules generated so far.
- Provides a context summary (via `get_context_for_module`) that is injected into the Coder’s generation prompt.
- Ensures that when the Coder writes `main.py`, it already knows the public API of previously generated modules such as `utils.py` or `calculator.py`.

### Integration
- The Coder receives a ContextManager instance through dependency injection.
- After writing a file, the Coder calls `add_module(filename, code)` so the registry stays up to date.
- The context is also available to the Engineer when generating fix prompts.

## New in v3.0 – Knowledge Base

**Location:** `memory/knowledge_base.py`

The Knowledge Base turns MetaForge from a stateless generator into a system that can learn across runs.

### Three-layer structure
1. **Lessons** – general advice extracted from successful or failed runs (e.g. “avoid global variables in library modules”).
2. **Successful Patterns** – patterns that produced clean, working code.
3. **Failures** – recorded failure diagnoses together with the fix that eventually worked (or the reason the project stopped).

### Usage
- The Engineer and Coder can query the Knowledge Base before generating prompts or code.
- The Debugger searches the failures layer first when analysing a new error; if a similar past failure exists, it can raise confidence and suggest a historically successful fix.
- Lessons are stored after each project run (successful or failed) so that later projects benefit from earlier experience.

## New in v3.0 – Debugger Agent

**Location:** `agents/debugger.py`

In v2.0 the Supervisor reacted to test failures by simply asking the Engineer for a new prompt. In v3.0 the Debugger inserts a structured analysis step between the failure and the fix request.

### Analysis pipeline
1. Receive `filepath`, `stderr`, `stdout`, `return_code` from the Supervisor.
2. Classify the error with explicit regular expressions.
3. Build a diagnosis dictionary with confidence score.
4. Optionally enrich the diagnosis from the Knowledge Base.
5. Return the dictionary to the Supervisor.

### Integration with Supervisor
When `_handle_waiting_for_tester` receives a `failed` or `timeout` status:
- The Supervisor calls `_analyze_failure(...)`.
- If a non-empty diagnosis is returned, it is attached to the payload as `debugger_diagnosis`.
- The Engineer receives the diagnosis and incorporates it into the regenerated prompt.
- The fix-attempt counter for that module is incremented; after three failures the project is stopped.

## Self-Repair Loop

Complete flow for a failing module:

```
Tester reports failure / timeout
        ↓
Supervisor calls Debugger.analyze_error(...)
        ↓
Debugger returns structured diagnosis
        ↓
Supervisor attaches diagnosis to fix request
        ↓
Engineer generates an enriched prompt
        ↓
Coder regenerates the module (with Context Manager awareness)
        ↓
Tester re-executes the module
        ↓
(repeat up to 3 times per module, then stop)
```

This loop replaces the previous “blind regenerate” behaviour with targeted, diagnosis-driven fixes.

## Communication Protocol

All inter-agent communication uses immutable `Message` dataclasses and a `MessageChannel` that acts as a thread-safe message bus.

### Message (`communication/message.py`)
- Frozen dataclass: `sender`, `receiver`, `msg_type`, `phase`, `payload`.
- Two types: `CommandMsg` and `ResultMsg`.
- Serialisation helpers: `to_dict()` / `from_dict()`.

### MessageChannel (`communication/message_channel.py`)
- One `queue.Queue` per agent name.
- `send(message)` places the message into the receiver’s queue.
- `receive(agent_name, timeout)` blocks until a message arrives or times out.
- Agents never share queues directly; they only know the channel and their own name.

## Dependency Injection

`main.py` is the Composition Root. All concrete dependencies are constructed there and injected into the agents:

- `LLMProvider` (reads API key from environment)
- `StructureDesignerLLM` and `CodeGeneratorLLM` (receive the provider)
- `CodeExecutor`
- `ContextManager`
- `KnowledgeBase`
- `Debugger` (optionally receives the KnowledgeBase)
- `WorkspaceManager` and `MessageChannel`

Agents receive only the interfaces they need. This keeps the system testable and allows mock substitution in unit tests.

## Known Technical Limitations

- **CLI testing**: The Tester still cannot fully execute programs that require command-line arguments (`sys.argv` / `argparse`). Interactive entry points are currently auto-passed after syntax checking. Improvement planned for v3.1.
- **LLM prompt adherence**: The underlying LLM sometimes ignores specific instructions (e.g. exact import names), producing subtle errors that the Debugger can detect but not always fully repair.
- **Knowledge Base utilisation**: The Debugger can read from the Knowledge Base, but the feedback loop that automatically writes high-quality lessons back is still limited. Deeper integration is planned for v3.1.
- **Single-threaded execution**: Agents run cooperatively in one process; true parallelism is not yet supported.
- **File I/O**: Workspace JSON files are written without locking; concurrent external access could corrupt state.
- **Timeout**: Subprocess timeout is fixed (currently 10 s). Long-running legitimate modules will be marked as failed.

## Future Roadmap

- ✅ **v1.0** — Simulated agents with mock responses
- ✅ **v2.0** — Full LLM-powered agents + Fallback + Diagnostics
- ✅ **v3.0-beta** — Context Manager, Debugger, Knowledge Base, Self-Repair Loop
- ⬜ **v3.1** — Better CLI testing, deeper Debugger–Knowledge Base integration
- ⬜ **v4.0** — Web UI