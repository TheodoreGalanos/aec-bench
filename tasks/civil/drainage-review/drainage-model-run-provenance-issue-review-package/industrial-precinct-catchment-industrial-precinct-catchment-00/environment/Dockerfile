# ABOUTME: Auto-generated container for civil — drainage-model-run-provenance-issue-review-package.
# ABOUTME: Extensions: core only. Regenerate with: aec-bench generate dockerfiles
FROM --platform=linux/amd64 ubuntu:24.04

RUN apt-get update && apt-get install -y \
    bc \
    python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY trajectory_writer.py /workspace/trajectory_writer.py
COPY sources/catchment-basis.md /workspace/sources/catchment-basis.md
COPY sources/criteria-comments.md /workspace/sources/criteria-comments.md
COPY sources/document-register.md /workspace/sources/document-register.md
COPY sources/drainage-design-memo.md /workspace/sources/drainage-design-memo.md
COPY sources/hydraulic-model-report.md /workspace/sources/hydraulic-model-report.md
COPY sources/model-input-manifest.md /workspace/sources/model-input-manifest.md
COPY sources/network-model-config.md /workspace/sources/network-model-config.md
COPY sources/rainfall-basis.md /workspace/sources/rainfall-basis.md
COPY sources/run-register.md /workspace/sources/run-register.md
COPY system_prompt.md /workspace/system_prompt.md
