# ABOUTME: Verifies Morph proposal build contexts against immutable task-package manifests.
# ABOUTME: Admits only descriptor-bound, source-free Docker inputs and the governed output contract.

from __future__ import annotations

import hashlib
from pathlib import Path

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.output_completion import OutputCompletionContract
from aec_bench.harness.proposal_task_packaging.contracts import (
    ProposalTaskPackageError,
    ProposalTaskPackageFile,
    ProposalTaskPackageManifest,
    VerifiedProposalTaskBuildContext,
)
from aec_bench.harness.proposal_task_packaging.file_io import (
    read_regular_payload,
    update_digest_field,
)

_BUILD_CONTEXT_ROLES = {
    ".dockerignore": "agent_build_context",
    "Dockerfile": "agent_build_context",
    "output_contract.json": "public_output_contract",
}


def verify_proposal_task_build_context(
    context_dir: Path,
    *,
    expected_dockerfile: bytes,
    expected_dockerignore: bytes,
) -> VerifiedProposalTaskBuildContext:
    """Prove a Morph build context is the exact source-free derived surface."""

    context = Path(context_dir)
    _validate_build_context_root(context)
    manifest = _load_proposal_task_package_manifest(context.parent)
    observed_payloads = _read_build_context_payloads(context)
    context_entries = _build_context_manifest_entries(manifest)
    _validate_build_context_surface(
        observed_payloads=observed_payloads,
        context_entries=context_entries,
    )
    _validate_build_context_templates(
        observed_payloads,
        expected_dockerfile=expected_dockerfile,
        expected_dockerignore=expected_dockerignore,
    )
    _validate_build_context_output_contract(
        payload=observed_payloads["output_contract.json"],
        manifest=manifest,
    )
    ordered_payloads = tuple(sorted(observed_payloads.items()))
    return VerifiedProposalTaskBuildContext(
        manifest=manifest,
        payloads=ordered_payloads,
        content_sha256=_build_context_sha256(
            payloads=ordered_payloads,
            manifest_sha256=manifest.content_sha256,
        ),
    )


def _validate_build_context_root(context: Path) -> None:
    if context.is_symlink() or not context.is_dir():
        raise ProposalTaskPackageError("proposal build context must be a non-symlink directory")


def _load_proposal_task_package_manifest(parent: Path) -> ProposalTaskPackageManifest:
    manifest_bytes = read_regular_payload(
        parent / "proposal-task-package.json",
        label="proposal task package manifest",
        max_bytes=4 * 1024 * 1024,
    )
    try:
        return ProposalTaskPackageManifest.model_validate_json(manifest_bytes)
    except ValueError as error:
        raise ProposalTaskPackageError("proposal task package manifest is invalid") from error


def _read_build_context_payloads(context: Path) -> dict[str, bytes]:
    observed_payloads: dict[str, bytes] = {}
    for path in sorted(context.rglob("*")):
        relative = path.relative_to(context).as_posix()
        if path.is_symlink():
            raise ProposalTaskPackageError(f"proposal build context contains a symbolic link: {relative}")
        if path.is_dir():
            continue
        observed_payloads[relative] = read_regular_payload(
            path,
            label=f"proposal build context member {relative}",
            max_bytes=16 * 1024 * 1024,
        )
    return observed_payloads


def _build_context_manifest_entries(
    manifest: ProposalTaskPackageManifest,
) -> dict[str, ProposalTaskPackageFile]:
    return {
        item.path.removeprefix("environment/"): item for item in manifest.files if item.path.startswith("environment/")
    }


def _validate_build_context_surface(
    *,
    observed_payloads: dict[str, bytes],
    context_entries: dict[str, ProposalTaskPackageFile],
) -> None:
    expected_paths = set(_BUILD_CONTEXT_ROLES)
    if set(observed_payloads) != expected_paths or set(context_entries) != expected_paths:
        raise ProposalTaskPackageError("proposal build context does not match the source-free manifest surface")
    for relative, expected_role in _BUILD_CONTEXT_ROLES.items():
        manifest_entry = context_entries[relative]
        payload = observed_payloads[relative]
        if (
            manifest_entry.role != expected_role
            or manifest_entry.byte_size != len(payload)
            or manifest_entry.sha256 != hashlib.sha256(payload).hexdigest()
        ):
            raise ProposalTaskPackageError(f"proposal build context identity mismatch: {relative}")


def _validate_build_context_templates(
    observed_payloads: dict[str, bytes],
    *,
    expected_dockerfile: bytes,
    expected_dockerignore: bytes,
) -> None:
    if observed_payloads["Dockerfile"] != expected_dockerfile:
        raise ProposalTaskPackageError("proposal build context Dockerfile is not the source-free template")
    if observed_payloads[".dockerignore"] != expected_dockerignore:
        raise ProposalTaskPackageError("proposal build context .dockerignore is not the source-free template")


def _validate_build_context_output_contract(
    *,
    payload: bytes,
    manifest: ProposalTaskPackageManifest,
) -> None:
    try:
        output_contract = OutputCompletionContract.model_validate_json(payload)
    except ValueError as error:
        raise ProposalTaskPackageError("proposal build context output contract is invalid") from error
    if (
        output_contract.output_path != "/workspace/output.md"
        or canonical_content_sha256(output_contract.model_dump(mode="json")) != manifest.output_contract_sha256
    ):
        raise ProposalTaskPackageError("proposal build context output contract identity mismatch")


def _build_context_sha256(
    *,
    payloads: tuple[tuple[str, bytes], ...],
    manifest_sha256: str,
) -> str:
    digest = hashlib.sha256(b"aecbench.proposal-task-build-context.v1\0")
    for relative, payload in payloads:
        update_digest_field(digest, relative.encode("utf-8"))
        update_digest_field(digest, payload)
    update_digest_field(digest, manifest_sha256.encode("ascii"))
    return digest.hexdigest()
