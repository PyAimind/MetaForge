# MetaForge v4.0 – Technical Architecture

## Architecture Overview

MetaForge v4.0 is a multi-agent pipeline that transforms a natural language project idea into a tested, runnable multi-module Python codebase, now with a full desktop UI on top. The system is built around specialised agents that communicate through a central message bus using per-agent message queues, with a shared workspace for state and logging. An LLM provider integration enables intelligent design and code generation.

Version 4.0 adds a **local UI layer** on top of the existing pipeline. The UI does not replace any CLI behaviour; it observes and controls the same pipeline through a FastAPI backend with WebSocket streaming.

### New in v4.0

- **Event Stream Foundation** – A structured `EventEmitter` writes JSON Lines events to stderr when `METAFORGE_STRUCTURED=1`. The CLI behaviour is unchanged when this mode is off.
- **ProjectStore** – Persistent per-project storage under `projects/<uuid>/`, holding metadata, structure, contracts, thinking log, and generated output.
- **FastAPI Backend + Runner** – A local HTTP + WebSocket server that spawns the CLI pipeline as a subprocess, captures structured events, saves them to the ProjectStore, and streams them live to the UI.
- **Timeline Events** – User-facing, human-readable timeline entries emitted during runs (e.g. `"Writing storage.py"`, `"storage.py passed"`, `"Refining the solution"`).
- **Live Timeline UI** – A vertical animated timeline that grows as the pipeline runs, with auto-scroll and category-based colors.
- **Project History UI** – A drawer listing all past projects with rename, delete, and reopen support.
- **Code Viewer UI** – A syntax-highlighted viewer for every generated module, with a copy button.
- **Atmospheric Home Screen** – A two-layer drifting fog background rendered entirely in CSS, and a real-time Three.js glass logo with procedural environment reflections.

The core v3.3 pipeline remains completely unchanged.

### New in v3.3 (still active in v4.0)

- **Generic Acceptance Testing Engine** – Tester is no longer hardcoded for Todo. It executes a project-agnostic `acceptance_tests` specification produced by the Engineer/StructureDesigner.
- **Entrypoint-Aware Validation** – Modules with `type: "entrypoint"` (e.g. `cli.py`) skip API Inspector structural checks, while `library` modules continue to be validated strictly.
- **Shared Runtime Isolation** – All acceptance tests for a project run inside a single temporary directory, preserving state across sequential commands while preventing leakage between runs.
- **Acceptance Criteria Injection** – Coder and repair prompts include acceptance test requirements as mandatory behavioural contracts.
- **Robust Acceptance Test Generation** – StructureDesignerLLM applies deterministic rules for generating acceptance tests.

### Core Components

- **Supervisor** – orchestrates the entire workflow, manages state transitions, and handles error recovery. It stores `acceptance_tests`, manages `acceptance_repair_pending`, and decides when to run final acceptance.
- **Engineer** – designs the project structure and generates contract-aware coding prompts. During repair, it can generate a multi-module repair prompt containing all relevant module sources and contracts.
- **Coder** – writes Python code using an LLM-powered generator. It reads `contracts.json`, injects contracts into prompts, and updates `generated` flags.
- **Tester** – executes generated code safely and returns structured results. Its acceptance test executor is generic and runs in a shared temporary directory per project.
- **Debugger** – analyses test failures and produces structured diagnoses.
- **Contract Generator** – extracts public API contracts from the project structure and persists them as `contracts.json`, including `type` metadata.
- **API Inspector** – validates a generated Python file against its declared contract using AST analysis. Skipped for entrypoint modules.
- **Semantic Analyzer** – performs cross-module semantic checks using dependency contracts.
- **MessageChannel** – thread-safe queue-based message bus.
- **WorkspaceManager** – persistent short-term memory backed by JSON files.
- **ContextManager** – collects structural information about generated modules.
- **KnowledgeBase** – stores lessons, successful patterns, and failures.
- **LLMProvider** – HTTP client for the DeepSeek API or compatible endpoint.

### v4.0 UI Components

- **EventEmitter** (`communication/events.py`) — writes structured JSON Lines events to a stream (default: stderr). Schema version 1.
- **ProjectStore** (`project_store.py`) — filesystem-backed store for project metadata, structure, contracts, thinking log, and output.
- **RunManager** (`ui/runner.py`) — spawns `main.py` as a subprocess, reads structured events from stderr, appends them to the ProjectStore, and broadcasts them to WebSocket subscribers. Only one subprocess is allowed at a time.
- **FastAPI Server** (`ui/server.py`) — REST endpoints for projects, modules, and thinking logs, plus a WebSocket endpoint for live event streaming.
- **Frontend** (`ui/static/`) — pure HTML, CSS, and vanilla JavaScript modules. Uses highlight.js for syntax highlighting and Three.js for the glass logo. No framework, no bundler, no CDN.

---

## Agent Roles

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

### Engineer (`agents/engineer.py`)

- Accepts `design_structure`, `generate_prompts`, `generate_single_prompt`.
- During repair, if the repair context contains `all_modules`, the Engineer builds a multi-module repair prompt.

### Coder (`agents/coder.py`)

- Loads the module's contract from `contracts.json` and injects it into the generation prompt.
- For entrypoint modules, includes acceptance tests in `module_info`.
- In repair mode, uses the Engineer-provided prompt and parses multi-module JSON responses.

### Tester (`agents/tester.py`)

- Contains no project-specific logic.
- `_run_generic_acceptance_tests(acceptance_tests, output_dir)` creates **one shared temporary directory** for the entire batch and executes each test with `working_directory=test_dir`.

### Debugger, Contract Generator, API Inspector, Semantic Analyzer

- Unchanged from v3.3 except for ContractGenerator's `type` preservation.

---

## v4.0 UI Architecture

### Event Stream System

`communication/events.py` defines the `EventEmitter` class. Events are JSON Lines with schema version 1:

```json
{
  "v": 1,
  "ts": 1788945678.123,
  "run_id": "uuid-v4",
  "type": "run_started | timeline_entry | run_completed | run_failed | run_interrupted",
  "payload": { "...": "..." }
}
```

Emission is opt-in via `METAFORGE_STRUCTURED=1`. When this flag is off, `EventEmitter.emit()` is a no-op and the CLI behaves exactly as before.

**Event types currently emitted:**

| Type | Source | Payload |
|------|--------|---------|
| `run_started` | `main.py` | `{idea}` |
| `timeline_entry` | `DiagnosticMessageChannel.send` | `{title, detail, color, icon}` |
| `run_completed` | `main.py` | `{total_runtime, iterations}` |
| `run_failed` | `main.py` | `{reason, total_runtime}` |
| `run_interrupted` | `main.py` | `{total_runtime}` |

### ProjectStore

Located at `project_store.py`. Each project occupies a folder under `projects/<uuid>/`:

```
projects/<uuid>/
├── metadata.json        # id, name, idea, status, created_at, updated_at
├── structure.json       # copy of project_structure.json
├── contracts.json       # copy of contracts.json
├── thinking.jsonl       # one JSON event per line
└── output/              # final generated modules
```

Public API:

- `create(name, idea) -> project_id`
- `list() -> [metadata]`
- `get(project_id) -> metadata`
- `rename(project_id, new_name) -> bool`
- `delete(project_id) -> bool`
- `update_status(project_id, status) -> bool`
- `append_event(project_id, event) -> bool`
- `copy_structure(project_id, path) -> bool`
- `copy_contracts(project_id, path) -> bool`
- `copy_output(project_id, output_dir) -> bool`

All methods are non-raising; they return `True`/`False` or `None` on failure.

### RunManager (`ui/runner.py`)

Spawns `main.py` as a subprocess with:

- `METAFORGE_STRUCTURED=1`
- `METAFORGE_IDEA=<idea>`
- `METAFORGE_PROJECT_ID=<uuid>`

A background thread reads stderr line by line, parses each JSON event, appends it to the ProjectStore, and broadcasts it to all subscribers for that project. When the subprocess exits, the project status is updated based on the final event type (`run_completed` → `completed`, `run_failed` → `failed`, `run_interrupted` → `interrupted`).

Only **one subprocess** is allowed at a time. A `threading.Lock` plus a `_starting` flag prevent concurrent spawns.

### FastAPI Server (`ui/server.py`)

REST endpoints:

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/projects` | Start a new run |
| GET | `/api/projects` | List all projects |
| GET | `/api/projects/{id}` | Get project metadata |
| PATCH | `/api/projects/{id}` | Rename a project |
| DELETE | `/api/projects/{id}` | Delete a project (stops run first if active) |
| GET | `/api/projects/{id}/thinking` | Full thinking log |
| GET | `/api/projects/{id}/modules` | List generated modules |
| GET | `/api/projects/{id}/modules/{filename}` | Module content |
| WS | `/ws/run/{id}` | Live event stream |

The WebSocket endpoint first sends all existing events from `thinking.jsonl`, then streams new events as they arrive. This allows a reconnecting client to reconstruct the full timeline.

### Timeline Events (v4.0 addition)

`DiagnosticMessageChannel.send` in `main.py` inspects each outgoing message and emits a `timeline_entry` event with user-facing wording. This keeps `main.py` unaware of internal state — all mapping happens at the channel boundary.

Example mapping:

| Internal message | Timeline entry |
|------------------|----------------|
| `supervisor → engineer` (`design_structure`) | `"Understanding your idea" / "Analyzing requirements..."` |
| `supervisor → coder` (not fix) | `"Writing storage.py" / "Generating code..."` |
| `coder → supervisor` (success) | `"storage.py written"` |
| `supervisor → tester` | `"Testing storage.py"` |
| `tester → supervisor` (passed) | `"storage.py passed"` |
| `tester → supervisor` (failed) | `"storage.py failed"` |
| `supervisor → engineer` (is_fix) | `"Refining the solution"` |

Colors: `blue`, `purple`, `cyan`, `green`, `orange`, `red`. Icons: `spinner`, `check`, `cross`, `dot`.

### Frontend (`ui/static/`)

Pure HTML, CSS, and vanilla JavaScript modules loaded via `<script type="module">`. No framework, no bundler, no CDN.

```
ui/static/
├── index.html
├── css/
│   ├── theme.css        # variables, reset, scrollbar
│   ├── layout.css       # fog background, topbar, home, drawer, project view
│   └── components.css   # buttons, idea form, timeline, code viewer, modal
├── js/
│   ├── app.js           # entry point, state, view switching
│   ├── api.js           # fetch wrappers for /api/*
│   ├── home.js          # idea form
│   ├── galaxy.js        # fog background (name retained; renders fog, not a galaxy)
│   ├── glasslogo.js     # Three.js glass logo scene
│   ├── project.js       # project view, module list
│   ├── code_viewer.js   # highlight.js wrapper, copy button
│   ├── modal.js         # custom rename/delete modals
│   └── thinking.js      # WebSocket client + timeline renderer
├── assets/
│   ├── logo.svg
│   └── favicon.svg
└── vendor/
    ├── highlight.min.js
    ├── atom-one-dark.min.css
    └── three/
        ├── three.module.js
        ├── FontLoader.js
        ├── TextGeometry.js
        └── helvetiker_bold.typeface.json
```

#### View States

- **Home** – hero (glass logo, headline, idea form) plus optional timeline. When a run starts, the `running` class is added to `#view-home`.
- **Project View** – module list sidebar + code panel. Opened by clicking a project in the drawer.
- **Drawer** – right-side panel for project history.

#### Thinking Panel

The `thinking.js` module connects to `/ws/run/{id}`, renders each `timeline_entry` as a vertical timeline row, auto-scrolls to the newest event, and closes the socket once a terminal event (`run_completed`, `run_failed`, `run_interrupted`) arrives.

Timeline rows use semantic keys (`write:<file>`, `test:<file>`, `verify`) and update in place. For example, `"Writing storage.py"` (spinner) transitions to `"storage.py written"` (check) on the same row. Unnamed spinners (`"Understanding"`, `"Planning"`, `"Refining"`) auto-complete when the next event arrives or when the run terminates.

The active project ID is stored in `localStorage` under `metaforge.active_project_id` so that reloading the page restores the timeline.

#### Drawer

Each project row in the drawer exposes two hover actions: `✎` (Rename) and `×` (Delete). Both use a custom modal (`modal.js`) instead of browser-native `prompt()` and `confirm()`, keeping the dark theme consistent and preventing jarring system dialogs.

---

## Atmospheric Background and Glass Logo

The `#galaxy` element is animated with two CSS pseudo-elements carrying radial gradients with a slow drift, producing a subtle fog effect on a near-black background. Each layer animates independently with different speed and direction to avoid visible repetition.

The home hero contains a `<canvas id="glasslogo">` driven by Three.js. `glasslogo.js` builds a `MeshPhysicalMaterial` with `transmission: 1`, `ior: 1.45`, and a custom blue-white equirectangular environment map generated at runtime on a 2D canvas. The logo group (`"Meta"` on top, `"Forge"` below) is slanted via `rotation.z` and animated with a gentle float. When a run starts, the canvas transitions to a compact size at the top of the view.

**Limitation:** The Three.js glass logo does not reproduce studio-quality HDRI reflections of a professional render; it approximates the look with a custom procedural environment map. It is intentional and lightweight.

---

## Acceptance Test Generation

`StructureDesignerLLM` produces `acceptance_tests` at the root level of the project structure.

### Prompt rules

1. Always include a help test:

   ```json
   {"args": ["--help"], "expected_stdout_contains": ["usage"], "expected_return_code": 0}
   ```

2. For deterministic commands, use actual input data in `expected_stdout_contains`.
3. For random/unpredictable output, set `expected_stdout_contains` to `[]`.
4. Only generate a no-arguments error test if the CLI has required arguments.
5. Do not generate tests for optional flags or runtime errors unless explicitly requested.
6. Avoid positional arguments unless the contract defines them.
7. Keep total tests between 2 and 4.

### Tester isolation

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

All runtime files (e.g. `todos.json`) are created inside `test_dir`. Source files remain in `OUTPUT_DIR`.

---

## Self-Repair Loops

Two distinct repair loops exist:

### Module-level repair

Triggered by API Inspector, Semantic Analyzer, or per-module Tester failures. Uses single or multi-module repair prompts.

### Acceptance-level repair

Triggered when final acceptance tests fail. The Supervisor sets `acceptance_repair_pending=True`, builds a project-level repair context, and requests a repair from Engineer. The same `acceptance_tests` are re-used after repair.

---

## Contract Lifecycle

1. Engineer designs structure with explicit exports, `type`, and `required_imports`.
2. StructureDesigner produces `acceptance_tests`.
3. ContractGenerator creates `contracts.json` including `type`.
4. Coder loads contract, implements it, sets `generated: true`.
5. API Inspector verifies structural compliance (skipped for entrypoint).
6. Semantic Analyzer verifies cross-module usage.
7. Tester runs the module.
8. Supervisor sets `validated: true` on success.
9. Final acceptance tests run; only if they pass is the project marked completed.

> **Note:** Signature-level enforcement (parameter types, return values) is **not** implemented. It remains a limitation.

---

## End-to-End Validation

MetaForge v4.0 has been validated with real CLI projects through the UI pipeline.

**Validated projects:**

- **Todo App** — `storage.py`, `todo_manager.py`, `cli.py`
- **Temperature Converter** — `converter.py`, `cli.py`
- **Password Generator** — `generator.py`, `cli.py`

**Notable observation:** Todo App passes or fails across runs due to LLM non-determinism in generated CLI code (missing state persistence in some commands). This is a known limitation of the current LLM-driven repair loop, not of the UI layer.

File Organizer is only partially validated; file-system acceptance tests require fixture support that is deferred to v4.1.

---

## Known Technical Limitations

- Non-CLI projects (GUI, interactive, web) are not yet fully supported.
- File-system acceptance tests requiring pre-existing fixtures are only partially covered.
- Acceptance tests are generic but not exhaustive.
- The underlying LLM is non-deterministic; identical ideas can produce different structures.
- Repair loops are bounded by configured attempt limits.
- Runtime isolation currently applies only to the acceptance-test environment.
- The v4.0 UI runs on a single local port (8765 by default) and does not yet support remote access or multiple concurrent runs.
- `FileResponse` and `StaticFiles` are used from FastAPI without authentication; the server is intended for local use only.
- The Three.js glass logo uses a procedural environment map, not a real HDRI. Reflections are approximated for performance and portability.

---

## Future Roadmap

- ✅ **v1.0** – Simulated agents with mock responses
- ✅ **v2.0** – Full LLM-powered agents + Fallback + Diagnostics
- ✅ **v3.0-beta** – Context Manager, Debugger, Knowledge Base, Self-Repair Loop
- ✅ **v3.1** – Contract Generator, contract-aware Coder, API Inspector
- ✅ **v3.2** – Semantic Analysis, improved multi-module repair, isolated acceptance testing
- ✅ **v3.3** – Generic acceptance testing, entrypoint-aware validation, shared runtime isolation
- ✅ **v4.0** – Desktop UI with event stream, ProjectStore, live timeline, project history, and code viewer
- ⬜ **v4.1** – Fixture-aware acceptance tests for file-system operations
- ⬜ **v4.2** – Error handling UI, pause/resume, checkpointing
- ⬜ **v5.0** – Remote deployment, multi-project runtime, and extended UI capabilities
```

---

## ۳. `docs/README.md` — نسخه‌ی کامل

```markdown
# MetaForge Documentation Assets

This folder holds all media used in the main README and the project documentation.

## Structure

```
docs/
├── screenshots/     Static PNG images
└── demos/           MP4 videos
```

## Screenshots

| File | Content | Used in README section |
|------|---------|------------------------|
| `01-home.png` | Home screen with two-layer fog background, Three.js glass logo, and idea input | Getting Started |
| `02-timeline-running.png` | Live timeline with several events | Live Timeline |
| `03-project-view.png` | Project detail with module list | Project View |
| `04-code-viewer.png` | Module code with syntax highlighting | Code Viewer |
| `05-drawer-history.png` | Drawer open with several projects | Project History |

**Recommended size:** 1440px wide PNG, under 500KB each.

## Demos

| File | Content | Duration | Used in README section |
|------|---------|----------|------------------------|
| `demo-full.mp4` | Full run from Home to completion | 20-30s | Hero (top of README) |
| `timeline-live.mp4` | Timeline growing in real time | 10-15s | Live Timeline |
| `code-copy.mp4` | Click module + Copy button | 5-8s | Code Viewer |

**Recommended size:** 1280×720 or 1920×1080 MP4, under 5MB each.

## Recording Guidelines

- Consistent window size across all screenshots
- For Home / Timeline: capture the full browser window
- For Project View / Code Viewer: capture only the content area
- For Drawer: capture the browser window with drawer open
- Use MP4 instead of GIF whenever possible (10x smaller, autoplay on GitHub)
- If GIF is needed, keep under 3MB and 800px wide

## Tools

- **ShareX** — screenshots and screen recording
- **TinyPNG** — PNG compression
- **ScreenToGif** — GIF recording (optional)

## Naming Rules

- All lowercase
- Hyphens for separators (no underscores, no spaces)
- Numeric prefix for screenshots to control order
- Descriptive but short names

## UI Terminology

- **Fog background** — Two-layer drifting fog rendered with CSS radial gradients (module: `galaxy.js`, name retained from an earlier design)
- **Glass logo** — Three.js `MeshPhysicalMaterial` with procedural environment map (module: `glasslogo.js`)
- **Timeline** — Vertical animated event feed shown during a run (module: `thinking.js`)
- **Drawer** — Right-side panel for project history
- **Modal** — Custom dark-theme dialog for rename and delete (module: `modal.js`)
```
