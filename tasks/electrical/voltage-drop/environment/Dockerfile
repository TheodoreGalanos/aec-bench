# ABOUTME: Container environment for the voltage-drop calculation task.
# ABOUTME: Provides Python 3 and bc on Ubuntu 24.04 for agent use.
FROM --platform=linux/amd64 ubuntu:24.04

RUN apt-get update && apt-get install -y \
    python3 \
    bc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
