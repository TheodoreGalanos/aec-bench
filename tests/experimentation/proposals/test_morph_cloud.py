# ABOUTME: Proves proposal-only Morph image construction consumes a pinned filtered runtime archive.
# ABOUTME: Guards the remote build surface against full project-source upload and archive substitution.

from __future__ import annotations

import base64
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import pytest

from aec_bench.contracts.execution_environment import RUNTIME_PYTHON_PACKAGES
from aec_bench.contracts.harness_kernel import canonical_json_sha256
from aec_bench.contracts.output_completion import OutputCompletionContract
from aec_bench.contracts.task_definition import Visibility
from aec_bench.experimentation.proposals.morph_cloud import (
    _STOPPED_ARTIFACT_FILE_READER,
    _STOPPED_ARTIFACT_INVENTORY_READER,
    ProposalMorphCloudOperations,
    ProposalMorphRuntimeBuildError,
)
from aec_bench.experimentation.proposals.task_package import (
    ProposalTaskPackageFile,
    ProposalTaskPackageManifest,
)
from aec_bench.providers.morph_cloud import MorphCommandResult

_ManifestRole = Literal[
    "harbor_metadata",
    "agent_build_context",
    "public_output_contract",
    "verifier_only",
]


def test_proposal_runtime_build_uploads_only_task_context_and_filtered_archive(
    tmp_path: Path,
) -> None:
    environment_dir = _environment_dir(tmp_path)
    runtime_archive = _runtime_archive(tmp_path)
    build_snapshot = FakeSnapshot("snapshot-build")
    runtime_snapshot = FakeSnapshot("snapshot-runtime")
    builder = FakeInstance(runtime_snapshot=runtime_snapshot)
    client = FakeClient(build_snapshot=build_snapshot, builder=builder)
    operations = RecordingProposalMorphCloudOperations(client_factory=lambda: client)
    archive_sha256 = hashlib.sha256(runtime_archive.read_bytes()).hexdigest()

    result = operations.build_proposal_runtime_snapshot(
        dockerfile_path=environment_dir / "Dockerfile",
        context_dir=environment_dir,
        runtime_archive_path=runtime_archive,
        runtime_archive_sha256=archive_sha256,
        runtime_archive_content_sha256=_runtime_content_sha256(runtime_archive),
        runtime_packages=RUNTIME_PYTHON_PACKAGES,
    )

    assert result is runtime_snapshot
    uploaded_paths = [event for event in operations.events if event.startswith(("upload:", "upload-file:"))]
    assert len(uploaded_paths) == 2
    assert uploaded_paths[0].endswith("/environment:/tmp/aec-bench-runtime-build/task")
    assert uploaded_paths[1] == (f"upload-file:{runtime_archive}:/tmp/aec-bench-runtime-build/proposal-runtime.tar.gz")
    assert not any("src/aec_bench" in event for event in operations.events)
    runtime_dockerfile = next(
        content
        for remote_path, content in operations.written_files
        if remote_path == "/tmp/aec-bench-runtime-build/Dockerfile"
    ).decode()
    assert "COPY proposal-runtime/aec_bench /opt/aec_bench/aec_bench" in runtime_dockerfile
    assert "COPY src/aec_bench" not in runtime_dockerfile
    assert any("sha256sum" in command and archive_sha256 in command for command in operations.commands)
    assert any("rm -rf -- /tmp/aec-bench-runtime-build/task" in command for command in operations.commands)
    assert builder.stopped is True
    assert build_snapshot.deleted is True


def test_proposal_runtime_build_rejects_archive_substitution_before_provider_use(
    tmp_path: Path,
) -> None:
    environment_dir = _environment_dir(tmp_path)
    runtime_archive = _runtime_archive(tmp_path)
    operations = RecordingProposalMorphCloudOperations(
        client_factory=lambda: pytest.fail("provider client must not be opened")
    )

    with pytest.raises(ProposalMorphRuntimeBuildError, match="archive SHA-256"):
        operations.build_proposal_runtime_snapshot(
            dockerfile_path=environment_dir / "Dockerfile",
            context_dir=environment_dir,
            runtime_archive_path=runtime_archive,
            runtime_archive_sha256=hashlib.sha256(b"wrong").hexdigest(),
            runtime_archive_content_sha256=hashlib.sha256(b"logical-runtime").hexdigest(),
            runtime_packages=RUNTIME_PYTHON_PACKAGES,
        )

    assert operations.events == []


def test_proposal_runtime_build_rejects_unsafe_archive_member_before_provider_use(
    tmp_path: Path,
) -> None:
    environment_dir = _environment_dir(tmp_path)
    archive = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive, mode="w:gz") as bundle:
        content = b"escape\n"
        member = tarfile.TarInfo("../escape.py")
        member.size = len(content)
        bundle.addfile(member, io.BytesIO(content))
    operations = RecordingProposalMorphCloudOperations(
        client_factory=lambda: pytest.fail("provider client must not be opened")
    )

    with pytest.raises(ProposalMorphRuntimeBuildError, match="outside the proposal runtime allowlist"):
        operations.build_proposal_runtime_snapshot(
            dockerfile_path=environment_dir / "Dockerfile",
            context_dir=environment_dir,
            runtime_archive_path=archive,
            runtime_archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
            runtime_archive_content_sha256=hashlib.sha256(b"logical-runtime").hexdigest(),
            runtime_packages=RUNTIME_PYTHON_PACKAGES,
        )


def test_proposal_runtime_build_rejects_non_runtime_project_source_before_provider_use(
    tmp_path: Path,
) -> None:
    environment_dir = _environment_dir(tmp_path)
    archive = tmp_path / "non-runtime-source.tar.gz"
    _write_runtime_archive(
        archive,
        extra_members=("aec_bench/meta_harness/compiler.py",),
    )
    operations = RecordingProposalMorphCloudOperations(
        client_factory=lambda: pytest.fail("provider client must not be opened")
    )

    with pytest.raises(
        ProposalMorphRuntimeBuildError,
        match="outside the proposal runtime allowlist",
    ):
        operations.build_proposal_runtime_snapshot(
            dockerfile_path=environment_dir / "Dockerfile",
            context_dir=environment_dir,
            runtime_archive_path=archive,
            runtime_archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
            runtime_archive_content_sha256=_runtime_content_sha256(archive),
            runtime_packages=RUNTIME_PYTHON_PACKAGES,
        )


def test_proposal_runtime_build_rejects_extra_build_context_source_before_provider_use(
    tmp_path: Path,
) -> None:
    environment_dir = _environment_dir(tmp_path)
    forbidden = environment_dir / "src" / "aec_bench" / "meta_harness"
    forbidden.mkdir(parents=True)
    (forbidden / "compiler.py").write_text(
        "# ABOUTME: Must stay host-only.\\n# ABOUTME: Contains proposal policy.\\n",
        encoding="utf-8",
    )
    runtime_archive = _runtime_archive(tmp_path)
    operations = RecordingProposalMorphCloudOperations(
        client_factory=lambda: pytest.fail("provider client must not be opened")
    )

    with pytest.raises(
        ProposalMorphRuntimeBuildError,
        match="does not match the source-free manifest surface",
    ):
        operations.build_proposal_runtime_snapshot(
            dockerfile_path=environment_dir / "Dockerfile",
            context_dir=environment_dir,
            runtime_archive_path=runtime_archive,
            runtime_archive_sha256=hashlib.sha256(runtime_archive.read_bytes()).hexdigest(),
            runtime_archive_content_sha256=_runtime_content_sha256(runtime_archive),
            runtime_packages=RUNTIME_PYTHON_PACKAGES,
        )


def test_proposal_runtime_build_rejects_runtime_package_override_before_provider_use(
    tmp_path: Path,
) -> None:
    environment_dir = _environment_dir(tmp_path)
    runtime_archive = _runtime_archive(tmp_path)
    operations = RecordingProposalMorphCloudOperations(
        client_factory=lambda: pytest.fail("provider client must not be opened")
    )

    with pytest.raises(
        ProposalMorphRuntimeBuildError,
        match="governed runtime lock",
    ):
        operations.build_proposal_runtime_snapshot(
            dockerfile_path=environment_dir / "Dockerfile",
            context_dir=environment_dir,
            runtime_archive_path=runtime_archive,
            runtime_archive_sha256=hashlib.sha256(runtime_archive.read_bytes()).hexdigest(),
            runtime_archive_content_sha256=_runtime_content_sha256(runtime_archive),
            runtime_packages=("aec-bench @ git+https://example.invalid/repo.git",),
        )


def test_stopped_artifact_reader_enforces_incremental_inventory_and_regular_root(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    session = workspace / "proposal-session"
    session.mkdir(parents=True)
    output = workspace / "output.md"
    output.write_bytes(b"answer\n")
    evidence = session / "receipt.json"
    evidence.write_bytes(b'{"status":"completed"}\n')
    policy = {
        "exact": {str(output): 1024},
        "tree_root": str(session),
        "tree_max_entries": 8,
        "tree_max_files": 4,
        "tree_max_file_bytes": 1024,
        "tree_max_total_bytes": 2048,
        "handoff_max_total_bytes": 4096,
    }
    inventory_result = _run_reader_script(
        _STOPPED_ARTIFACT_INVENTORY_READER,
        base64.b64encode(json.dumps(policy, sort_keys=True).encode("utf-8")).decode("ascii"),
    )

    assert inventory_result.returncode == 0, inventory_result.stderr
    inventory = json.loads(inventory_result.stdout)
    assert inventory == [
        {"path": str(output), "size_bytes": len(b"answer\n")},
        {
            "path": str(evidence),
            "size_bytes": len(b'{"status":"completed"}\n'),
        },
    ]
    for item in inventory:
        file_result = _run_reader_script(
            _STOPPED_ARTIFACT_FILE_READER,
            item["path"],
            str(item["size_bytes"]),
            "1024",
        )
        assert file_result.returncode == 0, file_result.stderr
        assert len(base64.b64decode(file_result.stdout)) == item["size_bytes"]

    unsafe_root = workspace / "unsafe-session"
    unsafe_root.symlink_to(session, target_is_directory=True)
    policy["tree_root"] = str(unsafe_root)
    unsafe_result = _run_reader_script(
        _STOPPED_ARTIFACT_INVENTORY_READER,
        base64.b64encode(json.dumps(policy, sort_keys=True).encode("utf-8")).decode("ascii"),
    )
    assert unsafe_result.returncode != 0
    assert "root is not a regular directory" in unsafe_result.stderr


def _environment_dir(tmp_path: Path) -> Path:
    environment_dir = tmp_path / "environment"
    environment_dir.mkdir()
    context_payloads = {
        ".dockerignore": b"*\n!Dockerfile\n",
        "Dockerfile": (
            b"FROM --platform=linux/amd64 python:3.13-slim\n\n"
            b"RUN apt-get update && apt-get install -y --no-install-recommends \\\n"
            b"    bash \\\n"
            b"    bc \\\n"
            b"    ca-certificates \\\n"
            b"    && rm -rf /var/lib/apt/lists/*\n\n"
            b"WORKDIR /workspace\n"
        ),
        "output_contract.json": _output_contract_bytes(),
    }
    for relative, content in context_payloads.items():
        (environment_dir / relative).write_bytes(content)
    manifest_files: dict[str, tuple[bytes, _ManifestRole]] = {
        "instruction.md": (b"instruction\n", "harbor_metadata"),
        "task.toml": (b'version = "1.0"\n', "harbor_metadata"),
        "tests/test.sh": (b"#!/bin/sh\n", "verifier_only"),
        **{
            f"environment/{relative}": (
                content,
                ("public_output_contract" if relative == "output_contract.json" else "agent_build_context"),
            )
            for relative, content in context_payloads.items()
        },
    }
    contract = _output_contract()
    manifest = ProposalTaskPackageManifest(
        task_id="proposal-runtime-test",
        task_revision=hashlib.sha256(b"task").hexdigest(),
        source_task_package_sha256=hashlib.sha256(b"source").hexdigest(),
        problem_view_sha256=hashlib.sha256(b"problem").hexdigest(),
        output_contract_sha256=canonical_json_sha256(contract.model_dump(mode="json")),
        visibility=Visibility.PUBLIC,
        files=tuple(
            ProposalTaskPackageFile(
                path=relative,
                sha256=hashlib.sha256(content).hexdigest(),
                byte_size=len(content),
                role=role,
            )
            for relative, (content, role) in sorted(manifest_files.items())
        ),
    )
    (tmp_path / "proposal-task-package.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), sort_keys=True),
        encoding="utf-8",
    )
    return environment_dir


def _output_contract() -> OutputCompletionContract:
    return OutputCompletionContract(
        schema_version="aecbench.output-completion-contract.v1",
        output_path="/workspace/output.md",
        format="markdown_final_fenced_json",
        required_top_level_keys=("decision",),
        require_single_final_json_block=True,
    )


def _output_contract_bytes() -> bytes:
    return (
        json.dumps(
            _output_contract().model_dump(mode="json"),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _runtime_archive(tmp_path: Path) -> Path:
    archive = tmp_path / "proposal-runtime.tar.gz"
    _write_runtime_archive(archive)
    return archive


def _write_runtime_archive(
    archive: Path,
    *,
    extra_members: tuple[str, ...] = (),
) -> None:
    with tarfile.open(archive, mode="w:gz") as bundle:
        for path in sorted(
            (
                "aec_bench/__init__.py",
                "aec_bench/harness/__init__.py",
                "aec_bench/harness/execution_entrypoint.py",
                "aec_bench/harness/execution_payload.py",
                "aec_bench/harness/provider_broker.py",
                "aec_bench/harness/provider_broker_bootstrap.py",
                "aec_bench/harness/provider_broker_runtime.py",
                *extra_members,
            )
        ):
            content = b"# ABOUTME: Test runtime package.\\n# ABOUTME: Contains no task sources.\\n"
            member = tarfile.TarInfo(path)
            member.size = len(content)
            member.mode = 0o644
            bundle.addfile(member, io.BytesIO(content))


def _runtime_content_sha256(archive_path: Path) -> str:
    digest = hashlib.sha256(b"aecbench.proposal-runtime-archive.v1\0")
    with tarfile.open(archive_path, mode="r:gz") as archive:
        for member in archive.getmembers():
            source = archive.extractfile(member)
            assert source is not None
            content = source.read()
            path = member.name.encode("utf-8")
            digest.update(len(path).to_bytes(8, byteorder="big"))
            digest.update(path)
            digest.update(len(content).to_bytes(8, byteorder="big"))
            digest.update(content)
    return digest.hexdigest()


def _run_reader_script(
    script: str,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", script, *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


@dataclass
class FakeSnapshot:
    id: str
    deleted: bool = False

    def delete(self) -> None:
        self.deleted = True


@dataclass
class FakeInstance:
    runtime_snapshot: FakeSnapshot
    id: str = "builder"
    stopped: bool = False
    snapshot_metadata: dict[str, str] | None = None

    def wait_until_ready(self) -> None:
        return None

    def snapshot(self, *, digest: str, metadata: dict[str, str], ttl_seconds: int) -> FakeSnapshot:
        assert len(digest) == 64
        assert ttl_seconds > 0
        self.snapshot_metadata = metadata
        return self.runtime_snapshot


@dataclass
class FakeSnapshots:
    build_snapshot: FakeSnapshot

    def create(self, **kwargs: Any) -> FakeSnapshot:
        assert kwargs["metadata"] == {"aec-bench-role": "runtime-build"}
        return self.build_snapshot


@dataclass
class FakeInstances:
    builder: FakeInstance

    def start(self, **kwargs: Any) -> FakeInstance:
        assert kwargs["snapshot_id"] == "snapshot-build"
        return self.builder


@dataclass
class FakeClient:
    build_snapshot: FakeSnapshot
    builder: FakeInstance

    @property
    def snapshots(self) -> FakeSnapshots:
        return FakeSnapshots(self.build_snapshot)

    @property
    def instances(self) -> FakeInstances:
        return FakeInstances(self.builder)


@dataclass(frozen=True)
class RecordingProposalMorphCloudOperations(ProposalMorphCloudOperations):
    events: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    written_files: list[tuple[str, bytes]] = field(default_factory=list)

    def _prepare_docker_host(self, instance: Any) -> None:
        self.events.append(f"prepare:{instance.id}")

    def _run_host_command(
        self,
        instance: Any,
        command: str,
        *,
        check: bool = True,
        command_timeout_seconds: int | None = None,
    ) -> MorphCommandResult:
        del check, command_timeout_seconds
        self.events.append(f"command:{instance.id}")
        self.commands.append(command)
        return MorphCommandResult(exit_code=0, stdout="", stderr="")

    def upload_directory(self, *, instance: Any, local_path: Path, remote_path: str) -> None:
        del instance
        self.events.append(f"upload:{local_path}:{remote_path}")

    def _upload_file_path(
        self,
        *,
        instance: Any,
        local_path: Path,
        remote_path: str,
        content: bytes,
    ) -> None:
        del instance
        assert content == local_path.read_bytes()
        self.events.append(f"upload-file:{local_path}:{remote_path}")

    def write_instance_file(self, *, instance: Any, remote_path: str, content: bytes) -> None:
        del instance
        self.written_files.append((remote_path, content))

    def stop_instance(self, *, instance: Any) -> None:
        instance.stopped = True
