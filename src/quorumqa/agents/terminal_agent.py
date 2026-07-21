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


from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from quorumqa.qwen_client import QwenClient

AGENT_SYSTEM = (
    "You are an agent operating a real Linux terminal to complete a task. "
    "You can run exactly one shell command per turn and you will be shown "
    "its stdout, stderr, and return code before choosing your next command. "
    "When the task is fully complete, respond with done=true and no command.\n\n"
    'JSON shape: {"done": true|false, "command": "shell command or null", "summary": "one short sentence"}'
)


class QuorumQAAgent(BaseAgent):
    SUPPORTS_ATIF = False
    SUPPORTS_RESUME = False
    SUPPORTS_WINDOWS = False

    def __init__(self, logs_dir, model_name=None, logger=None, mcp_servers=None,
                 skills_dir=None, *args, extra_env=None, client=None, max_turns=30,
                 command_timeout_sec=300, **kwargs):
        super().__init__(logs_dir, model_name=model_name, logger=logger, mcp_servers=mcp_servers,
                          skills_dir=skills_dir, *args, extra_env=extra_env, **kwargs)
        self._client = client or QwenClient()
        self._max_turns = max_turns
        # 300s, not a shorter default: live-measured 2026-07-21 against a
        # real 14-task Terminal-Bench pilot, a 60s command timeout killed
        # 6/14 tasks with RuntimeError before the agent got a real chance --
        # compiling, downloading a model, building a Cython extension all
        # routinely exceed 60s. Same lesson already learned once today for
        # qwen_client.py's own request timeout (120s -> 300s).
        self._command_timeout_sec = command_timeout_sec

    @staticmethod
    def name() -> str:
        return "quorumqa-single"

    def version(self) -> str | None:
        return "0.1.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        # No extra tooling to install -- the agent only issues plain shell
        # commands via environment.exec(), nothing needs to be copied into
        # the container ahead of time for Phase 1.
        pass

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        transcript = []
        total_input_tokens = 0
        total_output_tokens = 0
        model = self.model_name or "qwen3.7-max"

        for turn in range(self._max_turns):
            user_prompt = self._build_prompt(instruction, transcript)
            result = self._client.chat_json(
                model=model, system=AGENT_SYSTEM, user=user_prompt,
                role="terminal_agent", thinking=True,
            )
            total_input_tokens += result.usage.input_tokens
            total_output_tokens += result.usage.output_tokens

            action = parse_next_action(result.data)
            if action.done or action.command is None:
                break

            exec_result = await environment.exec(action.command, timeout_sec=self._command_timeout_sec)
            transcript.append({
                "command": action.command,
                "stdout": exec_result.stdout or "",
                "stderr": exec_result.stderr or "",
                "return_code": exec_result.return_code,
            })

            # Populate as we go, not just at the end, so a timeout or crash
            # mid-loop still leaves a real token count behind -- matching
            # BaseAgent.run()'s own docstring guidance.
            context.n_input_tokens = total_input_tokens
            context.n_output_tokens = total_output_tokens

        context.n_input_tokens = total_input_tokens
        context.n_output_tokens = total_output_tokens
        # Token Plan billing, not per-token USD -- see qwen_client.py's own
        # cost_usd=0.0 note. No honest dollar figure to report here either.
        context.cost_usd = 0.0

    @staticmethod
    def _build_prompt(instruction: str, transcript: list[dict]) -> str:
        lines = [f"Task: {instruction}", ""]
        if not transcript:
            lines.append("No commands run yet. Propose the first one.")
        else:
            lines.append("Commands run so far, most recent last:")
            for entry in transcript:
                lines.append(f"$ {entry['command']}")
                if entry["stdout"]:
                    lines.append(f"stdout: {entry['stdout'][:2000]}")
                if entry["stderr"]:
                    lines.append(f"stderr: {entry['stderr'][:2000]}")
                lines.append(f"return code: {entry['return_code']}")
                lines.append("")
        return "\n".join(lines)
