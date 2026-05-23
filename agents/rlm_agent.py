# ABOUTME: RLM REPL agent — provider-agnostic via PydanticAI.
# ABOUTME: Subclasses Harbor's BaseAgent directly, composes aec_bench utility functions.

# DEPRECATED: This file is superseded by agents/entrypoint_agent.py (EntrypointAgent).
# It uses inline scripts instead of the library adapter layer. Kept for rollback
# safety during the transition. Will be removed in a future cleanup pass.

from harbor.agents.base import BaseAgent

from aec_bench.agents._shell import quote_for_shell
from aec_bench.agents.env import build_all_provider_env
from aec_bench.agents.results import read_agent_result
from aec_bench.agents.rlm_script import build_rlm_script
from aec_bench.agents.tools import inject_trajectory_writer


class RlmAgent(BaseAgent):
    """RLM REPL agent using PydanticAI for provider-agnostic execution.

    PydanticAI handles provider routing from env vars:
    Bedrock (AWS_BEARER_TOKEN_BEDROCK), Azure OpenAI (AZURE_OPENAI_ENDPOINT),
    or Anthropic direct (ANTHROPIC_API_KEY).
    """

    @staticmethod
    def name() -> str:
        return "rlm"

    def version(self) -> str | None:
        return "2.0.0"

    async def setup(self, environment) -> None:  # type: ignore[override]
        result = await environment.exec("python3 --version")
        if result.return_code != 0:
            raise RuntimeError(
                f"Python3 not available in sandbox.\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        await inject_trajectory_writer(environment)

    async def run(self, instruction, environment, context) -> None:  # type: ignore[override]
        script = build_rlm_script()
        env_vars = build_all_provider_env(
            instruction,
            self.model_name,
        )
        timeout = 30 * 60  # 30 minutes for RLM (more iterations)
        exec_result = await environment.exec(
            f"python3 -c {quote_for_shell(script)}",
            env=env_vars,
            timeout_sec=timeout,
        )
        result = await read_agent_result(environment, exec_result)
        context.n_input_tokens = result.input_tokens
        context.n_output_tokens = result.output_tokens
        context.metadata = result.metadata
