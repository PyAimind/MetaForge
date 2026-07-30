# MetaForge v3.1 – Technical Architecture

## Architecture Overview

MetaForge v3.1 is a multi-agent pipeline that transforms a natural language project idea into a tested, runnable multi-module Python codebase. The system is built around specialised agents that communicate asynchronously via a central message bus, with a shared workspace for state and logging. An LLM provider integration enables intelligent design and code generation.

**New in v3.1:** A Contract Layer enforces module API consistency. Before any code is written, the Engineer defines strict public contracts for every module. A Contract Generator persists them as `contracts.json`. The Coder is forced to read and implement exactly the declared API. An API Inspector validates the generated code against the contract before the module is tested, acting as a quality gate inside the Supervisor.

Core components:

- **Supervisor** – orchestrates the entire workflow, manages state transitions, and handles error recovery through a structured self-repair loop. Now includes an optional API Inspector quality gate that blocks invalid modules from testing.
- **Engineer** – designs the project structure and generates contract-aware coding prompts for each module. The structure now includes detailed export and import specifications.
- **Coder** – writes the actual Python code using an LLM-powered generator. It reads `contracts.json`, injects the contract into the generation prompt, and updates the `generated` flag after a successful write.
- **Tester** – executes the generated code safely and returns structured test results.
- **Debugger** – analyses test failures and produces structured diagnoses.
- **Contract Generator** – extracts public API contracts from the project structure and persists them as `contracts.json` with initial flags (`generated: false`, `validated: false`). (new in v3.1)
- **API Inspector** – validates a generated Python file against its declared contract using AST analysis. Checks that all exports exist, their kinds match (function/class), and no extra public symbols exist. Returns a pass/fail result with error details. (new in v3.1)
- **MessageChannel** – thread-safe queue-based message bus connecting all agents.
- **WorkspaceManager** – persistent short-term memory backed by JSON files (phase, logs, structure, test results).
- **ContextManager** – collects structural information about generated modules and provides it to the Coder.
- **KnowledgeBase** – stores lessons, successful patterns, and failures across runs.
- **LLMProvider** – HTTP client for the DeepSeek API (or compatible OpenAI-compatible endpoint).

The system follows the **Supervisor-Worker** pattern: the Supervisor issues sequential commands, each agent processes them and responds asynchronously. All critical state is managed in-memory by the Supervisor and persisted to the workspace for diagnostics and recovery.

## Agent Roles (v3.1 updates)

### Supervisor (`agents/supervisor.py`)
- Owns the project idea, overall status, module list, current module index, prompt cache, and per-module fix counters.
- Drives the state machine, now with an additional contract generation step:
  1. **designing** → sends `design_structure` to Engineer.
  2. **waiting_for_engineer** → receives structure, stores it, **invokes ContractGenerator** to produce `contracts.json`, then requests prompts.
  3. Receives prompts, dispatches the first ready module to Coder.
  4. **waiting_for_coder** → receives filepath. If an API Inspector is injected, it inspects the generated file against its contract. On failure, the module is blocked from testing and sent back through the repair loop (incrementing fix attempts). On success, or if no inspector is present, it sends the module to Tester.
  5. **waiting_for_tester** → processes test results: on success, sets `validated: true` in `contracts.json` and advances; on failure/timeout, invokes Debugger and retries.
- The `api_inspector` dependency is optional; if omitted, the Supervisor behaves exactly as in v3.0.

### Engineer (`agents/engineer.py`)
- Accepts `design_structure`, `generate_prompts`, `generate_single_prompt`.
- The LLM-powered structure designer now returns detailed `exports` and `required_imports` for every module. The Engineer validates these fields before storing the structure.
- When generating prompts, the contract for each module (from the structure) is injected into the prompt, forcing the Coder to implement the precise API.

### Coder (`agents/coder.py`)
- Before generation, loads the module’s contract from `contracts.json` and adds it to the generation prompt.
- After writing a file successfully, updates the `generated` flag for that module in `contracts.json` to `true`.
- Continues to use ContextManager, KnowledgeBase, and fallback logic as in v3.0.

### Tester (`agents/tester.py`)
- Unchanged from v3.0; still performs safety checks, CLI detection, and safe subprocess execution.

### Debugger (`agents/debugger.py`)
- Unchanged from v3.0.

### Contract Generator (`project_design/contract_generator.py`) — New in v3.1
- Reads the project structure from the workspace.
- For each module, extracts `filename`, `dependencies`, `exports`, and `required_imports`.
- Produces a `contracts.json` file with every module’s contract and initial flags:
  ```json
  {
    "greeter.py": {
      "module": "greeter.py",
      "dependencies": [],
      "exports": [{"name": "greet", "kind": "function", "parameters": [...], "returns": "str"}],
      "required_imports": [],
      "generated": false,
      "validated": false
    }
  }
  ```
- Called by the Supervisor immediately after receiving the structure and before any prompts are generated.

### API Inspector (`agents/api_inspector.py`) — New in v3.1
- Standalone class `APIInspector` with zero knowledge of MetaForge internals.
- Method `inspect(filepath: str, exports: list[dict]) -> dict`:
  - Parses the Python file with `ast`.
  - Collects all top-level `FunctionDef`, `AsyncFunctionDef`, and `ClassDef` whose names do not start with `_`.
  - Ignores imported names (from `ast.Import` / `ast.ImportFrom`).
  - Checks that every export exists with the correct kind (function/class).
  - Checks that no extra public symbols are present.
  - Returns `{"valid": bool, "errors": [str]}`.
- Injected into the Supervisor and called after Coder success to gate the module before testing.

## Self-Repair Loop (v3.1 update)

The self-repair loop now also handles API inspection failures:

```
Coder success
   ↓
(optional) API Inspector checks contract
   ↓
if invalid → block Tester, increment fix counter, re-prompt Engineer
   ↓
if valid → Tester executes
   ↓
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
Coder regenerates the module (contract still enforced)
   ↓
(repeat up to 3 times per module, then stop)
```

## Contract Lifecycle (v3.1)

1. Engineer designs structure with explicit `exports` and `required_imports`.
2. ContractGenerator creates `contracts.json` (`generated: false`, `validated: false`).
3. Coder loads the contract, implements it, and sets `generated: true` on success.
4. API Inspector (if active) verifies the generated file against the contract.
5. Tester runs the module.
6. Supervisor sets `validated: true` on successful test.

## Communication Protocol

Unchanged from v3.0. All inter-agent communication uses immutable `Message` dataclasses and a `MessageChannel` with per-agent queues.

## Dependency Injection

In `main.py`, the Composition Root now optionally creates an `APIInspector` and passes it to the Supervisor. All other injections remain as in v3.0.

## Known Technical Limitations (v3.1)

- **Cross-module semantic consistency**: The current contract validates that each module individually implements its declared exports (by name and kind). It does not yet enforce parameter lists, types, or return values. Two modules may each satisfy their own contract yet fail to interoperate due to signature mismatches. This was discovered during end-to-end testing with a multi-module Todo application and is the primary target for v3.2.
- **CLI testing**: The Tester still cannot fully execute programs that require interactive `input()` or complex `argparse` usage that causes timeouts. CLI entry points are still auto-passed after syntax checking in many cases.
- **LLM prompt adherence**: The underlying LLM may occasionally ignore strict prompt constraints, potentially adding forbidden imports or altering declared exports. The API Inspector catches most such violations, but the repair loop may still exhaust attempts.
- **Knowledge Base utilisation**: The Debugger can read from the Knowledge Base, but the automatic write-back of high-quality lessons remains limited.
- **Single-threaded execution**: Agents run cooperatively in one process; true parallelism is not yet supported.
- **File I/O**: Workspace JSON files are written without locking; concurrent external access could corrupt state.

## Future Roadmap

- ✅ **v1.0** — Simulated agents with mock responses
- ✅ **v2.0** — Full LLM-powered agents + Fallback + Diagnostics
- ✅ **v3.0-beta** — Context Manager, Debugger, Knowledge Base, Self-Repair Loop
- ✅ **v3.1** — Contract Generator, contract-aware Coder, API Inspector, Supervisor quality gate
- ⬜ **v3.2** — Signature-level contract enforcement (parameter & return type validation)
- ⬜ **v4.0** — Web UI