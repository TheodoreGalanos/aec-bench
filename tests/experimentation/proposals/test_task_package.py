# ABOUTME: Proves derived proposal-session Harbor tasks contain no agent-visible task sources or gold assets.
# ABOUTME: Exercises deterministic identities, Harbor verifier isolation, mutation binding, and unsafe-input rejection.

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest
from harbor.models.task.task import Task as HarborTask  # type: ignore[import-untyped]
from harbor.models.trial.paths import TrialPaths  # type: ignore[import-untyped]
from harbor.verifier.verifier import Verifier  # type: ignore[import-untyped]

from aec_bench.contracts.evaluation_plane import (
    TaskVerifierFileInventoryEntry,
    TaskVerifierSurface,
    TaskVerifierSurfaceScope,
)
from aec_bench.contracts.harness_kernel import canonical_json_sha256
from aec_bench.contracts.output_completion import OutputCompletionContract
from aec_bench.contracts.task_definition import Visibility
from aec_bench.experimentation.proposals.task_package import (
    ProposalTaskPackageError,
    ProposalTaskPackageIdentity,
    assert_proposal_task_verifier_scope,
    assert_proposal_task_verifier_surface,
    build_proposal_task_package,
    project_proposal_task_verifier_surface,
    source_task_package_sha256,
    verify_proposal_task_build_context,
)
from tests.support.harbor_local_environment import LocalFilesystemHarborEnvironment

_PUBLIC_MARKER = b"PUBLIC-SOURCE-BYTES-MUST-NOT-CROSS"
_ORIGINAL_INSTRUCTION_MARKER = b"ORIGINAL-INSTRUCTION-DISCLOSES-sources/design.md"
_WORLD_MARKER = b"WORLD-GOLD-MUST-NOT-CROSS"
_GOLD_FIXTURE_MARKER = b"GOLD-FIXTURE-MUST-NOT-CROSS"
_HIDDEN_VERIFIER_MARKER = b"HIDDEN-VERIFIER-ONLY"


def test_builds_deterministic_source_free_harbor_task_package(tmp_path: Path) -> None:
    source_task = _source_task(tmp_path / "source-task")
    contract = _output_contract()
    identity = _identity(source_task, contract)

    first = build_proposal_task_package(
        source_task_dir=source_task,
        destination_task_dir=tmp_path / "derived-one",
        identity=identity,
        output_contract=contract,
        verifier_asset_paths=(
            "tests/test.sh",
            "tests/verify.py",
            "tests/instance.json",
        ),
    )
    second = build_proposal_task_package(
        source_task_dir=source_task,
        destination_task_dir=tmp_path / "derived-two",
        identity=identity,
        output_contract=contract,
        verifier_asset_paths=(
            "tests/instance.json",
            "tests/verify.py",
            "tests/test.sh",
        ),
    )

    assert first.manifest == second.manifest
    assert first.manifest.content_sha256 == second.manifest.content_sha256
    assert first.manifest.files == second.manifest.files
    assert _tree_payloads(first.path) == _tree_payloads(second.path)

    relative_paths = set(_tree_payloads(first.path))
    assert relative_paths == {
        "environment/.dockerignore",
        "environment/Dockerfile",
        "environment/output_contract.json",
        "instruction.md",
        "proposal-task-package.json",
        "task.toml",
        "tests/instance.json",
        "tests/test.sh",
        "tests/verify.py",
    }
    assert "environment/sources" not in relative_paths
    assert "world.json" not in relative_paths
    assert "tests/fixtures/golden_pass.md" not in relative_paths

    copied_bytes = b"\n".join(_tree_payloads(first.path).values())
    assert _PUBLIC_MARKER not in copied_bytes
    assert _ORIGINAL_INSTRUCTION_MARKER not in copied_bytes
    assert _WORLD_MARKER not in copied_bytes
    assert _GOLD_FIXTURE_MARKER not in copied_bytes
    assert _HIDDEN_VERIFIER_MARKER in copied_bytes

    build_context = _tree_payloads(first.path / "environment")
    assert set(build_context) == {
        ".dockerignore",
        "Dockerfile",
        "output_contract.json",
    }
    assert _HIDDEN_VERIFIER_MARKER not in b"\n".join(build_context.values())
    dockerfile = build_context["Dockerfile"].decode("utf-8")
    assert "\nCOPY " not in dockerfile
    assert "\nADD " not in dockerfile
    assert build_context[".dockerignore"] == b"*\n!Dockerfile\n"

    instruction = (first.path / "instruction.md").read_text(encoding="utf-8")
    assert instruction == (
        "Execute the governed proposal session supplied by the fixed kernel.\n"
        "Write the final artifact to /workspace/output.md.\n"
    )
    task_config = HarborTask(first.path).config
    assert task_config.metadata == {
        "category": "proposal-session",
        "difficulty": "medium",
        "tags": ["proposal-session", "source-free"],
        "visibility": "public",
    }
    assert not task_config.environment.mcp_servers

    stored_contract = OutputCompletionContract.model_validate_json(
        (first.path / "environment" / "output_contract.json").read_text(encoding="utf-8")
    )
    assert stored_contract == contract
    stored_manifest = type(first.manifest).model_validate_json(
        (first.path / "proposal-task-package.json").read_text(encoding="utf-8")
    )
    assert stored_manifest == first.manifest


def test_verifies_the_exact_manifest_bound_source_free_build_context(tmp_path: Path) -> None:
    source_task = _source_task(tmp_path / "source-task")
    contract = _output_contract()
    package = build_proposal_task_package(
        source_task_dir=source_task,
        destination_task_dir=tmp_path / "derived",
        identity=_identity(source_task, contract),
        output_contract=contract,
        verifier_asset_paths=("tests/test.sh",),
    )

    verified = verify_proposal_task_build_context(package.path / "environment")

    assert verified.manifest == package.manifest
    assert dict(verified.payloads) == _tree_payloads(package.path / "environment")
    assert len(verified.content_sha256) == 64


def test_build_context_verification_rejects_a_symbolic_link_member(tmp_path: Path) -> None:
    source_task = _source_task(tmp_path / "source-task")
    contract = _output_contract()
    package = build_proposal_task_package(
        source_task_dir=source_task,
        destination_task_dir=tmp_path / "derived",
        identity=_identity(source_task, contract),
        output_contract=contract,
        verifier_asset_paths=("tests/test.sh",),
    )
    dockerfile = package.path / "environment" / "Dockerfile"
    dockerfile.unlink()
    dockerfile.symlink_to(package.path / "instruction.md")

    with pytest.raises(ProposalTaskPackageError, match="symbolic link"):
        verify_proposal_task_build_context(package.path / "environment")


def test_harbor_uploads_hidden_verifier_only_after_agent_phase(tmp_path: Path) -> None:
    source_task = _source_task(tmp_path / "source-task")
    contract = _output_contract()
    package = build_proposal_task_package(
        source_task_dir=source_task,
        destination_task_dir=tmp_path / "derived",
        identity=_identity(source_task, contract),
        output_contract=contract,
        verifier_asset_paths=("tests/test.sh", "tests/instance.json"),
    )

    task = HarborTask(package.path)
    trial_paths = TrialPaths(trial_dir=tmp_path / "trial")
    trial_paths.mkdir()
    environment = LocalFilesystemHarborEnvironment(
        environment_dir=task.paths.environment_dir,
        environment_name="proposal-session",
        session_id="session-1",
        trial_paths=trial_paths,
        task_env_config=task.config.environment,
    )

    async def exercise_boundary() -> None:
        await environment.start(force_build=False)
        remote_root = trial_paths.trial_dir / "local-environment"
        assert not (remote_root / "tests").exists()
        assert _HIDDEN_VERIFIER_MARKER not in b"\n".join(
            path.read_bytes() for path in sorted((remote_root / "workspace").rglob("*")) if path.is_file()
        )

        result = await Verifier(
            task=task,
            trial_paths=trial_paths,
            environment=environment,
        ).verify()
        assert result.rewards == {"reward": 1.0}
        assert (remote_root / "tests" / "instance.json").read_bytes() == _HIDDEN_VERIFIER_MARKER + b"\n"
        await environment.stop(delete=True)

    asyncio.run(exercise_boundary())


def test_external_sealed_verifier_bundle_is_digest_bound_and_staged_post_agent(
    tmp_path: Path,
) -> None:
    source_task = _source_task(tmp_path / "source-task")
    sealed_task = tmp_path / "sealed-task"
    (sealed_task / "tests").mkdir(parents=True)
    sealed_instance = source_task / "tests" / "instance.json"
    (sealed_task / "tests" / "instance.json").write_bytes(sealed_instance.read_bytes())
    sealed_instance.unlink()
    (source_task / "world.json").unlink()
    for fixture in (source_task / "tests" / "fixtures").iterdir():
        fixture.unlink()
    (source_task / "tests" / "fixtures").rmdir()

    contract = _output_contract()
    sealed_sha256 = source_task_package_sha256(sealed_task)
    identity = _identity(source_task, contract).model_copy(update={"sealed_task_package_sha256": sealed_sha256})
    package = build_proposal_task_package(
        source_task_dir=source_task,
        sealed_task_dir=sealed_task,
        destination_task_dir=tmp_path / "derived",
        identity=identity,
        output_contract=contract,
        verifier_asset_paths=("tests/test.sh", "tests/verify.py"),
        sealed_verifier_asset_paths=("tests/instance.json",),
    )

    assert package.manifest.schema_version == "aecbench.proposal-task-package.v2"
    assert package.manifest.sealed_task_package_sha256 == sealed_sha256
    assert package.manifest.source_task_package_sha256 == source_task_package_sha256(source_task)
    by_path = {item.path: item for item in package.manifest.files}
    assert by_path["tests/instance.json"].role == "sealed_verifier_only"
    assert by_path["tests/test.sh"].role == "verifier_only"
    assert (package.path / "tests" / "instance.json").read_bytes() == (_HIDDEN_VERIFIER_MARKER + b"\n")
    assert not (source_task / "tests" / "instance.json").exists()

    task = HarborTask(package.path)
    trial_paths = TrialPaths(trial_dir=tmp_path / "trial")
    trial_paths.mkdir()
    environment = LocalFilesystemHarborEnvironment(
        environment_dir=task.paths.environment_dir,
        environment_name="proposal-session",
        session_id="sealed-session",
        trial_paths=trial_paths,
        task_env_config=task.config.environment,
    )

    async def exercise_boundary() -> None:
        await environment.start(force_build=False)
        remote_root = trial_paths.trial_dir / "local-environment"
        assert not (remote_root / "tests").exists()
        result = await Verifier(
            task=task,
            trial_paths=trial_paths,
            environment=environment,
        ).verify()
        assert result.rewards == {"reward": 1.0}
        assert (remote_root / "tests" / "instance.json").read_bytes() == (_HIDDEN_VERIFIER_MARKER + b"\n")
        await environment.stop(delete=True)

    asyncio.run(exercise_boundary())


def test_projects_and_checks_exact_task_verifier_surfaces_and_multi_task_scope(
    tmp_path: Path,
) -> None:
    source_task = _source_task(tmp_path / "source-task")
    sealed_task = tmp_path / "sealed-task"
    (sealed_task / "tests").mkdir(parents=True)
    (sealed_task / "tests" / "instance.json").write_bytes(_HIDDEN_VERIFIER_MARKER + b"\n")
    contract = _output_contract()
    package = build_proposal_task_package(
        source_task_dir=source_task,
        sealed_task_dir=sealed_task,
        destination_task_dir=tmp_path / "derived",
        identity=_identity(source_task, contract).model_copy(
            update={
                "sealed_task_package_sha256": source_task_package_sha256(
                    sealed_task,
                ),
            }
        ),
        output_contract=contract,
        verifier_asset_paths=("tests/test.sh", "tests/verify.py"),
        sealed_verifier_asset_paths=("tests/instance.json",),
    )

    surface = project_proposal_task_verifier_surface(package.manifest)

    assert {item.role for item in surface.files} == {
        "verifier_only",
        "sealed_verifier_only",
    }
    assert {item.path for item in surface.files} == {
        "tests/instance.json",
        "tests/test.sh",
        "tests/verify.py",
    }
    assert_proposal_task_verifier_surface(
        manifest=package.manifest,
        expected_surface=surface,
    )

    changed_file = TaskVerifierFileInventoryEntry(
        **{
            **surface.files[0].model_dump(mode="python"),
            "sha256": _sha256(b"different-verifier-bytes"),
        }
    )
    wrong_surface = TaskVerifierSurface(
        **{
            **surface.model_dump(
                mode="python",
                exclude={"content_sha256", "files"},
            ),
            "files": (changed_file, *surface.files[1:]),
        }
    )
    with pytest.raises(ProposalTaskPackageError, match="verifier surface"):
        assert_proposal_task_verifier_surface(
            manifest=package.manifest,
            expected_surface=wrong_surface,
        )

    second_manifest = type(package.manifest).model_validate(
        {
            **package.manifest.model_dump(
                mode="python",
                exclude={"content_sha256"},
            ),
            "task_id": "civil/proposal-session/source-free-second",
            "task_revision": _sha256(b"second-task-revision"),
        }
    )
    second_surface = project_proposal_task_verifier_surface(second_manifest)
    scope = TaskVerifierSurfaceScope(
        scope_id="task-verifiers.two-task-pilot",
        task_surfaces=(second_surface, surface),
    )

    checked = assert_proposal_task_verifier_scope(
        manifests=(
            package.manifest,
            second_manifest,
            package.manifest,
            second_manifest,
        ),
        expected_scope=scope,
    )

    assert checked == scope
    with pytest.raises(ProposalTaskPackageError, match="verifier scope"):
        assert_proposal_task_verifier_scope(
            manifests=(package.manifest,),
            expected_scope=scope,
        )


def test_external_sealed_verifier_bundle_drift_fails_before_publication(
    tmp_path: Path,
) -> None:
    source_task = _source_task(tmp_path / "source-task")
    sealed_task = tmp_path / "sealed-task"
    (sealed_task / "tests").mkdir(parents=True)
    (sealed_task / "tests" / "instance.json").write_bytes(_HIDDEN_VERIFIER_MARKER + b"\n")
    contract = _output_contract()
    identity = _identity(source_task, contract).model_copy(
        update={
            "sealed_task_package_sha256": source_task_package_sha256(sealed_task),
        }
    )
    (sealed_task / "tests" / "instance.json").write_bytes(b"tampered\n")

    destination = tmp_path / "derived"
    with pytest.raises(
        ProposalTaskPackageError,
        match="sealed task package identity changed",
    ):
        build_proposal_task_package(
            source_task_dir=source_task,
            sealed_task_dir=sealed_task,
            destination_task_dir=destination,
            identity=identity,
            output_contract=contract,
            verifier_asset_paths=("tests/test.sh",),
            sealed_verifier_asset_paths=("tests/instance.json",),
        )

    assert not destination.exists()


def test_excluded_source_mutation_changes_only_the_governed_package_identity(tmp_path: Path) -> None:
    source_task = _source_task(tmp_path / "source-task")
    contract = _output_contract()
    first = build_proposal_task_package(
        source_task_dir=source_task,
        destination_task_dir=tmp_path / "derived-one",
        identity=_identity(source_task, contract),
        output_contract=contract,
        verifier_asset_paths=("tests/test.sh",),
    )

    (source_task / "environment" / "sources" / "design.md").write_bytes(_PUBLIC_MARKER + b"-MUTATED\n")
    second = build_proposal_task_package(
        source_task_dir=source_task,
        destination_task_dir=tmp_path / "derived-two",
        identity=_identity(source_task, contract),
        output_contract=contract,
        verifier_asset_paths=("tests/test.sh",),
    )

    first_payloads = _tree_payloads(first.path)
    second_payloads = _tree_payloads(second.path)
    first_payloads.pop("proposal-task-package.json")
    second_payloads.pop("proposal-task-package.json")
    assert first_payloads == second_payloads
    assert first.manifest.source_task_package_sha256 != second.manifest.source_task_package_sha256
    assert first.manifest.content_sha256 != second.manifest.content_sha256


@pytest.mark.parametrize(
    "unsafe_input",
    (
        "source_symlink",
        "verifier_traversal",
        "gold_asset",
        "meta_harness_asset",
        "task_identity_mismatch",
        "output_contract_mismatch",
        "existing_destination",
    ),
)
def test_unsafe_input_fails_without_publishing_a_partial_package(
    tmp_path: Path,
    unsafe_input: str,
) -> None:
    source_task = _source_task(tmp_path / "source-task")
    contract = _output_contract()
    identity = _identity(source_task, contract)
    destination = tmp_path / "derived"
    verifier_assets = ("tests/test.sh",)

    if unsafe_input == "source_symlink":
        (source_task / "environment" / "source-link.md").symlink_to(
            source_task / "environment" / "sources" / "design.md"
        )
    elif unsafe_input == "verifier_traversal":
        verifier_assets = ("tests/test.sh", "../instruction.md")
    elif unsafe_input == "gold_asset":
        verifier_assets = ("tests/test.sh", "tests/fixtures/golden_pass.md")
    elif unsafe_input == "meta_harness_asset":
        verifier_assets = ("tests/test.sh", "tests/meta_harness.py")
    elif unsafe_input == "task_identity_mismatch":
        identity = identity.model_copy(update={"source_task_package_sha256": _sha256(b"different-task")})
    elif unsafe_input == "output_contract_mismatch":
        identity = identity.model_copy(update={"output_contract_sha256": _sha256(b"different-contract")})
    elif unsafe_input == "existing_destination":
        destination.mkdir()

    with pytest.raises(ProposalTaskPackageError):
        build_proposal_task_package(
            source_task_dir=source_task,
            destination_task_dir=destination,
            identity=identity,
            output_contract=contract,
            verifier_asset_paths=verifier_assets,
        )

    if unsafe_input != "existing_destination":
        assert not destination.exists()


def _source_task(task_dir: Path) -> Path:
    (task_dir / "environment" / "sources").mkdir(parents=True)
    (task_dir / "tests" / "fixtures").mkdir(parents=True)
    (task_dir / "task.toml").write_text(
        """
version = "1.0"

[metadata]
difficulty = "hard"
category = "original-category"
tags = ["original-source-path"]

[agent]
timeout_sec = 321

[verifier]
timeout_sec = 123

[environment]
build_timeout_sec = 456
cpus = 2
memory_mb = 3072
storage_mb = 6144
network_mode = "public"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (task_dir / "instruction.md").write_bytes(_ORIGINAL_INSTRUCTION_MARKER + b"\n")
    (task_dir / "environment" / "Dockerfile").write_text(
        "FROM python:3.13-slim\nCOPY sources/design.md /workspace/sources/design.md\n",
        encoding="utf-8",
    )
    (task_dir / "environment" / "sources" / "design.md").write_bytes(_PUBLIC_MARKER + b"\n")
    (task_dir / "environment" / "output_contract.json").write_text(
        json.dumps(_output_contract().model_dump(mode="json"), sort_keys=True),
        encoding="utf-8",
    )
    (task_dir / "tests" / "test.sh").write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        'SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"\n'
        f'grep -q {_HIDDEN_VERIFIER_MARKER.decode("ascii")} "$SCRIPT_DIR/instance.json"\n'
        'REWARD_PATH="${AEC_BENCH_REWARD_PATH:-/logs/verifier/reward.json}"\n'
        'mkdir -p "$(dirname -- "$REWARD_PATH")"\n'
        'printf \'{"reward": 1.0}\\n\' > "$REWARD_PATH"\n',
        encoding="utf-8",
    )
    (task_dir / "tests" / "verify.py").write_text(
        "# ABOUTME: Supplies a verifier fixture for proposal task-package tests.\n"
        "# ABOUTME: Remains host-hidden until Harbor starts verification.\n",
        encoding="utf-8",
    )
    (task_dir / "tests" / "instance.json").write_bytes(_HIDDEN_VERIFIER_MARKER + b"\n")
    (task_dir / "tests" / "meta_harness.py").write_text(
        "PRIVILEGED = True\n",
        encoding="utf-8",
    )
    (task_dir / "tests" / "fixtures" / "golden_pass.md").write_bytes(_GOLD_FIXTURE_MARKER + b"\n")
    (task_dir / "world.json").write_bytes(_WORLD_MARKER + b"\n")
    return task_dir


def _output_contract() -> OutputCompletionContract:
    return OutputCompletionContract(
        schema_version="aecbench.output-completion-contract.v1",
        output_path="/workspace/output.md",
        format="markdown_final_fenced_json",
        required_top_level_keys=("decision",),
        require_single_final_json_block=True,
    )


def _identity(
    source_task: Path,
    contract: OutputCompletionContract,
) -> ProposalTaskPackageIdentity:
    return ProposalTaskPackageIdentity(
        task_id="civil/proposal-session/source-free",
        task_revision=_sha256(b"task-revision"),
        source_task_package_sha256=source_task_package_sha256(source_task),
        problem_view_sha256=_sha256(b"problem-view"),
        output_contract_sha256=canonical_json_sha256(contract.model_dump(mode="json")),
        visibility=Visibility.PUBLIC,
    )


def _tree_payloads(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
