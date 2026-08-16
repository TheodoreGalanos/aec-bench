# ABOUTME: Tests neutral runtime dependency pins and custom Harbor environment bindings.
# ABOUTME: Proves shared execution values do not depend on harness or provider implementations.

import pytest
from pydantic import ValidationError

from aec_bench.contracts.execution_environment import (
    PYDANTIC_AI_RUNTIME_VERSION,
    PYDANTIC_RUNTIME_VERSION,
    RUNTIME_PYTHON_PACKAGES,
    HarborEnvironmentBinding,
)


def test_runtime_packages_pin_the_declared_model_runtime() -> None:
    assert PYDANTIC_RUNTIME_VERSION == "2.13.4"
    assert PYDANTIC_AI_RUNTIME_VERSION == "1.60.0"
    assert f"pydantic=={PYDANTIC_RUNTIME_VERSION}" in RUNTIME_PYTHON_PACKAGES
    assert f"pydantic-ai[anthropic,bedrock,openai]=={PYDANTIC_AI_RUNTIME_VERSION}" in RUNTIME_PYTHON_PACKAGES


def test_harbor_environment_binding_is_strict_and_immutable() -> None:
    binding = HarborEnvironmentBinding(
        backend="custom",
        import_path="example.environment:CustomEnvironment",
        kwargs={"region": "test"},
    )

    assert binding.kwargs == {"region": "test"}
    with pytest.raises(TypeError, match="immutable"):
        binding.kwargs["region"] = "changed"
    with pytest.raises(ValidationError):
        HarborEnvironmentBinding(
            backend="custom",
            import_path="example.environment:CustomEnvironment",
            unexpected=True,
        )
