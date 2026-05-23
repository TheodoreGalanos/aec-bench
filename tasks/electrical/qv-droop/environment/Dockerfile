# ABOUTME: Auto-generated container for electrical — qv-droop.
# ABOUTME: Extensions: multimodal. Regenerate with: aec-bench generate dockerfiles
FROM --platform=linux/amd64 python:3.13-slim

RUN apt-get update && apt-get install -y \
    bc \
    python3 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir matplotlib pydantic-ai[anthropic,openai]

WORKDIR /workspace
