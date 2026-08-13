# MetaForge

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![LLM](https://img.shields.io/badge/LLM-Powered-orange.svg)]()
[![Multi-Agent](https://img.shields.io/badge/Architecture-Multi--Agent-green.svg)]()
[![Version](https://img.shields.io/badge/Version-3.2-brightgreen.svg)]()

MetaForge transforms a natural-language software idea into a runnable multi-module Python project using a coordinated team of LLM-powered agents.

It is designed as an automated software-engineering pipeline that can design, generate, inspect, test, diagnose, repair, and validate generated projects before declaring them complete.

---

## Why MetaForge?

Unlike simple AI wrappers that ask a single model to generate an entire project, MetaForge uses a structured multi-agent architecture where different agents are responsible for different stages of the software-development process.

The system combines project design, contract-driven generation, structural inspection, semantic analysis, runtime testing, diagnostics, and self-repair into a single workflow.

The core philosophy is:

> **Generation is not enough. A generated project should be inspected, tested, repaired when necessary, and validated before completion.**

---

## How It Works

```mermaid
flowchart TD
    A[User Idea] --> B[Supervisor]
    B --> C[Engineer]
    C --> B
    B --> D[Contract Generator]
    D --> B
    B --> E[Coder]
    E --> B
    B --> F[API Inspector]
    F --> B
    B --> G[Semantic Analyzer]
    G --> B
    B --> H[Tester]
    H --> B
    H --> I{Validation Result}
    I -->|Failure| J[Debugger / Repair Loop]
    J --> B
    I -->|Success| K[Validated Project]
```

MetaForge coordinates these stages through a message-passing architecture. The Supervisor controls the overall workflow and determines when a project is ready for completion or requires another repair cycle.

---

## Key Features

- **Multi-Agent Architecture**: Specialized Supervisor, Engineer, Coder, and Tester agents collaborate through a message-driven workflow.
- **Contract-Driven Generation**: Public module APIs are defined before implementation.
- **Contract-Aware Coding**: The Coder receives explicit project and module contracts when generating code.
- **API Inspection**: Generated modules are checked against their declared public APIs.
- **Semantic Analysis**: Cross-module compatibility is analyzed beyond basic structural validation.
- **Multi-Module Repair**: Runtime failures can be analyzed in the context of multiple related modules.
- **Self-Repair Loop**: Detected failures can trigger targeted repair attempts instead of immediately terminating the project.
- **Runtime Acceptance Testing**: Generated CLI applications can be exercised through real command sequences.
- **Isolated Testing**: Acceptance tests run in controlled environments to prevent previous test state from affecting later validation.
- **LLM-Powered Generation**: Uses real LLM calls for project design, implementation, analysis, and repair.
- **Intelligent Failure Handling**: The system can detect failures and stop safely when they cannot be resolved.
- **Built-in Diagnostics**: Development and debugging tools provide visibility into project generation and validation.
- **Knowledge Base**: Successful patterns and lessons from previous failures can be retained.
- **Context Awareness**: Agents receive relevant project context to reduce inconsistent implementations across modules.
- **End-to-End Automation**: The complete workflow can run from a natural-language idea to validated generated code.
- **Modular Architecture**: Major components are separated by responsibility and can be tested or replaced independently.

---

## Version 3.2

Version 3.2 focuses on improving MetaForge's reliability when generating and repairing multi-module projects.

The main improvements include:

- Semantic analysis for cross-module compatibility
- Improved API Inspector integration
- More effective multi-module runtime repair
- Expanded context for repair operations
- Improved diagnostic capabilities for investigating repair-loop failures
- Isolated acceptance-test execution
- Improved protection against stale runtime state between validation attempts
- Real end-to-end validation using an LLM-powered Todo CLI application

These improvements make the repair and validation process more reliable when generated modules interact with one another.

---

## Real-World Validation

MetaForge v3.2 has been validated using a real multi-module Todo CLI application.

The generated application contains:

- `storage.py`
- `todo_manager.py`
- `cli.py`

The complete MetaForge pipeline successfully generated, analyzed, repaired, tested, and validated the project.

Final result:

```
status=completed
ACCEPTANCE TEST PASSED
```

This validation demonstrates the complete workflow on the tested Todo CLI scenario.

It does **not** imply that MetaForge guarantees successful generation for every arbitrary software project.

---

## Example Runs

| Project Idea | Result | Notes |
|---|---|---|
| Simple greeting app | ✅ Completed | Basic generation and validation |
| Calculator CLI with multiple modules | ✅ Completed | Multi-module generation and dependency handling |
| Todo application | ✅ Completed | Multi-module analysis, repair, and acceptance testing validated |

The Todo application became the primary real-world scenario used to validate the reliability improvements introduced in v3.2.

---

## Installation & Usage

```bash
git clone https://github.com/PyAimind/MetaForge.git
cd MetaForge

pip install -r requirements.txt
```

Create a `.env` file in the root directory:

```env
DEEPSEEK_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.deepseek.com/v1/chat/completions
MAX_LLM_REQUESTS=40
LLM_ENGINEER_MODEL=deepseek/deepseek-chat-v3.1
LLM_CODER_MODEL=deepseek/deepseek-chat-v3.1
```

Run MetaForge:

```bash
python main.py
```

Enter a natural-language software idea when prompted.

For example:

```
A simple CLI Todo app with add, remove, list, and JSON storage
```

MetaForge will then coordinate the project through its generation and validation pipeline.

---

## Testing

MetaForge includes unit tests, diagnostic tests, and end-to-end scenarios.

Examples:

```bash
python tests/test_api_inspector.py
python tests/diagnostic_repair_loop_state_investigation.py
python tests/debug_full_todo_generation.py
```

The final test demonstrates the complete LLM-powered generation and validation workflow.

---

## Project Structure

```
MetaForge/
├── main.py
├── agents/
│   ├── supervisor.py
│   ├── engineer.py
│   ├── coder.py
│   ├── tester.py
│   ├── api_inspector.py
│   └── semantic_analyzer.py
│
├── communication/
│   ├── message.py
│   └── message_channel.py
│
├── workspace/
│   └── workspace_manager.py
│
├── project_design/
│   ├── structure_designer_llm.py
│   ├── code_generator_llm.py
│   ├── prompt_generator.py
│   ├── contract_generator.py
│   └── code_executor.py
│
├── memory/
│   └── knowledge_base.py
│
├── diagnostics/
│   ├── common.py
│   ├── diagnose.py
│   └── checks/
│
├── tests/
├── output/
├── requirements.txt
├── .env
└── config.py
```

---

## Current Limitations

MetaForge is still an LLM-driven software-generation system and cannot guarantee correct generation for arbitrary project ideas.

Known limitations include:

- Complex interactive applications may require additional testing support.
- The underlying LLM may occasionally ignore strict generation constraints.
- Semantic analysis depends on the quality of the available project context.
- Contract and API validation cannot replace complete behavioral testing.
- Acceptance-test coverage depends on the type of generated application.
- The repair process is bounded by configured repair limits.
- Different project types may require specialized acceptance tests.
- Generated architecture and semantic quality still depend partly on the selected LLM.

---

## Roadmap

- ✅ **v1.0** — Simulated agents with mock responses
- ✅ **v2.0** — Full LLM-powered agents, fallback handling, and diagnostics
- ✅ **v3.0-beta** — Context Manager, Debugger, Knowledge Base, Self-Repair Loop, and multi-module coordination
- ✅ **v3.1** — Contract Generator, Contract-Aware Coder, API Inspector, and Supervisor validation gate
- ✅ **v3.2** — Semantic Analysis, improved multi-module repair, diagnostic investigation, isolated acceptance testing, and real Todo end-to-end validation
- ⬜ **v4.0** — Web UI

---

## Version History

- **v3.2** — Reliability improvements, Semantic Analyzer, improved multi-module repair, isolated acceptance testing, and real Todo end-to-end validation
- **v3.1** — Contract Layer, `contracts.json`, Contract-Aware Coder, API Inspector, and Supervisor validation gate
- **v3.0-beta** — Context Manager, Debugger, Knowledge Base, Self-Repair Loop, and multi-module coordination
- **v2.0** — Full LLM-powered agents with real API integration, fallback detection, and diagnostic system
- **v1.0** — Simulated agents with mock responses

---

## Technical Documentation

For detailed architecture, internal workflows, repair-loop behavior, diagnostics, contracts, and implementation details, see:

[TECHNICAL.md](TECHNICAL.md)

---

## License

This project is licensed under the MIT License.

