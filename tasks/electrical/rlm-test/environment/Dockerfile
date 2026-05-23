# ABOUTME: Container environment for electrical — rlm-test.
# ABOUTME: Extensions: multimodal. PydanticAI with Bedrock support for RLM agent.
FROM --platform=linux/amd64 python:3.13-slim

RUN apt-get update && apt-get install -y \
    bc \
    python3 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pydantic-ai[anthropic,openai,bedrock]

WORKDIR /workspace
