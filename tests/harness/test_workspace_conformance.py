# ABOUTME: Runs the shared artifact workspace conformance matrix.
# ABOUTME: Covers full-copy setup, private staging, deltas, source safety, and cleanup.

from aec_bench.harness.workspace_conformance import REQUIRED_GUARANTEES, run_workspace_conformance


def test_artifact_workspace_conformance() -> None:
    result = run_workspace_conformance()

    assert set(result["proven"]) == REQUIRED_GUARANTEES
