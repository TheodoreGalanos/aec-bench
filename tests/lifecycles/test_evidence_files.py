# ABOUTME: Tests lifecycle evidence file safety and semantic artifact roles.
# ABOUTME: Keeps conditional evidence and operation transactions distinct in finalized records.

from pathlib import Path

from aec_bench.lifecycles.evidence_files import lifecycle_artifact_kind


def test_conditional_evidence_artifacts_keep_protocol_roles() -> None:
    cases = {
        "run/evidence_requests/request-1/action.json": "evidence_request_action",
        "run/evidence_requests/request-1/committed.json": "evidence_request_commit",
        "run/evidence_requests/request-1/artifacts/report.pdf": "requested_evidence",
        "run/workspace/checkpoints/review/evidence-requests.json": "evidence_request_catalog",
        "run/workspace/inbox/review/requests/request-1/report.pdf": "requested_evidence_projection",
    }

    assert {path: lifecycle_artifact_kind(Path(path)) for path in cases} == cases


def test_operation_artifacts_keep_protocol_roles() -> None:
    cases = {
        "run/lifecycle_operations/operation-1/request.json": "lifecycle_operation_request",
        "run/lifecycle_operations/operation-1/action.json": "lifecycle_operation_action",
        "run/lifecycle_operations/operation-1/result-manifest.json": "lifecycle_operation_result_manifest",
        "run/lifecycle_operations/operation-1/committed.json": "lifecycle_operation_commit",
        "run/lifecycle_operations/operation-1/artifacts/result.json": "lifecycle_operation_artifact",
        "run/workspace/checkpoints/review/operations.json": "lifecycle_operation_catalog",
        "run/workspace/operations/current-source.json": "lifecycle_operation_current_source",
        "run/workspace/inbox/review/operations/operation-1/result.json": "lifecycle_operation_projection",
    }

    assert {path: lifecycle_artifact_kind(Path(path)) for path in cases} == cases


def test_recovered_episode_artifacts_keep_distinct_roles() -> None:
    cases = {
        "run/sessions/session-1/environment_prepared_episode_request.json": (
            "environment_prepared_lifecycle_episode_request"
        ),
        "run/sessions/session-1/environment_prepared_episode_result.json": (
            "environment_prepared_lifecycle_episode_result"
        ),
        "run/sessions/session-1/environment_prepared_rejected_episode_result.json": (
            "environment_prepared_lifecycle_episode_result"
        ),
        "run/sessions/session-1/rejected_episode_result.json": "rejected_lifecycle_episode_result",
        "run/sessions/session-1/agent_result.corrupt.json": "corrupt_agent_result",
    }

    assert {path: lifecycle_artifact_kind(Path(path)) for path in cases} == cases
