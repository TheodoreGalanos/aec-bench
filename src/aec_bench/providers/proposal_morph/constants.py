# ABOUTME: Centralizes stable public paths and bounded Morph proposal payload limits.
# ABOUTME: Keeps the provider facade path and confinement policy free of orchestration state.

from __future__ import annotations

import re

from aec_bench.providers.proposal_morph_cloud import (
    PROPOSAL_EXACT_ARTIFACT_LIMITS as PROPOSAL_EXACT_ARTIFACT_LIMITS,
)
from aec_bench.providers.proposal_morph_cloud import (
    PROPOSAL_HANDOFF_MAX_TOTAL_BYTES as PROPOSAL_HANDOFF_MAX_TOTAL_BYTES,
)
from aec_bench.providers.proposal_morph_cloud import (
    PROPOSAL_SESSION_MAX_FILE_BYTES as PROPOSAL_SESSION_MAX_FILE_BYTES,
)
from aec_bench.providers.proposal_morph_cloud import (
    PROPOSAL_SESSION_MAX_FILES as PROPOSAL_SESSION_MAX_FILES,
)
from aec_bench.providers.proposal_morph_cloud import (
    PROPOSAL_SESSION_MAX_TOTAL_BYTES as PROPOSAL_SESSION_MAX_TOTAL_BYTES,
)
from aec_bench.providers.proposal_morph_cloud import (
    PROPOSAL_SESSION_ROOT as PROPOSAL_SESSION_ROOT,
)

PROPOSAL_MORPH_HARBOR_ENVIRONMENT_IMPORT_PATH = (
    "aec_bench.providers.proposal_morph_harbor:ProposalMorphHarborEnvironment"
)
REMOTE_WORKSPACE_DIR = "/workspace"
REMOTE_LOGS_DIR = "/logs"
REMOTE_TESTS_DIR = "/tests"
MORPH_MIN_DISK_SIZE_MB = 8192

OUTPUT_PATH = "/workspace/output.md"
PROPOSAL_SESSION_RECEIPT_PATH = f"{PROPOSAL_SESSION_ROOT}/session-receipt.json"
TESTS_MAX_FILES = 1024
TESTS_MAX_FILE_BYTES = 32 * 1024 * 1024
TESTS_MAX_TOTAL_BYTES = 256 * 1024 * 1024
INVOCATION_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
