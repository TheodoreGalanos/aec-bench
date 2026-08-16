# ABOUTME: Defines the current Harbor lifecycle export filenames and resource limits.
# ABOUTME: Shares one policy surface across export, bridge loading, and verification.

from __future__ import annotations

from pathlib import Path

HARBOR_LIFECYCLE_BRIDGE_MODE = "host_owned_evidence_lifecycle"
ATTESTATION_FILENAME = "harbor-bridge-attestation.json"
CANONICAL_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
MAX_CANONICAL_SOURCE_FILE_BYTES = 64 * 1024 * 1024
MAX_EXPORT_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_RUNTIME_WHEEL_BYTES = 64 * 1024 * 1024
MAX_TASK_CONTROL_FILE_BYTES = 2 * 1024 * 1024
WHEEL_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
OUTPUT_PATH = "/workspace/lifecycle-run"
BASE_TOOLS = (
    "list_workspace",
    "read_workspace_file",
    "revisit_checkpoint",
    "submit_checkpoint",
    "write_checkpoint_submission",
)
BASE_IMAGE = "python:3.13-slim-bookworm@sha256:9d7f287598e1a5a978c015ee176d8216435aaf335ed69ac3c38dd1bbb10e8d64"
RUNTIME_DEPENDENCIES = (
    "annotated-types==0.7.0",
    "pydantic-core==2.46.4",
    "pydantic==2.13.4",
    "typing-extensions==4.15.0",
    "typing-inspection==0.4.2",
)
HARBOR_SECURITY = {
    "agent_timeout_sec": 3600.0,
    "allow_internet": False,
    "build_timeout_sec": 1800.0,
    "cpus": 2,
    "memory_mb": 4096,
    "storage_mb": 10240,
    "verifier_timeout_sec": 600.0,
}
