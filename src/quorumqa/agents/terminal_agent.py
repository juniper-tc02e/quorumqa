"""A single, non-deliberating agent for Terminal-Bench-style tasks: ask the
model for the next shell command, run it, feed the result back, repeat.
Phase 1 of docs/agentic-rebuild-scoping.md -- deliberately no multi-agent
logic here, see that doc's Option A/B/C for what comes after this phase
proves the integration point works."""

from dataclasses import dataclass


@dataclass(frozen=True)
class NextAction:
    done: bool
    command: str | None
    summary: str | None


def parse_next_action(data: dict) -> NextAction:
    done = bool(data.get("done", False))
    command = data.get("command")
    summary = data.get("summary")
    if not done and not command:
        # Malformed response: claims more work is needed but gave no
        # command to run. Treat as done rather than looping forever or
        # crashing when this None reaches environment.exec().
        done = True
    return NextAction(done=done, command=command, summary=summary)
