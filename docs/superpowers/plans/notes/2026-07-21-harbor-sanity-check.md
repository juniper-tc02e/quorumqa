# Harbor sanity check, 2026-07-21

## Environment
- `uv tool install harbor --python 3.12` succeeded. `uv tool install "harbor[daytona]"` and even plain `harbor` at the default resolved litellm version (1.93.0) both FAILED: litellm 1.93.0 ships a Rust extension (`litellm-rust`) with no prebuilt Windows wheel, and this machine's Rust/MSVC linker toolchain can't build it (`link.exe` errors, missing VS Build Tools C++ workload). Worked around by forcing an older, pure-Python litellm: `uv tool install harbor --python 3.12 --with "litellm<1.90"`. Confirmed `litellm==1.77.0` ships a `py3-none-any` wheel -- the Rust rewrite landed somewhere between 1.77.0 and 1.93.0.
- `harbor --version` -> `0.20.0`.
- Docker Desktop was not running at the start of this session; started via `"C:\Program Files\Docker\Docker\Docker Desktop.exe"` and polled `docker info` until ready (~2 min).
- Python 3.12.10 was already installed at `C:\Users\Ong Jun Kai\AppData\Local\Programs\Python\Python312\python.exe` -- no separate install needed once `--python 3.12` was passed explicitly (the ambient default was 3.11.15, which doesn't satisfy harbor's `Python>=3.12` requirement).

## CLI facts confirmed directly from `harbor run --help` (not assumed from the earlier research pass)
- `--agent`/`-a` accepts either a name from Harbor's built-in agent list (`aider`, `claude-code`, `nop`, `oracle`, `terminus-2`, etc.) **or a raw custom agent import path in `module.path:ClassName` format** -- confirms `BaseAgent.import_path()`'s format is exactly what Task 4 needs, no separate registration step required.
- `--ak`/`--agent-kwarg key=value` passes additional constructor kwargs straight through to the agent's `__init__` -- this is how `max_turns` (or any other `QuorumQAAgent`-specific kwarg) gets set from the CLI without Harbor-specific plumbing.
- `--task`/`-t org/name` runs a single task, not `--task-id` as speculatively guessed in the original plan -- corrected for Task 4.
- `--dataset`/`-d name@version` selects the dataset; `terminal-bench/terminal-bench-2-1` resolved correctly with no version pin needed.

## Sanity run
```
harbor run -d terminal-bench/terminal-bench-2-1 --task terminal-bench/cancel-async-tasks -a nop -m nop -k 1 -n 1 --jobs-dir /tmp/harbor_jobs
```
Result: 1 trial, 0 exceptions, reward 0.0 (correct -- `nop` does nothing, so the task's own verifier correctly fails it), total runtime 26s. Job results written to `harbor_jobs/2026-07-21__15-21-01/result.json`.

**This confirms the full harness plumbing works end to end on this machine**: dataset resolution, task container build, agent execution (even a no-op one), the task's real verifier running and grading, and job result serialization. Zero harness-level exceptions. Safe to proceed to writing `QuorumQAAgent` against this same, now-verified setup.

Task name used for future steps: `terminal-bench/cancel-async-tasks` (picked from the real task listing at `github.com/harbor-framework/terminal-bench-2-1/tree/main/tasks`, not verified for difficulty -- any task works equally well for Phase 1's integration-proof purpose).
