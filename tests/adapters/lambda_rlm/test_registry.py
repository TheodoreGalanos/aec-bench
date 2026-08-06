# ABOUTME: Tests that the lambda-rlm adapter is available to local execution.
# ABOUTME: Validates the fixed local composition root advertises Lambda-RLM.

from aec_bench.adapters.local_registry import available_local_adapters


def test_lambda_rlm_is_registered():
    assert "lambda-rlm" in available_local_adapters()
