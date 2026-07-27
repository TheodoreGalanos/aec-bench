# ABOUTME: Defines the host-only provider operations required by the Morph environment.
# ABOUTME: Builds default operations from explicit resource sizes without owning lifecycle state.

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from aec_bench.providers.morph_cloud import MorphCommandResult
from aec_bench.providers.proposal_morph_cloud import ProposalMorphCloudOperations

from .constants import MORPH_MIN_DISK_SIZE_MB


class ProposalMorphHarborOperations(Protocol):
    """Host-only provider surface used by the proposal environment."""

    def build_proposal_runtime_snapshot(
        self,
        *,
        dockerfile_path: Path,
        context_dir: Path,
        runtime_archive_path: Path,
        runtime_archive_sha256: str,
        runtime_archive_content_sha256: str,
        runtime_packages: tuple[str, ...],
    ) -> object: ...

    def start_instance(self, *, snapshot: object) -> object: ...

    def start_proposal_container(
        self,
        *,
        instance: object,
        role: str,
        workspace_dir: str,
        logs_dir: str,
        tests_dir: str,
    ) -> str: ...

    def trial_container_identity(self, *, instance: object) -> str: ...

    def stop_trial_container(
        self,
        *,
        instance: object,
        expected_container_identity: str,
    ) -> None: ...

    def reset_trial_mounts(self, *, instance: object) -> None: ...

    def read_stopped_trial_artifacts(
        self,
        *,
        instance: object,
    ) -> dict[str, bytes]: ...

    def run_container_command_result(
        self,
        *,
        instance: object,
        command: tuple[str, ...],
        workdir: str | None = None,
        env: dict[str, str] | None = None,
        timeout_seconds: int | None = None,
    ) -> MorphCommandResult: ...

    def write_instance_file(
        self,
        *,
        instance: object,
        remote_path: str,
        content: bytes,
    ) -> None: ...

    def upload_directory(
        self,
        *,
        instance: object,
        local_path: Path,
        remote_path: str,
    ) -> None: ...

    def read_container_file(
        self,
        *,
        instance: object,
        remote_path: str,
    ) -> bytes | None: ...

    def read_container_directory_archive(
        self,
        *,
        instance: object,
        remote_path: str,
    ) -> bytes | None: ...

    def scrub_trial_instance(self, *, instance: object) -> None: ...

    def stop_instance(self, *, instance: object) -> None: ...

    def delete_snapshot(self, *, snapshot: object) -> None: ...


def default_proposal_morph_operations(
    *,
    cpus: int,
    memory_mb: int,
    storage_mb: int,
) -> ProposalMorphHarborOperations:
    """Construct the one default Morph operations implementation."""

    return ProposalMorphCloudOperations(
        vcpus=cpus,
        memory_mb=memory_mb,
        disk_size_mb=max(storage_mb, MORPH_MIN_DISK_SIZE_MB),
    )
