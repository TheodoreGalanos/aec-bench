# ABOUTME: Tests that the lambda-rlm adapter is registered and buildable.
# ABOUTME: Validates LocalAdapterRegistry can construct a LambdaRlmAdapter.

from aec_bench.adapters.local_registry import LocalAdapterRegistry


def test_lambda_rlm_is_registered():
    registry = LocalAdapterRegistry()
    assert "lambda-rlm" in registry.available_adapters()
