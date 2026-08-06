# ABOUTME: Tests execution of an exact host-authorized proposal Harbor dispatch.
# ABOUTME: Proves canonical config use, immutable attempt evidence, and duplicate-run prevention.

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import yaml

from aec_bench.contracts.authority import AuthorityAction, BasisKind
from aec_bench.meta_harness.authority_ledger import AuthorityLedger
from aec_bench.meta_harness.proposal_dispatch import (
    GovernedProposalDispatchAuthorization,
    ProposalDispatchGovernanceError,
)
from aec_bench.meta_harness.proposal_harbor_runtime import (
    ProposalHarborExecutionStatus,
    ProposalProviderOperationCoordinate,
    ProposalProviderOperationStart,
    ProposalProviderOperationTerminal,
    load_proposal_harbor_execution,
    run_governed_proposal_harbor,
)
from tests.meta_harness.test_proposal_dispatch_governance import (
    _authorize,
    _dispatch_fixture,
)


@dataclass
class _RecordingHarborExecutor:
    exit_code: int = 0
    create_job: bool = True
    calls: list[tuple[tuple[str, ...], Path]] = field(default_factory=list)

    def execute(self, *, command: list[str], cwd: Path) -> int:
        self.calls.append((tuple(command), cwd))
        if self.create_job:
            trial_dir = cwd / "jobs" / "proposal" / "job.001" / "trial.001"
            trial_dir.mkdir(parents=True)
            (trial_dir / "result.json").write_text(
                json.dumps({"trial_name": "trial.001"}),
                encoding="utf-8",
            )
        return self.exit_code


@dataclass
class _InterruptedHarborExecutor:
    calls: int = 0

    def execute(self, *, command: list[str], cwd: Path) -> int:
        del command, cwd
        self.calls += 1
        raise KeyboardInterrupt


def test_runs_only_the_authorized_canonical_job_and_replays_without_redispatch(
    tmp_path: Path,
) -> None:
    fixture = _dispatch_fixture(tmp_path / "fixture")
    authorization = _authorize(fixture)
    executor = _RecordingHarborExecutor()

    result = run_governed_proposal_harbor(
        ledger=fixture.ledger,
        authorization=authorization,
        project_root=tmp_path,
        jobs_root=tmp_path / "jobs" / "proposal",
        artifacts_root=tmp_path / "artifacts",
        executor=executor,
    )

    assert result.receipt.status is ProposalHarborExecutionStatus.COMPLETED
    assert result.receipt.trial_record_import_permitted is True
    assert result.receipt.dispatch_sha256 == authorization.dispatch.content_sha256
    assert result.receipt.provider_dispatch_event_sha256 == (authorization.provider_dispatch_event.content_sha256)
    assert result.receipt.result_paths == ("trial.001/result.json",)
    assert result.receipt.job_dir == str(
        (tmp_path / "jobs" / "proposal" / "job.001").resolve(),
    )
    assert result.receipt.finished_at >= result.receipt.started_at
    assert result.receipt.total_seconds >= 0
    assert result.replayed is False
    assert len(executor.calls) == 1
    command, cwd = executor.calls[0]
    assert command[:4] == ("uv", "run", "harbor", "run")
    assert command[4] == "-c"
    assert cwd == tmp_path.resolve()
    config_path = Path(command[5])
    assert yaml.safe_load(config_path.read_text(encoding="utf-8")) == json.loads(
        authorization.dispatch.harbor_job_config_json,
    )

    replay_executor = _RecordingHarborExecutor()
    replayed = run_governed_proposal_harbor(
        ledger=AuthorityLedger(fixture.ledger.root),
        authorization=authorization,
        project_root=tmp_path,
        jobs_root=tmp_path / "jobs" / "proposal",
        artifacts_root=tmp_path / "artifacts",
        executor=replay_executor,
    )

    assert replayed.receipt == result.receipt
    assert replayed.replayed is True
    assert replay_executor.calls == []
    assert (
        load_proposal_harbor_execution(
            receipt_path=result.receipt_path,
            ledger=AuthorityLedger(fixture.ledger.root),
            authorization=authorization,
        )
        == result.receipt
    )


def test_fresh_ledger_replays_completed_dispatch_across_artifact_roots(
    tmp_path: Path,
) -> None:
    fixture = _dispatch_fixture(tmp_path / "fixture")
    authorization = _authorize(fixture)
    first = run_governed_proposal_harbor(
        ledger=fixture.ledger,
        authorization=authorization,
        project_root=tmp_path,
        jobs_root=tmp_path / "jobs" / "proposal",
        artifacts_root=tmp_path / "artifacts-a",
        executor=_RecordingHarborExecutor(),
    )
    replay_executor = _RecordingHarborExecutor()

    replayed = run_governed_proposal_harbor(
        ledger=AuthorityLedger(fixture.ledger.root),
        authorization=authorization,
        project_root=tmp_path,
        jobs_root=tmp_path / "jobs" / "proposal",
        artifacts_root=tmp_path / "artifacts-b",
        executor=replay_executor,
    )

    assert replayed.receipt == first.receipt
    assert replayed.receipt_path == first.receipt_path
    assert replayed.replayed is True
    assert replay_executor.calls == []
    assert not (tmp_path / "artifacts-b").exists()
    coordinate = _operation_coordinate(authorization)
    start_basis = fixture.ledger.basis_for_id(
        kind=BasisKind.EVIDENCE,
        artifact_id=f"proposal-provider-operation.{coordinate.content_sha256}.start",
    )
    terminal_basis = fixture.ledger.basis_for_id(
        kind=BasisKind.EVIDENCE,
        artifact_id=f"proposal-provider-operation.{coordinate.content_sha256}.terminal",
    )
    assert start_basis is not None
    assert terminal_basis is not None
    start = ProposalProviderOperationStart.model_validate_json(
        start_basis.content_path.read_bytes(),
    )
    terminal = ProposalProviderOperationTerminal.model_validate_json(
        terminal_basis.content_path.read_bytes(),
    )
    assert start.coordinate == coordinate
    assert terminal.coordinate == coordinate
    assert terminal.start_sha256 == start.content_sha256
    assert terminal.receipt_path == str(first.receipt_path)


def test_fresh_ledger_replays_failed_dispatch_across_artifact_roots(
    tmp_path: Path,
) -> None:
    fixture = _dispatch_fixture(tmp_path / "fixture")
    authorization = _authorize(fixture)
    first = run_governed_proposal_harbor(
        ledger=fixture.ledger,
        authorization=authorization,
        project_root=tmp_path,
        jobs_root=tmp_path / "jobs" / "proposal",
        artifacts_root=tmp_path / "artifacts-a",
        executor=_RecordingHarborExecutor(exit_code=7),
    )
    replay_executor = _RecordingHarborExecutor()

    replayed = run_governed_proposal_harbor(
        ledger=AuthorityLedger(fixture.ledger.root),
        authorization=authorization,
        project_root=tmp_path,
        jobs_root=tmp_path / "jobs" / "proposal",
        artifacts_root=tmp_path / "artifacts-b",
        executor=replay_executor,
    )

    assert first.receipt.status is ProposalHarborExecutionStatus.FAILED
    assert replayed.receipt == first.receipt
    assert replayed.receipt_path == first.receipt_path
    assert replayed.replayed is True
    assert replay_executor.calls == []
    assert not (tmp_path / "artifacts-b").exists()


def test_interrupted_dispatch_is_consumed_globally_before_executor_and_cannot_redispatch(
    tmp_path: Path,
) -> None:
    fixture = _dispatch_fixture(tmp_path / "fixture")
    authorization = _authorize(fixture)
    interrupted = _InterruptedHarborExecutor()
    with pytest.raises(KeyboardInterrupt):
        run_governed_proposal_harbor(
            ledger=fixture.ledger,
            authorization=authorization,
            project_root=tmp_path,
            jobs_root=tmp_path / "jobs" / "proposal",
            artifacts_root=tmp_path / "artifacts-a",
            executor=interrupted,
        )
    replay_executor = _RecordingHarborExecutor()

    with pytest.raises(ValueError, match="incomplete prior attempt"):
        run_governed_proposal_harbor(
            ledger=AuthorityLedger(fixture.ledger.root),
            authorization=authorization,
            project_root=tmp_path,
            jobs_root=tmp_path / "jobs" / "proposal",
            artifacts_root=tmp_path / "artifacts-b",
            executor=replay_executor,
        )

    assert interrupted.calls == 1
    assert replay_executor.calls == []
    assert not (tmp_path / "artifacts-b").exists()
    coordinate = _operation_coordinate(authorization)
    assert (
        fixture.ledger.basis_for_id(
            kind=BasisKind.EVIDENCE,
            artifact_id=f"proposal-provider-operation.{coordinate.content_sha256}.start",
        )
        is not None
    )
    assert (
        fixture.ledger.basis_for_id(
            kind=BasisKind.EVIDENCE,
            artifact_id=f"proposal-provider-operation.{coordinate.content_sha256}.terminal",
        )
        is None
    )


def test_fails_before_executor_when_dispatch_authority_is_no_longer_replayable(
    tmp_path: Path,
) -> None:
    fixture = _dispatch_fixture(tmp_path / "fixture")
    authorization = _authorize(fixture)
    executor = _RecordingHarborExecutor()
    inherited = fixture.ledger.resolve_basis(
        fixture.governed_freeze.basis.problem_view,
    )
    inherited.origin_path.unlink()

    with pytest.raises(
        ProposalDispatchGovernanceError,
        match="origin closure",
    ):
        run_governed_proposal_harbor(
            ledger=AuthorityLedger(fixture.ledger.root),
            authorization=authorization,
            project_root=tmp_path,
            jobs_root=tmp_path / "jobs" / "proposal",
            artifacts_root=tmp_path / "artifacts",
            executor=executor,
        )

    assert executor.calls == []
    assert not (tmp_path / "artifacts").exists()


@pytest.mark.parametrize(
    ("executor", "failure_code"),
    (
        (_RecordingHarborExecutor(exit_code=7), "harbor_exit_nonzero"),
        (_RecordingHarborExecutor(create_job=False), "job_directory_missing"),
    ),
)
def test_persists_failed_attempt_without_granting_import(
    tmp_path: Path,
    executor: _RecordingHarborExecutor,
    failure_code: str,
) -> None:
    fixture = _dispatch_fixture(tmp_path / "fixture")
    authorization = _authorize(fixture)

    result = run_governed_proposal_harbor(
        ledger=fixture.ledger,
        authorization=authorization,
        project_root=tmp_path,
        jobs_root=tmp_path / "jobs" / "proposal",
        artifacts_root=tmp_path / "artifacts",
        executor=executor,
    )

    assert result.receipt.status is ProposalHarborExecutionStatus.FAILED
    assert result.receipt.failure_code == failure_code
    assert result.receipt.trial_record_import_permitted is False
    assert result.receipt.provider_dispatch_event_sha256 == (authorization.provider_dispatch_event.content_sha256)
    assert authorization.provider_dispatch_event.action is AuthorityAction.PROVIDER_DISPATCH


def test_rejects_jobs_root_that_differs_from_authorized_job_config(
    tmp_path: Path,
) -> None:
    fixture = _dispatch_fixture(tmp_path / "fixture")
    authorization = _authorize(fixture)
    executor = _RecordingHarborExecutor()

    with pytest.raises(ValueError, match="jobs root"):
        run_governed_proposal_harbor(
            ledger=fixture.ledger,
            authorization=authorization,
            project_root=tmp_path,
            jobs_root=tmp_path / "other-jobs",
            artifacts_root=tmp_path / "artifacts",
            executor=executor,
        )

    assert executor.calls == []


@pytest.mark.parametrize("target", ("config", "job"))
def test_replay_rejects_config_or_job_evidence_tamper(
    tmp_path: Path,
    target: str,
) -> None:
    fixture = _dispatch_fixture(tmp_path / "fixture")
    authorization = _authorize(fixture)
    result = run_governed_proposal_harbor(
        ledger=fixture.ledger,
        authorization=authorization,
        project_root=tmp_path,
        jobs_root=tmp_path / "jobs" / "proposal",
        artifacts_root=tmp_path / "artifacts",
        executor=_RecordingHarborExecutor(),
    )
    if target == "config":
        Path(result.receipt.config_path).write_text(
            "jobs_dir: changed\n",
            encoding="utf-8",
        )
    else:
        assert result.receipt.job_dir is not None
        (Path(result.receipt.job_dir) / "trial.001" / "result.json").write_text(
            '{"trial_name":"changed"}',
            encoding="utf-8",
        )

    with pytest.raises(ValueError, match="changed|differs"):
        load_proposal_harbor_execution(
            receipt_path=result.receipt_path,
            ledger=AuthorityLedger(fixture.ledger.root),
            authorization=authorization,
        )


def _operation_coordinate(
    authorization: GovernedProposalDispatchAuthorization,
) -> ProposalProviderOperationCoordinate:
    return ProposalProviderOperationCoordinate(
        dispatch_id=authorization.dispatch.dispatch_id,
        dispatch_sha256=authorization.dispatch.content_sha256,
        provider_dispatch_event_id=authorization.provider_dispatch_event.event_id,
        provider_dispatch_event_sha256=(authorization.provider_dispatch_event.content_sha256),
    )
