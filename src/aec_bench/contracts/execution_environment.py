# ABOUTME: Defines neutral environment values shared by harness and provider implementations.
# ABOUTME: Keeps runtime dependency pins and custom Harbor bindings outside concrete owners.

from __future__ import annotations

from typing import Any

from pydantic import Field

from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr

PYDANTIC_AI_RUNTIME_VERSION = "1.60.0"

RUNTIME_PYTHON_PACKAGES = (
    "pydantic==2.11.10",
    f"pydantic-ai[anthropic,bedrock,openai]=={PYDANTIC_AI_RUNTIME_VERSION}",
    "boto3==1.42.73",
    "botocore==1.42.73",
    "httpx==0.28.1",
    "PyYAML==6.0.3",
    "polars==1.39.0",
)


class HarborEnvironmentBinding(FrozenStrictModel):
    """One explicit custom Harbor environment selected by an outer caller."""

    backend: NonEmptyStr
    import_path: NonEmptyStr
    kwargs: dict[str, Any] = Field(default_factory=dict)
