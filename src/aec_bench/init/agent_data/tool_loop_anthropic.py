# ABOUTME: Multi-turn Anthropic tool-loop agent — uses Messages API with tool_use.
# ABOUTME: Subclasses Harbor's BaseAgent directly, composes aec_bench utility functions.

from harbor.agents.base import BaseAgent

from aec_bench.agents._shell import quote_for_shell
from aec_bench.agents.env import build_provider_env
from aec_bench.agents.results import read_agent_result
from aec_bench.agents.scripts import build_anthropic_tool_loop_script
from aec_bench.agents.tools import discover_tools, inject_trajectory_writer


class ToolLoopAnthropicAgent(BaseAgent):
    """Multi-turn Anthropic agent with bash + discovered tools."""

    @staticmethod
    def name() -> str:
        return "tool-loop-anthropic"

    def version(self) -> str | None:
        return "1.0.0"

    async def setup(self, environment) -> None:  # type: ignore[override]
        result = await environment.exec("python3 --version")
        if result.return_code != 0:
            raise RuntimeError(f"Python3 not available in sandbox.\nstdout: {result.stdout}\nstderr: {result.stderr}")
        await inject_trajectory_writer(environment)
        self._tools = await discover_tools(environment)

    async def run(self, instruction, environment, context) -> None:  # type: ignore[override]
        script = build_anthropic_tool_loop_script()
        env_vars = build_provider_env(
            "anthropic",
            instruction,
            self.model_name,
            tools=self._tools,
        )
        timeout = 10 * 180 + 60
        exec_result = await environment.exec(
            f"python3 -c {quote_for_shell(script)}",
            env=env_vars,
            timeout_sec=timeout,
        )
        result = await read_agent_result(environment, exec_result)
        context.n_input_tokens = result.input_tokens
        context.n_output_tokens = result.output_tokens
        context.metadata = result.metadata
