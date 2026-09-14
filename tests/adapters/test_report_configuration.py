# ABOUTME: Validates supported report configurations before provider work.
# ABOUTME: Checks unknown keys, ineffective modes, explicit precedence, and host bounds.

import pytest

from aec_bench.adapters.base import AdapterRequest
from aec_bench.adapters.lambda_rlm.config import parse_lambda_rlm_config
from aec_bench.adapters.rlm.config import parse_rlm_config
from aec_bench.adapters.rlm.request_runtime import resolve_rlm_request


@pytest.mark.parametrize(
    "config",
    [
        '[execution]\ncontext_strategy="full"',
        "[execution]\ncontext_limit=0",
        "[execution]\ncompaction_threshold_pct=0.99\nhard_ceiling_pct=0.95",
        '[template]\ndefiniton="template.toml"',
        '[constitution]\nmodel="inference-model"',
    ],
)
def test_invalid_guided_configuration_is_rejected(config: str) -> None:
    with pytest.raises(ValueError):
        parse_rlm_config(config)


@pytest.mark.parametrize(
    "config",
    [
        "[sandbox]\ntool_use=true",
        "[sandbox.tool_use_caps]\nmax_total_fetches=2",
        "[compose]\nplanning_phase_blocking=false",
        "[fill_section]\nk_candidates=2",
        '[fill_section]\ntournament_mode="round_robin"',
        "[execution]\nmax_parallel_workers=0",
        '[review]\ntrigger="consistency"',
        '[review]\ntrigger="unknown"',
        '[fill_section.synthesis]\nsynthesis_mode="tool_loop"',
        '[constitution]\nmodel="inference-model"',
        '[execution]\ncontext_strategy="full"',
        "[guardrails]\nmax_iterationz=2",
    ],
)
def test_invalid_lambda_configuration_is_rejected(config: str) -> None:
    with pytest.raises(ValueError):
        parse_lambda_rlm_config(config)


def test_condition_overrides_authored_values_but_cannot_raise_host_limits() -> None:
    config = parse_rlm_config(
        "[guardrails]\ntoken_budget=100\n[execution]\ncontext_limit=128000",
        overrides={
            "guardrails": {"token_budget": 500},
            "execution": {"context_limit": 64000},
        },
    )
    assert config.guardrails.token_budget == 500
    assert config.execution.context_limit == 64000
    effective = resolve_rlm_request(
        AdapterRequest(instruction="Report", configuration={"token_budget": 200, "context_budget_tokens": 32000}),
        guardrails=config.guardrails,
        execution=config.execution,
    )
    assert effective.token_budget == 200
    assert effective.context_limit == 32000
