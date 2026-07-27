# ABOUTME: Defines the content-pinned Python dependency surface for remote kernel execution.
# ABOUTME: Keeps Harbor agents and cloud backends on the same provider API versions as the checked lockfile.

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
