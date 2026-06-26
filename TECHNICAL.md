# Technical Notes – MetaForge v1.0

## Known Limitations

The current implementation (v1.0) was intentionally kept simple to focus on validating the core multi-agent architecture and workflow. The following limitations are known and planned for future versions:

- **Race condition in file operations**  
  Methods such as `log_event()` and `save_test_result()` use a read-modify-write pattern on JSON files. In a multi-threaded environment, this can lead to data corruption or loss.  
  *Planned for v2.0*: Introduce file-level locking or switch to an asynchronous logging queue.

- **Potential infinite recursion in error handling**  
  If an error occurs inside `read_phase()` and the error handler itself calls `log_event()`, which then fails again, a recursion loop could theoretically occur.  
  *Planned for v2.0*: Implement a low-level `_safe_log()` method that bypasses normal error handling logic.

- **No backup of corrupted state files**  
  When a JSON state file becomes corrupted, `WorkspaceManager` resets it to default values, resulting in loss of previous data.  
  *Planned for v2.0*: Automatically rename corrupted files with a `.bak` extension before resetting them.

## Architecture Decisions

- **Hub-and-spoke communication model**  
  All inter-agent communication passes through the `Supervisor`. While this creates a potential bottleneck, it provides centralized control, easier debugging, and consistent logging.

- **In-memory state with selective persistence**  
  The `Supervisor` maintains critical runtime state (such as `modules`, `prompts`, and `current_module_index`) in memory. It only syncs to the workspace when necessary for crash recovery. This design reduces disk I/O and improves performance.

- **Prompt and code separation**  
  The `Coder` agent is designed to clearly distinguish between prompt instructions and actual code output. This reduces the risk of prompt leakage into generated files.

## Future Roadmap

| Version | Focus Area                              | Key Improvements                              |
|---------|-----------------------------------------|-----------------------------------------------|
| v2.0    | Real LLM Integration                    | Connect agents to actual LLM APIs             |
| v2.0    | Robust Error Recovery                   | Automatic fix → retest loop                   |
| v3.0    | Scalability & Complexity                | Support for larger projects and more agents   |
| v3.0    | Self-Optimization                       | Feedback-driven prompt improvement            |

---

**Note**: This document reflects the state of MetaForge v1.0 and is intended to provide transparency about current limitations and design decisions.