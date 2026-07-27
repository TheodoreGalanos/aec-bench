# ABOUTME: Validates, seals, and reloads evidence crossing the Morph proposal boundary.
# ABOUTME: Preserves exact receipt schemas, content identities, handoff variants, and test modes.

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath

from aec_bench.contracts.harness_kernel import canonical_content_sha256, validate_sha256
from aec_bench.contracts.proposal_execution import (
    ProposalSessionReceipt,
    ProposalSessionStatus,
)

from .boundary import (
    BoundaryPhase,
    HandoffVariant,
    ProposalMorphBoundaryError,
    ProposalMorphCleanupReceipt,
    SealedArtifact,
    SealedHandoff,
    TestsSnapshot,
    VerifierRotationBinding,
)
from .confinement import (
    payloads_sha256,
    read_regular_file,
    read_regular_tree,
    validated_remote_path,
    write_json_atomic,
    write_payload_tree,
)
from .constants import (
    OUTPUT_PATH,
    PROPOSAL_EXACT_ARTIFACT_LIMITS,
    PROPOSAL_HANDOFF_MAX_TOTAL_BYTES,
    PROPOSAL_SESSION_MAX_FILE_BYTES,
    PROPOSAL_SESSION_MAX_FILES,
    PROPOSAL_SESSION_MAX_TOTAL_BYTES,
    PROPOSAL_SESSION_RECEIPT_PATH,
    PROPOSAL_SESSION_ROOT,
    TESTS_MAX_FILE_BYTES,
    TESTS_MAX_FILES,
    TESTS_MAX_TOTAL_BYTES,
)


def load_completed_proposal_morph_cleanup_receipt(
    path: Path | str,
    *,
    expected_runtime_archive_sha256: str,
    expected_runtime_archive_content_sha256: str,
) -> ProposalMorphCleanupReceipt:
    """Load a fail-closed cleanup proof for Harbor import."""

    validate_sha256(expected_runtime_archive_sha256)
    validate_sha256(expected_runtime_archive_content_sha256)
    receipt_path = Path(path)
    raw, receipt, content_sha256 = _read_content_addressed_receipt(
        receipt_path,
        label="proposal Morph cleanup receipt",
    )
    handoff_variant, candidate_failure_sha256 = _cleanup_handoff(receipt)
    _validate_cleanup_schema(receipt, handoff_variant=handoff_variant)
    _validate_completed_cleanup(
        receipt,
        expected_runtime_archive_sha256=expected_runtime_archive_sha256,
        expected_runtime_archive_content_sha256=expected_runtime_archive_content_sha256,
    )
    expected_verifier_identity, rotation_sha256, rotation_content_sha256 = _cleanup_identities(receipt)
    rotation = load_completed_verifier_rotation(
        path=receipt_path.parent / "verifier-rotation.json",
        runtime_archive_sha256=expected_runtime_archive_sha256,
        runtime_archive_content_sha256=expected_runtime_archive_content_sha256,
        expected_container_identity=expected_verifier_identity,
    )
    if (
        rotation.receipt_sha256 != rotation_sha256
        or rotation.receipt_content_sha256 != rotation_content_sha256
        or rotation.handoff_variant is not handoff_variant
        or rotation.candidate_failure_session_receipt_sha256 != candidate_failure_sha256
    ):
        raise ProposalMorphBoundaryError("proposal Morph cleanup rotation receipt identity does not match")
    return ProposalMorphCleanupReceipt(
        receipt_path=receipt_path,
        receipt_sha256=hashlib.sha256(raw).hexdigest(),
        content_sha256=content_sha256,
        runtime_archive_sha256=expected_runtime_archive_sha256,
        runtime_archive_content_sha256=expected_runtime_archive_content_sha256,
        runtime_snapshot_identity=_required_receipt_string(
            receipt,
            "runtime_snapshot_identity",
            label="proposal Morph cleanup receipt",
        ),
        trial_instance_identity=_required_receipt_string(
            receipt,
            "trial_instance_identity",
            label="proposal Morph cleanup receipt",
        ),
        rotation_receipt_sha256=rotation_sha256,
        rotation_receipt_content_sha256=rotation_content_sha256,
        verifier_container_identity=expected_verifier_identity,
        handoff_variant=handoff_variant.value,
        candidate_failure_session_receipt_sha256=candidate_failure_sha256,
    )


def _cleanup_handoff(
    receipt: Mapping[str, object],
) -> tuple[HandoffVariant, str | None]:
    raw_handoff_variant = receipt.get("handoff_variant")
    if raw_handoff_variant is None:
        return HandoffVariant.COMPLETED_OUTPUT, None
    if raw_handoff_variant == HandoffVariant.CANDIDATE_FAILURE.value:
        return (
            HandoffVariant.CANDIDATE_FAILURE,
            _required_receipt_sha256(
                receipt,
                "candidate_failure_session_receipt_sha256",
                label="proposal Morph cleanup receipt",
            ),
        )
    raise ProposalMorphBoundaryError("proposal Morph cleanup receipt has an unsupported handoff variant")


def _validate_cleanup_schema(
    receipt: Mapping[str, object],
    *,
    handoff_variant: HandoffVariant,
) -> None:
    expected_fields = {
        "boundary_phase_at_stop",
        "content_sha256",
        "delete_requested",
        "expected_verifier_container_identity",
        "failure_steps",
        "observed_verifier_container_identity",
        "rotation_receipt_content_sha256",
        "rotation_receipt_sha256",
        "rotation_receipt_verified",
        "runtime_archive_content_sha256",
        "runtime_archive_sha256",
        "runtime_snapshot_deleted",
        "runtime_snapshot_identity",
        "schema_version",
        "status",
        "trial_instance_identity",
        "trial_instance_scrubbed",
        "trial_instance_stopped",
        "verifier_container_identity_verified",
        "verifier_container_scrubbed",
        "verifier_container_stopped",
    }
    if handoff_variant is HandoffVariant.CANDIDATE_FAILURE:
        expected_fields.update(
            {
                "candidate_failure_session_receipt_sha256",
                "handoff_variant",
            }
        )
    if set(receipt) != expected_fields:
        raise ProposalMorphBoundaryError("proposal Morph cleanup receipt fields do not match its schema")


def _validate_completed_cleanup(
    receipt: Mapping[str, object],
    *,
    expected_runtime_archive_sha256: str,
    expected_runtime_archive_content_sha256: str,
) -> None:
    expected_values = (
        (
            "schema_version",
            "aecbench.proposal-morph-cleanup.v1",
            "proposal Morph cleanup receipt schema is unsupported",
        ),
        ("status", "completed", "proposal Morph cleanup receipt is not completed"),
        ("delete_requested", True, "proposal Morph cleanup receipt did not request deletion"),
        (
            "boundary_phase_at_stop",
            BoundaryPhase.VERIFIER.value,
            "proposal Morph cleanup receipt did not close a verifier",
        ),
        (
            "runtime_archive_sha256",
            expected_runtime_archive_sha256,
            "proposal Morph cleanup receipt has the wrong runtime archive identity",
        ),
        (
            "runtime_archive_content_sha256",
            expected_runtime_archive_content_sha256,
            "proposal Morph cleanup receipt has the wrong runtime archive content identity",
        ),
    )
    for field, expected, message in expected_values:
        if receipt.get(field) != expected:
            raise ProposalMorphBoundaryError(message)
    required_true = (
        "rotation_receipt_verified",
        "verifier_container_identity_verified",
        "verifier_container_stopped",
        "verifier_container_scrubbed",
        "trial_instance_scrubbed",
        "trial_instance_stopped",
        "runtime_snapshot_deleted",
    )
    if any(receipt.get(field) is not True for field in required_true):
        raise ProposalMorphBoundaryError("proposal Morph cleanup receipt has incomplete teardown evidence")
    if receipt.get("failure_steps") != []:
        raise ProposalMorphBoundaryError("proposal Morph cleanup receipt records failed teardown steps")


def _cleanup_identities(
    receipt: Mapping[str, object],
) -> tuple[str, str, str]:
    expected_verifier_identity = _required_receipt_string(
        receipt,
        "expected_verifier_container_identity",
        label="proposal Morph cleanup receipt",
    )
    observed_verifier_identity = _required_receipt_string(
        receipt,
        "observed_verifier_container_identity",
        label="proposal Morph cleanup receipt",
    )
    if observed_verifier_identity != expected_verifier_identity:
        raise ProposalMorphBoundaryError("proposal Morph cleanup receipt verifier identities do not match")
    return (
        expected_verifier_identity,
        _required_receipt_sha256(
            receipt,
            "rotation_receipt_sha256",
            label="proposal Morph cleanup receipt",
        ),
        _required_receipt_sha256(
            receipt,
            "rotation_receipt_content_sha256",
            label="proposal Morph cleanup receipt",
        ),
    )


def load_completed_verifier_rotation(
    *,
    path: Path,
    runtime_archive_sha256: str,
    runtime_archive_content_sha256: str,
    expected_container_identity: str,
) -> VerifierRotationBinding:
    """Load and validate one completed candidate-to-verifier rotation."""

    raw, receipt, content_sha256 = _read_content_addressed_receipt(
        path,
        label="proposal verifier rotation receipt",
    )
    _validate_rotation_core(
        receipt,
        runtime_archive_sha256=runtime_archive_sha256,
        runtime_archive_content_sha256=runtime_archive_content_sha256,
    )
    handoff_variant, candidate_failure_sha256 = _rotation_handoff(receipt)
    verifier_identity = _required_receipt_string(
        receipt,
        "verifier_container_identity",
        label="proposal verifier rotation",
    )
    if verifier_identity != expected_container_identity:
        raise ProposalMorphBoundaryError("proposal verifier rotation does not bind the active verifier container")
    return VerifierRotationBinding(
        receipt_sha256=hashlib.sha256(raw).hexdigest(),
        receipt_content_sha256=content_sha256,
        verifier_container_identity=verifier_identity,
        handoff_variant=handoff_variant,
        candidate_failure_session_receipt_sha256=candidate_failure_sha256,
    )


def _validate_rotation_core(
    receipt: Mapping[str, object],
    *,
    runtime_archive_sha256: str,
    runtime_archive_content_sha256: str,
) -> None:
    expected_values = (
        (
            "schema_version",
            "aecbench.proposal-verifier-rotation.v1",
            "proposal verifier rotation receipt schema is unsupported",
        ),
        ("status", "completed", "proposal verifier rotation receipt is not completed"),
        (
            "runtime_archive_sha256",
            runtime_archive_sha256,
            "proposal verifier rotation has the wrong runtime archive identity",
        ),
        (
            "runtime_archive_content_sha256",
            runtime_archive_content_sha256,
            "proposal verifier rotation has the wrong runtime archive content identity",
        ),
    )
    for field, expected, message in expected_values:
        if receipt.get(field) != expected:
            raise ProposalMorphBoundaryError(message)
    required_true = (
        "candidate_container_stopped",
        "artifacts_sealed",
        "mounts_wiped",
        "tests_uploaded",
    )
    if any(receipt.get(field) is not True for field in required_true):
        raise ProposalMorphBoundaryError("proposal verifier rotation receipt is incomplete")


def _rotation_handoff(
    receipt: Mapping[str, object],
) -> tuple[HandoffVariant, str | None]:
    raw_handoff_variant = receipt.get("handoff_variant")
    if raw_handoff_variant is None:
        if "candidate_failure_session_receipt_sha256" in receipt or receipt.get("output_restored") is not True:
            raise ProposalMorphBoundaryError("proposal completed-output verifier rotation receipt is incomplete")
        _required_receipt_sha256(
            receipt,
            "sealed_output_sha256",
            label="proposal verifier rotation receipt",
        )
        return HandoffVariant.COMPLETED_OUTPUT, None
    if raw_handoff_variant == HandoffVariant.CANDIDATE_FAILURE.value:
        failure_sha256 = _required_receipt_sha256(
            receipt,
            "candidate_failure_session_receipt_sha256",
            label="proposal verifier rotation receipt",
        )
        if receipt.get("output_restored") is not False or receipt.get("sealed_output_sha256") is not None:
            raise ProposalMorphBoundaryError("proposal candidate-failure verifier rotation fabricated output evidence")
        return HandoffVariant.CANDIDATE_FAILURE, failure_sha256
    raise ProposalMorphBoundaryError("proposal verifier rotation receipt has an unsupported handoff variant")


def _read_content_addressed_receipt(
    path: Path,
    *,
    label: str,
) -> tuple[bytes, dict[str, object], str]:
    raw = read_regular_file(
        path,
        label=label,
        max_bytes=1024 * 1024,
    )
    try:
        parsed = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProposalMorphBoundaryError(f"{label} is not valid JSON") from error
    if not isinstance(parsed, dict) or any(not isinstance(key, str) for key in parsed):
        raise ProposalMorphBoundaryError(f"{label} must be a JSON object")
    receipt: dict[str, object] = dict(parsed)
    content_sha256 = receipt.get("content_sha256")
    if not isinstance(content_sha256, str):
        raise ProposalMorphBoundaryError(f"{label} has no content identity")
    validate_sha256(content_sha256)
    content = dict(receipt)
    content.pop("content_sha256")
    if canonical_content_sha256(content) != content_sha256:
        raise ProposalMorphBoundaryError(f"{label} content identity changed")
    return raw, receipt, content_sha256


def _required_receipt_string(
    receipt: Mapping[str, object],
    field: str,
    *,
    label: str,
) -> str:
    value = receipt.get(field)
    if not isinstance(value, str) or not value:
        raise ProposalMorphBoundaryError(f"{label} has no {field}")
    return value


def _required_receipt_sha256(
    receipt: Mapping[str, object],
    field: str,
    *,
    label: str,
) -> str:
    value = _required_receipt_string(receipt, field, label=label)
    validate_sha256(value)
    return value


def snapshot_tests(*, source_dir: Path, boundary_dir: Path) -> TestsSnapshot:
    """Capture one mode-sensitive verifier test tree before rotation."""

    payloads, modes = read_regular_tree(
        source_dir,
        label="proposal verifier tests",
        max_files=TESTS_MAX_FILES,
        max_file_bytes=TESTS_MAX_FILE_BYTES,
        max_total_bytes=TESTS_MAX_TOTAL_BYTES,
    )
    if "test.sh" not in payloads:
        raise ProposalMorphBoundaryError("proposal verifier tests are missing required test.sh")
    destination = boundary_dir / "verifier-tests"
    if destination.exists() or destination.is_symlink():
        raise ProposalMorphBoundaryError("proposal verifier tests snapshot already exists")
    temporary = Path(
        tempfile.mkdtemp(
            prefix=".verifier-tests.",
            dir=boundary_dir,
        )
    )
    try:
        write_payload_tree(temporary, payloads, modes=modes)
        temporary.replace(destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return TestsSnapshot(
        path=destination,
        content_sha256=payloads_sha256(
            payloads,
            domain=b"aecbench.proposal-verifier-tests.v1\0",
            modes=modes,
        ),
    )


def tests_content_sha256(source_dir: Path) -> str:
    """Hash one current verifier test tree with its executable modes."""

    payloads, modes = read_regular_tree(
        source_dir,
        label="proposal verifier tests",
        max_files=TESTS_MAX_FILES,
        max_file_bytes=TESTS_MAX_FILE_BYTES,
        max_total_bytes=TESTS_MAX_TOTAL_BYTES,
    )
    if "test.sh" not in payloads:
        raise ProposalMorphBoundaryError("proposal verifier tests are missing required test.sh")
    return payloads_sha256(
        payloads,
        domain=b"aecbench.proposal-verifier-tests.v1\0",
        modes=modes,
    )


def verify_tests_snapshot(snapshot: TestsSnapshot) -> None:
    """Fail if a pinned verifier test tree changed after capture."""

    if tests_content_sha256(snapshot.path) != snapshot.content_sha256:
        raise ProposalMorphBoundaryError("pinned proposal verifier tests snapshot changed after capture")


def seal_artifacts(
    *,
    artifacts: Mapping[str, bytes],
    seal_dir: Path,
    manifest_path: Path,
    runtime_archive_sha256: str,
    runtime_archive_content_sha256: str,
    environment_session_id: str,
    compute_backend: str,
) -> SealedHandoff:
    """Validate and atomically seal the exact candidate-to-verifier handoff."""

    candidate_failure_receipt = _candidate_failure_receipt_if_required(
        artifacts=artifacts,
        expected_environment_session_id=environment_session_id,
        expected_backend=compute_backend,
        expected_runtime_archive_sha256=runtime_archive_sha256,
        expected_runtime_archive_content_sha256=runtime_archive_content_sha256,
    )
    if seal_dir.exists() or seal_dir.is_symlink():
        raise ProposalMorphBoundaryError("proposal artifact seal already exists")
    payloads = _normalized_handoff_payloads(artifacts)
    _persist_sealed_payloads(seal_dir=seal_dir, payloads=payloads)
    sealed = _sealed_artifacts(seal_dir=seal_dir, payloads=payloads)
    _write_seal_manifest(
        manifest_path=manifest_path,
        sealed=sealed,
        runtime_archive_sha256=runtime_archive_sha256,
        runtime_archive_content_sha256=runtime_archive_content_sha256,
        candidate_failure_receipt=candidate_failure_receipt,
    )
    return SealedHandoff(
        artifacts=sealed,
        variant=(
            HandoffVariant.CANDIDATE_FAILURE
            if candidate_failure_receipt is not None
            else HandoffVariant.COMPLETED_OUTPUT
        ),
        candidate_failure_session_receipt_sha256=(
            candidate_failure_receipt.content_sha256 if candidate_failure_receipt is not None else None
        ),
    )


def _candidate_failure_receipt_if_required(
    *,
    artifacts: Mapping[str, bytes],
    expected_environment_session_id: str,
    expected_backend: str,
    expected_runtime_archive_sha256: str,
    expected_runtime_archive_content_sha256: str,
) -> ProposalSessionReceipt | None:
    if OUTPUT_PATH in artifacts:
        return None
    return _load_candidate_failure_session_receipt(
        artifacts=artifacts,
        expected_environment_session_id=expected_environment_session_id,
        expected_backend=expected_backend,
        expected_runtime_archive_sha256=expected_runtime_archive_sha256,
        expected_runtime_archive_content_sha256=expected_runtime_archive_content_sha256,
    )


def _normalized_handoff_payloads(
    artifacts: Mapping[str, bytes],
) -> dict[str, bytes]:
    payloads: dict[str, bytes] = {}
    proposal_session_count = 0
    proposal_session_total = 0
    handoff_total = 0
    for remote_path, content in sorted(artifacts.items()):
        canonical_path = validated_remote_path(remote_path)
        if canonical_path in PROPOSAL_EXACT_ARTIFACT_LIMITS:
            limit = PROPOSAL_EXACT_ARTIFACT_LIMITS[canonical_path]
        elif canonical_path.startswith(f"{PROPOSAL_SESSION_ROOT}/"):
            proposal_session_count += 1
            proposal_session_total += len(content)
            if proposal_session_count > PROPOSAL_SESSION_MAX_FILES:
                raise ProposalMorphBoundaryError("proposal session handoff exceeds its file-count limit")
            if proposal_session_total > PROPOSAL_SESSION_MAX_TOTAL_BYTES:
                raise ProposalMorphBoundaryError("proposal session handoff exceeds its total-byte limit")
            limit = PROPOSAL_SESSION_MAX_FILE_BYTES
        else:
            raise ProposalMorphBoundaryError(f"proposal handoff contains an unallowlisted artifact: {remote_path}")
        if not isinstance(content, bytes):
            raise ProposalMorphBoundaryError(f"proposal handoff artifact is not bytes: {remote_path}")
        if len(content) > limit:
            raise ProposalMorphBoundaryError(f"proposal handoff artifact exceeds its byte limit: {remote_path}")
        handoff_total += len(content)
        if handoff_total > PROPOSAL_HANDOFF_MAX_TOTAL_BYTES:
            raise ProposalMorphBoundaryError("proposal handoff exceeds its total-byte limit")
        relative = PurePosixPath(canonical_path).relative_to("/")
        payloads[relative.as_posix()] = content
    return payloads


def _persist_sealed_payloads(
    *,
    seal_dir: Path,
    payloads: Mapping[str, bytes],
) -> None:
    temporary = Path(
        tempfile.mkdtemp(
            prefix=".sealed-artifacts.",
            dir=seal_dir.parent,
        )
    )
    try:
        write_payload_tree(temporary, payloads)
        temporary.replace(seal_dir)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def _sealed_artifacts(
    *,
    seal_dir: Path,
    payloads: Mapping[str, bytes],
) -> dict[str, SealedArtifact]:
    return {
        f"/{relative}": SealedArtifact(
            path=seal_dir / Path(relative),
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
        )
        for relative, content in sorted(payloads.items())
    }


def _write_seal_manifest(
    *,
    manifest_path: Path,
    sealed: Mapping[str, SealedArtifact],
    runtime_archive_sha256: str,
    runtime_archive_content_sha256: str,
    candidate_failure_receipt: ProposalSessionReceipt | None,
) -> None:
    manifest_payload: dict[str, object] = {
        "schema_version": "aecbench.proposal-artifact-seal.v1",
        "runtime_archive_sha256": runtime_archive_sha256,
        "runtime_archive_content_sha256": runtime_archive_content_sha256,
        "artifacts": [
            {
                "path": remote_path,
                "sha256": artifact.sha256,
                "size_bytes": artifact.size_bytes,
            }
            for remote_path, artifact in sorted(sealed.items())
        ],
    }
    if candidate_failure_receipt is not None:
        manifest_payload["handoff_variant"] = HandoffVariant.CANDIDATE_FAILURE.value
        manifest_payload["candidate_failure_session_receipt_sha256"] = candidate_failure_receipt.content_sha256
    manifest_payload["content_sha256"] = canonical_content_sha256(manifest_payload)
    write_json_atomic(manifest_path, manifest_payload)


def _load_candidate_failure_session_receipt(
    *,
    artifacts: Mapping[str, bytes],
    expected_environment_session_id: str,
    expected_backend: str,
    expected_runtime_archive_sha256: str,
    expected_runtime_archive_content_sha256: str,
) -> ProposalSessionReceipt:
    raw_receipt = artifacts.get(PROPOSAL_SESSION_RECEIPT_PATH)
    if not isinstance(raw_receipt, bytes):
        raise ProposalMorphBoundaryError(
            "output-less proposal handoff lacks its exact candidate-failure session receipt"
        )
    try:
        receipt = ProposalSessionReceipt.model_validate_json(raw_receipt)
    except ValueError as error:
        raise ProposalMorphBoundaryError("output-less proposal session receipt is invalid") from error
    if (
        receipt.status is not ProposalSessionStatus.CANDIDATE_FAILURE
        or receipt.trial_record_permitted
        or receipt.final_output_artifact_sha256 is not None
        or receipt.output_commit_attestation_sha256 is not None
    ):
        raise ProposalMorphBoundaryError("output-less proposal handoff requires a candidate-failure session receipt")
    expected_session_id = f"proposal-session.{expected_environment_session_id}"
    if (
        receipt.session_id != expected_session_id
        or receipt.execution.session_id != expected_session_id
        or receipt.execution.environment_session_id != expected_environment_session_id
        or receipt.execution.backend != expected_backend
    ):
        raise ProposalMorphBoundaryError("output-less proposal session lineage does not match this Harbor environment")
    if (
        receipt.execution.runtime_archive_sha256 != expected_runtime_archive_sha256
        or receipt.execution.runtime_archive_content_sha256 != expected_runtime_archive_content_sha256
    ):
        raise ProposalMorphBoundaryError("output-less proposal session runtime archive identity does not match")
    return receipt


def read_sealed_artifact(
    artifact: SealedArtifact,
    *,
    remote_path: str,
) -> bytes:
    """Reload one sealed artifact and verify exact size and SHA-256."""

    content = read_regular_file(
        artifact.path,
        label=f"sealed proposal artifact {remote_path}",
        max_bytes=artifact.size_bytes,
    )
    if len(content) != artifact.size_bytes or hashlib.sha256(content).hexdigest() != artifact.sha256:
        raise ProposalMorphBoundaryError(f"sealed proposal artifact changed after capture: {remote_path}")
    return content
