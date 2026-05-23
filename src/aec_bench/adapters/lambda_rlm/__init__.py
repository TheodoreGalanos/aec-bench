# ABOUTME: Lambda-RLM adapter — deterministic, pre-planned execution for report generation.
# ABOUTME: Replaces open-ended REPL loop with computed decomposition and bounded LLM calls.

from aec_bench.adapters.lambda_rlm.adapter import LambdaRlmAdapter
from aec_bench.adapters.lambda_rlm.config import LambdaRlmConfig, parse_lambda_rlm_config
from aec_bench.adapters.lambda_rlm.initialiser import build_lambda_rlm_adapter

__all__ = [
    "LambdaRlmAdapter",
    "LambdaRlmConfig",
    "build_lambda_rlm_adapter",
    "parse_lambda_rlm_config",
]
