# ABOUTME: Auto-generated container for mechanical — stormwater-pump-station-control-backup-energy-package.
# ABOUTME: Extensions: core only. Regenerate with: aec-bench generate dockerfiles
FROM --platform=linux/amd64 ubuntu:24.04

RUN apt-get update && apt-get install -y \
    bc \
    python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY trajectory_writer.py /workspace/trajectory_writer.py
COPY stormwater-pump-station-control-backup-energy-package_calc.py /workspace/stormwater-pump-station-control-backup-energy-package_calc.py
COPY system_prompt.md /workspace/system_prompt.md
