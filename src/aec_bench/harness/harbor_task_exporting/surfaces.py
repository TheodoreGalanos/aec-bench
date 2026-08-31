# ABOUTME: Renders and validates canonical Harbor task, agent, and verifier surfaces.
# ABOUTME: Keeps generated control files identical across export and bridge admission.

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import cast

from aec_bench.contracts.evidence_lifecycle import EvidenceLifecycleSpec, LifecycleTaskMetadata
from aec_bench.lifecycles.catalogue import lifecycle_operation_resolver
from aec_bench.lifecycles.compiled import CompiledLifecycleEnvelope
from aec_bench.lifecycles.runtime.lifecycle import release_checkpoint

from .constants import (
    BASE_IMAGE,
    HARBOR_LIFECYCLE_BRIDGE_MODE,
    OUTPUT_PATH,
    RUNTIME_DEPENDENCIES,
)
from .stable_io import RegularFileSnapshot, directory_sha256, snapshot_text


def stage_initial_context(package_dir: Path, destination: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="aec-bench-harbor-initial-") as raw_run:
        run_dir = Path(raw_run) / "run"
        initial = release_checkpoint(
            Path(package_dir),
            run_dir,
            operation_resolver=lifecycle_operation_resolver(Path(package_dir), run_dir),
        )
        workspace = Path(cast(str, initial["workspace"]))
        destination.mkdir(parents=True)
        for source in sorted(workspace.iterdir()):
            if source.name.startswith("."):
                continue
            target = destination / source.name
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
    if not (destination / "instruction.md").is_file():
        raise ValueError("initial lifecycle context is missing its active instruction")


def validate_canonical_agent_surface(
    *,
    package_dir: Path,
    initial_context: Path,
    instruction: RegularFileSnapshot,
    dockerfile: RegularFileSnapshot,
    metadata: LifecycleTaskMetadata,
    lifecycle: EvidenceLifecycleSpec,
) -> None:
    if snapshot_text(instruction) != instruction_text(metadata=metadata, lifecycle=lifecycle):
        raise ValueError("Harbor canonical agent surface does not match the compiled lifecycle instruction")
    if snapshot_text(dockerfile) != dockerfile_text():
        raise ValueError("Harbor canonical agent surface does not match the supported environment")
    with tempfile.TemporaryDirectory(prefix="aec-bench-harbor-canonical-agent-") as raw_canonical:
        canonical_context = Path(raw_canonical) / "initial"
        stage_initial_context(package_dir, canonical_context)
        if directory_sha256(initial_context) != directory_sha256(canonical_context):
            raise ValueError("Harbor canonical agent surface contains undeclared lifecycle context")


def task_toml_text(*, metadata: LifecycleTaskMetadata, envelope: CompiledLifecycleEnvelope) -> str:
    variant = envelope.variant_id or "unversioned"
    domain = metadata.discipline
    tags = sorted({"compiled-lifecycle", "evidence-lifecycle", domain.lower().replace(" ", "-")})
    return (
        "# ABOUTME: Harbor task metadata for one content-pinned compiled lifecycle.\n"
        "# ABOUTME: Declares a host-owned bridge and Harbor-owned independent reward.\n"
        'version = "1.0"\n\n'
        "[identity]\n"
        f"id = {json.dumps(str(metadata.identity.id))}\n"
        f"key = {json.dumps(str(metadata.identity.key))}\n"
        f"version = {metadata.identity.version}\n\n"
        "[metadata]\n"
        'difficulty = "hard"\n'
        'category = "evidence-lifecycle"\n'
        'lifecycle = "active"\n'
        'visibility = "public"\n'
        f"tags = {json.dumps(tags)}\n"
        f"domain = {json.dumps(domain)}\n"
        f"source_template_id = {json.dumps(envelope.template_id)}\n"
        f"source_lifecycle_id = {json.dumps(envelope.lifecycle_id)}\n"
        f"source_variant_id = {json.dumps(variant)}\n"
        f"source_package_sha256 = {json.dumps(envelope.package_sha256)}\n"
        f"operation_protocol_sha256 = {json.dumps(envelope.operation_protocol_sha256)}\n"
        f"lifecycle_bridge_mode = {json.dumps(HARBOR_LIFECYCLE_BRIDGE_MODE)}\n\n"
        "[agent]\n"
        "timeout_sec = 3600.0\n\n"
        "[verifier]\n"
        "timeout_sec = 600.0\n\n"
        "[environment]\n"
        "build_timeout_sec = 1800.0\n"
        "cpus = 2\n"
        "memory_mb = 4096\n"
        "storage_mb = 10240\n"
        'network_mode = "no-network"\n'
    )


def instruction_text(*, metadata: LifecycleTaskMetadata, lifecycle: EvidenceLifecycleSpec) -> str:
    checkpoint_lines = "\n".join(
        f"- `{checkpoint.checkpoint_id}`: {checkpoint.title}" for checkpoint in lifecycle.checkpoints
    )
    return (
        f"# {metadata.name}\n\n"
        "Complete this staged evidence lifecycle through the task-owned lifecycle tools. The host releases only "
        "the active checkpoint context and declared operation results; arbitrary shell access is unavailable.\n\n"
        "The agent must not write a reward. Preserve the completed lifecycle run at `/workspace/lifecycle-run`; "
        "Harbor uploads the hidden verifier package only after the agent phase and assigns reward independently.\n\n"
        "## Checkpoints\n\n"
        f"{checkpoint_lines}\n"
    )


def dockerfile_text() -> str:
    return (
        "# ABOUTME: Provides a minimal agent surface for a host-owned lifecycle bridge.\n"
        "# ABOUTME: Contains public initial context but no AEC-Bench source or verifier authority.\n"
        f"FROM --platform=linux/amd64 {BASE_IMAGE}\n\n"
        f"RUN python -m pip install --no-cache-dir {' '.join(RUNTIME_DEPENDENCIES)}\n"
        "COPY context/ /workspace/context/\n"
        "RUN chmod -R a-w /workspace/context\n"
        "WORKDIR /workspace\n"
    )


def test_script_text(wheel_name: str) -> str:
    return f"""#!/bin/sh
# ABOUTME: Runs the hidden lifecycle verifier after Harbor ends the agent phase.
# ABOUTME: Loads the content-pinned verifier runtime only from Harbor's tests upload.
set -eu

PACKAGE_DIR="${{AEC_BENCH_COMPILED_WORLD_DIR:-/tests/compiled-world}}"
RUN_DIR="${{AEC_BENCH_LIFECYCLE_RUN_DIR:-{OUTPUT_PATH}}}"
ENVELOPE_PATH="${{AEC_BENCH_ENVELOPE_PATH:-/tests/compiled-world-envelope.json}}"
EXPORT_MANIFEST="${{AEC_BENCH_EXPORT_MANIFEST:-/tests/compiled-world-export.json}}"
INITIAL_CONTEXT="${{AEC_BENCH_INITIAL_CONTEXT_DIR:-/workspace/context/initial}}"
VERIFIER_RUNTIME="${{AEC_BENCH_VERIFIER_RUNTIME:-/tests/runtime/{wheel_name}}}"
REWARD_PATH="${{AEC_BENCH_REWARD_PATH:-/logs/verifier/reward.json}}"
DETAILS_PATH="${{AEC_BENCH_DETAILS_PATH:-/logs/verifier/details.json}}"
PYTHON_BIN="${{AEC_BENCH_PYTHON:-python3}}"
RUNTIME_DIR="$(mktemp -d)"
"$PYTHON_BIN" -m zipfile -e "$VERIFIER_RUNTIME" "$RUNTIME_DIR"

PYTHONPATH="$RUNTIME_DIR${{PYTHONPATH:+:$PYTHONPATH}}" "$PYTHON_BIN" \\
  -m aec_bench.harness.harbor_task_export verify \\
  --package-dir "$PACKAGE_DIR" \\
  --run-dir "$RUN_DIR" \\
  --envelope "$ENVELOPE_PATH" \\
  --export-manifest "$EXPORT_MANIFEST" \\
  --initial-context "$INITIAL_CONTEXT" \\
  --verifier-runtime "$VERIFIER_RUNTIME" \\
  --reward-path "$REWARD_PATH" \\
  --details-path "$DETAILS_PATH"
"""
