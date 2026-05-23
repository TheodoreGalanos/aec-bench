# ABOUTME: RLM adapter package for recursive language model execution.
# ABOUTME: Provides REPL engine, metadata management, typed sub-calls, and guardrails.

from aec_bench.adapters.rlm.adapter import RlmAdapter
from aec_bench.adapters.rlm.client import (
    ReplayRlmClient,
    RlmClient,
    RlmCompletionResponse,
    RlmMessage,
)
from aec_bench.adapters.rlm.config import (
    ExecutionConfig,
    GuardrailConfig,
    RlmConfig,
    SubcallConfig,
    parse_rlm_config,
)
from aec_bench.adapters.rlm.engine import ExecutionResult, ReplEnvironment
from aec_bench.adapters.rlm.initialiser import build_rlm_adapter
from aec_bench.adapters.rlm.template import ReportTemplate

__all__ = [
    "ExecutionConfig",
    "ExecutionResult",
    "GuardrailConfig",
    "ReplayRlmClient",
    "ReplEnvironment",
    "ReportTemplate",
    "RlmAdapter",
    "RlmClient",
    "RlmCompletionResponse",
    "RlmConfig",
    "RlmMessage",
    "SubcallConfig",
    "build_rlm_adapter",
    "parse_rlm_config",
]
