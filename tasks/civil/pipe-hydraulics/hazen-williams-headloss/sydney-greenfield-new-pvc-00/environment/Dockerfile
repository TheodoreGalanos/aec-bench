# ABOUTME: Auto-generated container for civil — hazen-williams-headloss.
# ABOUTME: Extensions: core only. Regenerate with: aec-bench generate dockerfiles
FROM --platform=linux/amd64 ubuntu:24.04

RUN apt-get update && apt-get install -y \
    bc \
    python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY trajectory_writer.py /workspace/trajectory_writer.py
COPY hazen-williams-headloss_calc.py /workspace/hazen-williams-headloss_calc.py
COPY system_prompt.md /workspace/system_prompt.md
