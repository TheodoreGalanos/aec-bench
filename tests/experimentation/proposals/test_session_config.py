# ABOUTME: Tests host-only proposal-session inputs before EntrypointAgent touches a sandbox.
# ABOUTME: Proves exact bundle, source task, derived task, and filtered runtime identities.

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from aec_bench.contracts.output_completion import OutputCompletionContract
from aec_bench.contracts.program_proposal.study import MatchedEvaluationCoordinate
from aec_bench.contracts.proposal_execution.compilation import ProposalCompilationRejection
from aec_bench.contracts.task_definition import Visibility
from aec_bench.experimentation.proposals.program_compilation import (
    ProposalRunSessionBundle,
    compile_governed_proposal,
)
from aec_bench.experimentation.proposals.runtime_archive import build_proposal_runtime_archive
from aec_bench.experimentation.proposals.session_config import (
    ProposalSessionHostConfig,
    ProposalSessionHostConfigError,
    load_proposal_session_host_inputs,
)
from aec_bench.experimentation.proposals.task_package import (
    ProposalTaskPackageIdentity,
    build_proposal_task_package,
    source_task_package_sha256,
)
from tests.experimentation.proposals.test_program_compilation import (
    _compile_arguments,
    _governed_graph_fixture,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PACKAGE_ROOT = _PROJECT_ROOT / "src" / "aec_bench"


def test_loads_exact_host_inputs_without_serializing_source_bytes(
    tmp_path: Path,
) -> None:
    config, expected_bundle, derived_task = _host_fixture(tmp_path)

    loaded = load_proposal_session_host_inputs(
        config.model_dump(mode="json"),
        environment_dir=derived_task / "environment",
    )

    assert loaded.config == config
    assert loaded.bundle == expected_bundle
    assert loaded.source_task_dir.is_dir()
    assert loaded.derived_task_manifest.source_task_package_sha256 == config.source_task_package_sha256
    assert loaded.runtime_archive.archive_sha256 == config.runtime_archive_sha256
    assert loaded.config.evaluation_coordinate.seed == 1701
    assert loaded.config.evaluation_coordinate.repetition == 2
    assert loaded.config.execution_schedule_sha256 == _sha256(b"execution-schedule")
    assert loaded.config.execution_assignment_sha256 == _sha256(b"execution-assignment")
    assert str(loaded.source_task_dir) not in expected_bundle.model_dump_json()
    assert str(loaded.runtime_archive.path) not in expected_bundle.model_dump_json()


def test_rejects_bundle_bytes_changed_after_dispatch_configuration(
    tmp_path: Path,
) -> None:
    config, _bundle, derived_task = _host_fixture(tmp_path)
    Path(config.bundle_path).write_bytes(Path(config.bundle_path).read_bytes() + b"\n")

    with pytest.raises(ProposalSessionHostConfigError, match="bundle file SHA-256"):
        load_proposal_session_host_inputs(
            config.model_dump(mode="json"),
            environment_dir=derived_task / "environment",
        )


def test_rejects_symbolic_link_at_bundle_admission_boundary(
    tmp_path: Path,
) -> None:
    config, _bundle, derived_task = _host_fixture(tmp_path)
    bundle_path = Path(config.bundle_path)
    target_path = bundle_path.with_name("proposal-session-bundle-target.json")
    bundle_path.rename(target_path)
    bundle_path.symlink_to(target_path)

    with pytest.raises(
        ProposalSessionHostConfigError,
        match="proposal session bundle must not be a symbolic link",
    ):
        load_proposal_session_host_inputs(
            config.model_dump(mode="json"),
            environment_dir=derived_task / "environment",
        )


def test_rejects_bundle_larger_than_admission_limit(
    tmp_path: Path,
) -> None:
    config, _bundle, derived_task = _host_fixture(tmp_path)
    with Path(config.bundle_path).open("wb") as handle:
        handle.truncate((64 * 1024 * 1024) + 1)

    with pytest.raises(
        ProposalSessionHostConfigError,
        match="proposal session bundle exceeds its byte limit",
    ):
        load_proposal_session_host_inputs(
            config.model_dump(mode="json"),
            environment_dir=derived_task / "environment",
        )


def test_rejects_bundle_fault_before_later_host_input_faults(
    tmp_path: Path,
) -> None:
    config, _bundle, derived_task = _host_fixture(tmp_path)
    Path(config.bundle_path).write_bytes(Path(config.bundle_path).read_bytes() + b"\n")
    invalid_later_inputs = config.model_copy(
        update={
            "source_task_dir": str((tmp_path / "missing-source").resolve()),
            "runtime_archive_path": str((tmp_path / "missing-runtime.tar.gz").resolve()),
        },
    )

    with pytest.raises(
        ProposalSessionHostConfigError,
        match="bundle file SHA-256",
    ):
        load_proposal_session_host_inputs(
            invalid_later_inputs.model_dump(mode="json"),
            environment_dir=derived_task / "missing-environment",
        )


def test_rejects_coordinate_fault_before_source_environment_and_runtime_faults(
    tmp_path: Path,
) -> None:
    config, _bundle, derived_task = _host_fixture(tmp_path)
    wrong_coordinate = MatchedEvaluationCoordinate.model_validate(
        {
            **config.evaluation_coordinate.model_dump(
                mode="python",
                exclude={"content_sha256"},
            ),
            "task_revision": "f" * 64,
        },
    )
    invalid_later_inputs = config.model_copy(
        update={
            "source_task_dir": str((tmp_path / "missing-source").resolve()),
            "runtime_archive_path": str((tmp_path / "missing-runtime.tar.gz").resolve()),
            "evaluation_coordinate": wrong_coordinate,
        },
    )

    with pytest.raises(
        ProposalSessionHostConfigError,
        match="evaluation coordinate",
    ):
        load_proposal_session_host_inputs(
            invalid_later_inputs.model_dump(mode="json"),
            environment_dir=derived_task / "missing-environment",
        )


def test_rejects_runtime_archive_changed_after_dispatch_configuration(
    tmp_path: Path,
) -> None:
    config, _bundle, derived_task = _host_fixture(tmp_path)
    Path(config.runtime_archive_path).write_bytes(Path(config.runtime_archive_path).read_bytes() + b"tamper")

    with pytest.raises(
        ProposalSessionHostConfigError,
        match="compressed SHA-256",
    ):
        load_proposal_session_host_inputs(
            config.model_dump(mode="json"),
            environment_dir=derived_task / "environment",
        )


def test_rejects_derived_task_manifest_from_another_source_package(
    tmp_path: Path,
) -> None:
    config, _bundle, derived_task = _host_fixture(tmp_path)
    manifest_path = derived_task / "proposal-task-package.json"
    payload = manifest_path.read_text(encoding="utf-8").replace(
        config.source_task_package_sha256,
        "f" * 64,
    )
    manifest_path.write_text(payload, encoding="utf-8")

    with pytest.raises(
        ProposalSessionHostConfigError,
        match="derived task package",
    ):
        load_proposal_session_host_inputs(
            config.model_dump(mode="json"),
            environment_dir=derived_task / "environment",
        )


def test_rejects_evaluation_coordinate_from_another_task_revision(
    tmp_path: Path,
) -> None:
    config, _bundle, derived_task = _host_fixture(tmp_path)
    wrong_coordinate = MatchedEvaluationCoordinate.model_validate(
        {
            **config.evaluation_coordinate.model_dump(
                mode="python",
                exclude={"content_sha256"},
            ),
            "task_revision": "f" * 64,
        },
    )

    with pytest.raises(
        ProposalSessionHostConfigError,
        match="evaluation coordinate",
    ):
        load_proposal_session_host_inputs(
            config.model_copy(
                update={"evaluation_coordinate": wrong_coordinate},
            ).model_dump(mode="json"),
            environment_dir=derived_task / "environment",
        )


def _host_fixture(
    tmp_path: Path,
) -> tuple[ProposalSessionHostConfig, ProposalRunSessionBundle, Path]:
    fixture, governed, _graph = _governed_graph_fixture(
        tmp_path / "governed",
        shape="serial",
    )
    compiled = compile_governed_proposal(
        **_compile_arguments(fixture, governed),
    )
    assert not isinstance(compiled, ProposalCompilationRejection)
    bundle_path = tmp_path / "proposal-session-bundle.json"
    bundle_path.write_text(compiled.model_dump_json(), encoding="utf-8")

    runtime_archive = build_proposal_runtime_archive(
        package_root=_PACKAGE_ROOT,
        archive_path=tmp_path / "proposal-runtime.tar.gz",
    )
    source_task_dir = fixture.ledger.root.parent / "tasks" / compiled.task_snapshot.task_id
    source_package_sha256 = source_task_package_sha256(source_task_dir)
    output_contract = OutputCompletionContract.model_validate(
        compiled.compilation.proposal_freeze.problem_view.output_contract
    )
    derived = build_proposal_task_package(
        source_task_dir=source_task_dir,
        destination_task_dir=tmp_path / "derived-task",
        identity=ProposalTaskPackageIdentity(
            task_id=compiled.task_snapshot.task_id,
            task_revision=compiled.task_snapshot.commitment_sha256,
            source_task_package_sha256=source_package_sha256,
            problem_view_sha256=(compiled.compilation.proposal_freeze.problem_view.content_sha256),
            output_contract_sha256=(compiled.compilation.proposal_graph.finalizer.output_completion_contract_sha256),
            visibility=Visibility.PUBLIC,
        ),
        output_contract=output_contract,
        verifier_asset_paths=("tests/test.sh",),
    )
    evaluation_coordinate = MatchedEvaluationCoordinate(
        coordinate_id="evaluation.proposal-session-config.2",
        task_id=compiled.task_snapshot.task_id,
        task_revision=compiled.task_snapshot.commitment_sha256,
        split=compiled.compilation.proposal_freeze.split,
        review_lineage_id=(compiled.compilation.proposal_freeze.selected_review_lineage_id),
        seed=1701,
        repetition=2,
    )
    return (
        ProposalSessionHostConfig(
            bundle_path=str(bundle_path.resolve()),
            bundle_file_sha256=_sha256(bundle_path.read_bytes()),
            bundle_content_sha256=compiled.content_sha256,
            source_task_dir=str(source_task_dir.resolve()),
            source_task_package_sha256=source_package_sha256,
            runtime_archive_path=str(runtime_archive.path.resolve()),
            runtime_archive_sha256=runtime_archive.archive_sha256,
            runtime_archive_content_sha256=runtime_archive.content_sha256,
            evaluation_coordinate=evaluation_coordinate,
            execution_schedule_sha256=_sha256(b"execution-schedule"),
            execution_assignment_sha256=_sha256(b"execution-assignment"),
        ),
        compiled,
        derived.path,
    )


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
