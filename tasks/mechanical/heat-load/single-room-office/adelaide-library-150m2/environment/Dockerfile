# ABOUTME: Auto-generated container for mechanical — heat-load — single-room-office — adelaide-library-150m2.
# ABOUTME: Extensions: claude-cli. Regenerate with: aec-bench generate dockerfiles
FROM --platform=linux/amd64 ubuntu:24.04

RUN apt-get update && apt-get install -y \
    bc \
    curl \
    procps \
    python3 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://claude.ai/install.sh | bash

WORKDIR /workspace

COPY heat_load_calc.py /workspace/heat_load_calc.py
COPY system_prompt.md /workspace/system_prompt.md
