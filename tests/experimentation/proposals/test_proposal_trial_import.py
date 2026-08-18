# ABOUTME: Tests finalization of one proposal Harbor execution into scored evidence.
# ABOUTME: Covers complete TrialRecord lineage, candidate failures, drift, and fresh-ledger replay.

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path

import pytest

from aec_bench.contracts.authority import AuthorityAction, AuthorityEvent
from aec_bench.contracts.commitments import canonical_json_sha256
from aec_bench.contracts.program_proposal.types import OptimizationSplit, ProgramCandidateKind
from aec_bench.contracts.proposal_execution.session import ProposalSessionReceipt
from aec_bench.contracts.trial_record import Completeness, TrialRecord
from aec_bench.experimentation.governance.authority_ledger import AuthorityLedger
from aec_bench.experimentation.proposals.harbor_import.api import (
    load_proposal_harbor_import_evidence,
)
from aec_bench.experimentation.proposals.proposal_dispatch import (
    GovernedProposalDispatchAuthorization,
)
from aec_bench.experimentation.proposals.proposal_harbor_runtime import (
    ProposalHarborExecution,
    run_governed_proposal_harbor,
)
from aec_bench.experimentation.proposals.proposal_trial_importing import (
    GovernedProposalCandidateFailureImport,
    GovernedProposalTrialImport,
    ProposalTrialImportError,
    finalize_governed_proposal_trial_import,
    replay_governed_proposal_candidate_failure_import,
    replay_governed_proposal_trial_import,
)
from aec_bench.experimentation.proposals.proposal_trial_importing.finalization import (
    DEFAULT_FINALIZATION_SERVICES,
)
from aec_bench.experimentation.proposals.proposal_trial_importing.validation import (
    meta_split,
    sole_trial_dir,
    validate_exact_evidence,
)
from tests.experimentation.proposals.test_proposal_dispatch_governance import (
    _authorize,
    _dispatch_fixture,
    _DispatchFixture,
)
from tests.harness.test_harbor_import import (
    _write_proposal_harbor_trial_artifacts,
)


@dataclass
class _ProposalTrialExecutor:
    fixture: _DispatchFixture
    project_root: Path
    candidate_failure: bool = False
    result_mutator: Callable[[dict[str, object]], None] | None = None
    exception: Exception | None = field(init=False, default=None)

    def execute(self, *, command: list[str], cwd: Path) -> int:
        try:
            return self._execute(command=command, cwd=cwd)
        except Exception as error:
            self.exception = error
            raise

    def _execute(self, *, command: list[str], cwd: Path) -> int:
        assert cwd == self.project_root.resolve()
        assert command[:5] == ["uv", "run", "harbor", "run", "-c"]
        trial_dir = self.project_root / "jobs" / "proposal" / "job.001" / "trial.001"
        _write_proposal_harbor_trial_artifacts(
            repo_root=self.project_root,
            trial_dir=trial_dir,
            bundle=self.fixture.bundle,
            source_task_root=Path(self.fixture.host_config.source_task_dir),
            derived_task_dir=self.fixture.dispatch.derived_task_path,
            host_config=self.fixture.host_config,
            recording_root=self.project_root / "recording-environment",
            candidate_failure=self.candidate_failure,
        )
        if self.result_mutator is not None:
            result_path = trial_dir / "result.json"
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            assert isinstance(payload, dict)
            self.result_mutator(payload)
            result_path.write_text(
                json.dumps(payload),
                encoding="utf-8",
            )
        return 0


def test_finalizes_exact_authorized_proposal_trial_with_complete_nested_provenance(
    tmp_path: Path,
) -> None:
    fixture, authorization, execution = _executed_proposal(tmp_path)

    result = finalize_governed_proposal_trial_import(
        ledger=fixture.ledger,
        authorization=authorization,
        harbor_execution_receipt_path=execution.receipt_path,
        repo_root=tmp_path,
        artifacts_root=tmp_path / "host-artifacts",
        import_id="proposal-import.1",
        authority_event_id="authority.scored-proposal-import.1",
    )

    assert isinstance(result, GovernedProposalTrialImport)
    assert result.record.completeness is Completeness.COMPLETE
    provenance = result.record.meta_harness_provenance
    assert provenance is not None
    assert provenance.run_id == authorization.dispatch.dispatch_id
    assert provenance.policy_id == (
        authorization.dispatch.bundle.compilation.proposal_freeze.candidate_manifest.manifest_id
    )
    assert provenance.kernel_sha256 == canonical_json_sha256(
        authorization.dispatch.bundle.fixed_harness.kernel_ref.model_dump(mode="json")
    )
    assert provenance.harness_sha256 == canonical_json_sha256(
        authorization.dispatch.bundle.fixed_harness.model_dump(mode="json")
    )
    assert provenance.program_sha256 == canonical_json_sha256(
        authorization.dispatch.bundle.compilation.compiled_program.model_dump(mode="json")
    )
    assert provenance.bundle_sha256 == canonical_json_sha256(authorization.dispatch.bundle.model_dump(mode="json"))
    assert provenance.proposal_session is not None
    assert provenance.proposal_session.session_id == result.import_receipt.session_id
    assert provenance.execution_seed == fixture.evaluation_coordinate.seed
    assert provenance.repetition == fixture.evaluation_coordinate.repetition
    assert provenance.execution_seed != _selected_coordinate_seed(fixture)
    assert result.record.environment.tool_versions
    assert result.authority.authority_event.event.action is AuthorityAction.SCORED_EVIDENCE_IMPORT
    artifact_kinds = {artifact.kind for artifact in result.record.outputs.artifacts or ()}
    assert {
        "candidate-manifest",
        "proposal-decomposition-graph",
        "proposal-freeze",
        "proposal-compilation",
        "governed-proposal-dispatch",
        "proposal_harbor_execution_receipt",
        "proposal-verifier-evidence",
    }.issubset(artifact_kinds)
    assert "proposal-evaluation-plan" not in artifact_kinds
    assert "proposal-structural-split" not in artifact_kinds
    for artifact in result.record.outputs.artifacts or ():
        path = Path(artifact.path)
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact.sha256
    persisted = TrialRecord.model_validate_json(result.record_path.read_bytes())
    assert persisted == result.record
    assert len(tuple(result.record_path.parent.glob("*.json"))) == 1

    provider_origin = result.authority.provider_dispatch_authority.origin
    expected_provider_parents = {
        fixture.ledger.resolve_basis(reference).origin.content_sha256
        for reference in authorization.provider_dispatch_event.basis
    }
    assert set(provider_origin.parent_origin_sha256s) == expected_provider_parents
    assert authorization.dispatch_origin.content_sha256 in expected_provider_parents
    execution_origin = result.authority.execution_receipt.origin
    assert set(execution_origin.parent_origin_sha256s) == {
        provider_origin.content_sha256,
    }
    node_origins = {binding.receipt_sha256: binding.basis.origin for binding in result.authority.node_receipts}
    session_receipt = ProposalSessionReceipt.model_validate_json(
        Path(provenance.proposal_session.session_receipt.path).read_bytes(),
    )
    for node in session_receipt.node_receipts:
        origin = node_origins[node.content_sha256]
        assert set(origin.parent_origin_sha256s) == {
            execution_origin.content_sha256,
        } | {node_origins[digest].content_sha256 for digest in node.upstream_receipt_sha256s}
    assert set(result.authority.session_receipt.origin.parent_origin_sha256s) == {
        execution_origin.content_sha256,
        *(origin.content_sha256 for origin in node_origins.values()),
    }
    assert set(result.authority.verifier_evidence.origin.parent_origin_sha256s) == {
        result.authority.session_receipt.origin.content_sha256,
    }
    assert set(result.authority.trial_record.origin.parent_origin_sha256s) == {
        result.authority.session_receipt.origin.content_sha256,
        result.authority.verifier_evidence.origin.content_sha256,
    }
    assert set(result.authority.import_receipt.origin.parent_origin_sha256s) == {
        execution_origin.content_sha256,
        result.authority.session_receipt.origin.content_sha256,
        result.authority.verifier_evidence.origin.content_sha256,
    }
    assert set(result.authority.authority_event.event.basis) == {
        result.authority.trial_record.reference,
        result.authority.import_receipt.reference,
    }

    replayed = replay_governed_proposal_trial_import(
        ledger=AuthorityLedger(fixture.ledger.root),
        authorization=authorization,
        result=result,
    )
    assert replayed == result


def test_incumbent_import_uses_matched_coordinate_and_incumbent_policy_lineage(
    tmp_path: Path,
) -> None:
    fixture = _dispatch_fixture(
        tmp_path / "fixture",
        agent_capability_id="aecbench.adapter.rlm-output-commit",
        include_tool_binding=False,
        repo_root=tmp_path,
        candidate_kind=ProgramCandidateKind.INCUMBENT,
    )
    authorization = _authorize(fixture)
    execution = _run_fixture(fixture, authorization, tmp_path)

    result = finalize_governed_proposal_trial_import(
        ledger=fixture.ledger,
        authorization=authorization,
        harbor_execution_receipt_path=execution.receipt_path,
        repo_root=tmp_path,
        artifacts_root=tmp_path / "host-artifacts",
        import_id="proposal-import.incumbent.1",
        authority_event_id="authority.scored-proposal-import.incumbent.1",
    )

    assert isinstance(result, GovernedProposalTrialImport)
    provenance = result.record.meta_harness_provenance
    assert provenance is not None
    assert provenance.execution_seed == fixture.evaluation_coordinate.seed
    assert provenance.repetition == fixture.evaluation_coordinate.repetition
    assert provenance.program_generator_sha256 == fixture.bundle.compilation.proposal_graph.incumbent_policy_sha256


@pytest.mark.parametrize(
    "changed_field",
    (
        "evaluation_coordinate",
        "execution_schedule_sha256",
        "execution_assignment_sha256",
    ),
)
def test_rejects_session_execution_ref_that_differs_from_dispatch_assignment(
    tmp_path: Path,
    changed_field: str,
) -> None:
    fixture, authorization, execution = _executed_proposal(tmp_path)
    trial_dir = sole_trial_dir(execution.receipt)
    evidence = load_proposal_harbor_import_evidence(
        trial_dir=trial_dir,
        repo_root=tmp_path,
    )
    assert evidence is not None
    if changed_field == "evaluation_coordinate":
        changed_value = evidence.session_receipt.execution.evaluation_coordinate.model_copy(
            update={"seed": evidence.session_receipt.execution.evaluation_coordinate.seed + 1},
        )
    else:
        changed_value = _sha(f"drifted-{changed_field}")
    changed_execution = evidence.session_receipt.execution.model_copy(
        update={changed_field: changed_value},
    )
    changed_evidence = replace(
        evidence,
        session_receipt=evidence.session_receipt.model_copy(
            update={"execution": changed_execution},
        ),
    )

    with pytest.raises(ProposalTrialImportError, match="authorized bundle"):
        validate_exact_evidence(
            authorization=authorization,
            evidence=changed_evidence,
        )


def test_same_execution_has_one_ledger_global_scored_import_across_roots(
    tmp_path: Path,
) -> None:
    fixture, authorization, execution = _executed_proposal(tmp_path)
    first_root = tmp_path / "host-artifacts.first"
    second_root = tmp_path / "host-artifacts.second"

    first = finalize_governed_proposal_trial_import(
        ledger=fixture.ledger,
        authorization=authorization,
        harbor_execution_receipt_path=execution.receipt_path,
        repo_root=tmp_path,
        artifacts_root=first_root,
        import_id="proposal-import.exactly-once.first",
        authority_event_id="authority.scored-proposal-import.exactly-once.first",
    )
    second = finalize_governed_proposal_trial_import(
        ledger=AuthorityLedger(fixture.ledger.root),
        authorization=authorization,
        harbor_execution_receipt_path=execution.receipt_path,
        repo_root=tmp_path,
        artifacts_root=second_root,
        import_id="proposal-import.exactly-once.second",
        authority_event_id="authority.scored-proposal-import.exactly-once.second",
    )

    assert isinstance(first, GovernedProposalTrialImport)
    assert second == first
    assert first.terminal_record.outcome == "scored"
    assert first.terminal_record.harbor_execution_receipt_sha256 == execution.receipt.content_sha256
    assert first.consumption_claim.artifacts_root == str(first_root.resolve())
    assert not second_root.exists()
    assert (
        fixture.ledger.authority_event_for_id(
            "authority.scored-proposal-import.exactly-once.second",
        )
        is None
    )
    assert len(tuple((first_root / "proposal-trial-records").rglob("*.json"))) == 1


def test_scored_import_resumes_after_trial_record_persistence_before_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture, authorization, execution = _executed_proposal(tmp_path)
    first_root = tmp_path / "host-artifacts.crash"

    def _crash_before_authority(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise RuntimeError("simulated process interruption after TrialRecord persistence")

    with pytest.raises(ProposalTrialImportError, match="simulated process interruption"):
        finalize_governed_proposal_trial_import(
            ledger=fixture.ledger,
            authorization=authorization,
            harbor_execution_receipt_path=execution.receipt_path,
            repo_root=tmp_path,
            artifacts_root=first_root,
            import_id="proposal-import.crash-recovery.first",
            authority_event_id="authority.scored-proposal-import.crash-recovery.first",
            services=replace(
                DEFAULT_FINALIZATION_SERVICES,
                record_authority=_crash_before_authority,
            ),
        )
    assert len(tuple((first_root / "proposal-trial-records").rglob("*.json"))) == 1

    second_root = tmp_path / "host-artifacts.crash-second-root"
    recovered = finalize_governed_proposal_trial_import(
        ledger=AuthorityLedger(fixture.ledger.root),
        authorization=authorization,
        harbor_execution_receipt_path=execution.receipt_path,
        repo_root=tmp_path,
        artifacts_root=second_root,
        import_id="proposal-import.crash-recovery.second",
        authority_event_id="authority.scored-proposal-import.crash-recovery.second",
    )

    assert isinstance(recovered, GovernedProposalTrialImport)
    assert recovered.import_receipt.import_id == "proposal-import.crash-recovery.first"
    assert recovered.authority.authority_event.event.event_id == "authority.scored-proposal-import.crash-recovery.first"
    assert recovered.terminal_record.outcome == "scored"
    assert not second_root.exists()
    assert len(tuple((first_root / "proposal-trial-records").rglob("*.json"))) == 1


def test_scored_import_resumes_after_authority_before_terminal_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture, authorization, execution = _executed_proposal(tmp_path)
    first_root = tmp_path / "host-artifacts.authority-crash"

    def _crash_before_terminal(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise RuntimeError("simulated process interruption before terminal index")

    with pytest.raises(ProposalTrialImportError, match="before terminal index"):
        finalize_governed_proposal_trial_import(
            ledger=fixture.ledger,
            authorization=authorization,
            harbor_execution_receipt_path=execution.receipt_path,
            repo_root=tmp_path,
            artifacts_root=first_root,
            import_id="proposal-import.authority-crash.first",
            authority_event_id="authority.scored-proposal-import.authority-crash.first",
            services=replace(
                DEFAULT_FINALIZATION_SERVICES,
                persist_terminal=_crash_before_terminal,
            ),
        )
    first_event = fixture.ledger.authority_event_for_id(
        "authority.scored-proposal-import.authority-crash.first",
    )
    assert first_event is not None

    second_root = tmp_path / "host-artifacts.authority-crash-second"
    recovered = finalize_governed_proposal_trial_import(
        ledger=AuthorityLedger(fixture.ledger.root),
        authorization=authorization,
        harbor_execution_receipt_path=execution.receipt_path,
        repo_root=tmp_path,
        artifacts_root=second_root,
        import_id="proposal-import.authority-crash.second",
        authority_event_id="authority.scored-proposal-import.authority-crash.second",
    )

    assert isinstance(recovered, GovernedProposalTrialImport)
    assert recovered.authority.authority_event == first_event
    assert recovered.terminal_record.authority_event_sha256 == first_event.event.content_sha256
    assert not second_root.exists()
    assert (
        fixture.ledger.authority_event_for_id(
            "authority.scored-proposal-import.authority-crash.second",
        )
        is None
    )
    assert len(tuple((first_root / "proposal-trial-records").rglob("*.json"))) == 1


def test_candidate_failure_preserves_evidence_without_trial_or_import_authority(
    tmp_path: Path,
) -> None:
    fixture, authorization, execution = _executed_proposal(
        tmp_path,
        candidate_failure=True,
    )

    result = finalize_governed_proposal_trial_import(
        ledger=fixture.ledger,
        authorization=authorization,
        harbor_execution_receipt_path=execution.receipt_path,
        repo_root=tmp_path,
        artifacts_root=tmp_path / "host-artifacts",
        import_id="proposal-import.failure.1",
        authority_event_id="authority.scored-proposal-import.failure.1",
    )

    assert isinstance(result, GovernedProposalCandidateFailureImport)
    assert result.evidence.session_receipt.trial_record_permitted is False
    assert result.evidence.session_receipt.failure_code is not None
    assert result.failure_record_path.is_file()
    assert all(Path(artifact.path).is_file() for artifact in result.failure_record.artifacts)
    failure_artifact_kinds = {artifact.kind for artifact in result.failure_record.artifacts}
    assert "proposal-evaluation-plan" not in failure_artifact_kinds
    assert "proposal-structural-split" not in failure_artifact_kinds
    assert not (tmp_path / "host-artifacts" / "proposal-trial-records").exists()
    assert (
        fixture.ledger.authority_event_for_id(
            "authority.scored-proposal-import.failure.1",
        )
        is None
    )
    assert result.terminal_record.outcome == "candidate_failure"
    assert result.terminal_record.authority_event_sha256 is None


def test_candidate_failure_is_terminal_and_idempotent_across_roots(
    tmp_path: Path,
) -> None:
    fixture, authorization, execution = _executed_proposal(
        tmp_path,
        candidate_failure=True,
    )
    first_root = tmp_path / "host-artifacts.failure-first"
    second_root = tmp_path / "host-artifacts.failure-second"

    first = finalize_governed_proposal_trial_import(
        ledger=fixture.ledger,
        authorization=authorization,
        harbor_execution_receipt_path=execution.receipt_path,
        repo_root=tmp_path,
        artifacts_root=first_root,
        import_id="proposal-import.failure.first",
        authority_event_id="authority.scored-proposal-import.failure.first",
    )
    second = finalize_governed_proposal_trial_import(
        ledger=AuthorityLedger(fixture.ledger.root),
        authorization=authorization,
        harbor_execution_receipt_path=execution.receipt_path,
        repo_root=tmp_path,
        artifacts_root=second_root,
        import_id="proposal-import.failure.second",
        authority_event_id="authority.scored-proposal-import.failure.second",
    )

    assert isinstance(first, GovernedProposalCandidateFailureImport)
    assert second == first
    assert first.terminal_record.outcome == "candidate_failure"
    assert first.terminal_record.terminal_artifact == first.failure_record_artifact
    assert not second_root.exists()
    assert (
        fixture.ledger.authority_event_for_id(
            "authority.scored-proposal-import.failure.first",
        )
        is None
    )
    assert (
        fixture.ledger.authority_event_for_id(
            "authority.scored-proposal-import.failure.second",
        )
        is None
    )


def test_replays_candidate_failure_with_exact_local_evidence_and_no_scored_claim(
    tmp_path: Path,
) -> None:
    fixture, authorization, execution = _executed_proposal(
        tmp_path,
        candidate_failure=True,
    )
    result = finalize_governed_proposal_trial_import(
        ledger=fixture.ledger,
        authorization=authorization,
        harbor_execution_receipt_path=execution.receipt_path,
        repo_root=tmp_path,
        artifacts_root=tmp_path / "host-artifacts",
        import_id="proposal-import.failure.replay",
        authority_event_id="authority.scored-proposal-import.failure.replay",
    )
    assert isinstance(result, GovernedProposalCandidateFailureImport)

    replayed = replay_governed_proposal_candidate_failure_import(
        ledger=AuthorityLedger(fixture.ledger.root),
        authorization=authorization,
        result=result,
    )

    assert replayed == result
    assert result.terminal_record.trial_record is None
    assert result.terminal_record.authority_event_id is None
    assert result.terminal_record.authority_event_sha256 is None
    assert (
        fixture.ledger.authority_event_for_id(
            result.consumption_claim.requested_authority_event_id,
        )
        is None
    )
    preserved_kinds = {artifact.kind for artifact in result.failure_record.artifacts}
    assert "proposal_cleanup_receipt" in preserved_kinds
    assert "proposal-trial-record" not in preserved_kinds
    assert "proposal-trial-import-receipt" not in preserved_kinds


def test_candidate_failure_replay_rejects_preserved_cleanup_tamper(
    tmp_path: Path,
) -> None:
    fixture, authorization, execution = _executed_proposal(
        tmp_path,
        candidate_failure=True,
    )
    result = finalize_governed_proposal_trial_import(
        ledger=fixture.ledger,
        authorization=authorization,
        harbor_execution_receipt_path=execution.receipt_path,
        repo_root=tmp_path,
        artifacts_root=tmp_path / "host-artifacts",
        import_id="proposal-import.failure.cleanup-tamper",
        authority_event_id="authority.scored-proposal-import.failure.cleanup-tamper",
    )
    assert isinstance(result, GovernedProposalCandidateFailureImport)
    cleanup = next(
        artifact for artifact in result.failure_record.artifacts if artifact.kind == "proposal_cleanup_receipt"
    )
    cleanup_path = Path(cleanup.path)
    cleanup_path.write_bytes(cleanup_path.read_bytes() + b"tamper")

    with pytest.raises(ProposalTrialImportError, match="artifact changed|cleanup"):
        replay_governed_proposal_candidate_failure_import(
            ledger=AuthorityLedger(fixture.ledger.root),
            authorization=authorization,
            result=result,
        )


def test_candidate_failure_replay_rejects_assignment_origin_drift(
    tmp_path: Path,
) -> None:
    fixture, authorization, execution = _executed_proposal(
        tmp_path,
        candidate_failure=True,
    )
    result = finalize_governed_proposal_trial_import(
        ledger=fixture.ledger,
        authorization=authorization,
        harbor_execution_receipt_path=execution.receipt_path,
        repo_root=tmp_path,
        artifacts_root=tmp_path / "host-artifacts",
        import_id="proposal-import.failure.assignment-drift",
        authority_event_id="authority.scored-proposal-import.failure.assignment-drift",
    )
    assert isinstance(result, GovernedProposalCandidateFailureImport)
    assignment = fixture.ledger.resolve_basis(
        authorization.execution_assignment_basis,
    )
    assignment.origin_path.unlink()

    with pytest.raises(ProposalTrialImportError, match="assignment|origin|dispatch"):
        replay_governed_proposal_candidate_failure_import(
            ledger=AuthorityLedger(fixture.ledger.root),
            authorization=authorization,
            result=result,
        )


def test_candidate_failure_replay_rejects_requested_scored_authority(
    tmp_path: Path,
) -> None:
    fixture, authorization, execution = _executed_proposal(
        tmp_path,
        candidate_failure=True,
    )
    result = finalize_governed_proposal_trial_import(
        ledger=fixture.ledger,
        authorization=authorization,
        harbor_execution_receipt_path=execution.receipt_path,
        repo_root=tmp_path,
        artifacts_root=tmp_path / "host-artifacts",
        import_id="proposal-import.failure.rogue-authority",
        authority_event_id="authority.scored-proposal-import.failure.rogue-authority",
    )
    assert isinstance(result, GovernedProposalCandidateFailureImport)
    event_payload = authorization.compile_event.model_dump(
        mode="json",
        exclude={"content_sha256"},
    )
    event_payload.update(
        {
            "event_id": result.consumption_claim.requested_authority_event_id,
            "action": AuthorityAction.SCORED_EVIDENCE_IMPORT,
            "subject_id": result.failure_record.import_id,
            "subject_sha256": result.failure_record.content_sha256,
            "reasons": ["candidate failure must not claim scored authority"],
        },
    )
    fixture.ledger.issue_authority_event(
        AuthorityEvent.model_validate(event_payload),
    )

    with pytest.raises(ProposalTrialImportError, match="scored authority"):
        replay_governed_proposal_candidate_failure_import(
            ledger=AuthorityLedger(fixture.ledger.root),
            authorization=authorization,
            result=result,
        )


def test_rejects_tampered_ledger_global_terminal_index(
    tmp_path: Path,
) -> None:
    fixture, authorization, execution = _executed_proposal(tmp_path)
    result = finalize_governed_proposal_trial_import(
        ledger=fixture.ledger,
        authorization=authorization,
        harbor_execution_receipt_path=execution.receipt_path,
        repo_root=tmp_path,
        artifacts_root=tmp_path / "host-artifacts",
        import_id="proposal-import.terminal-tamper",
        authority_event_id="authority.scored-proposal-import.terminal-tamper",
    )
    assert isinstance(result, GovernedProposalTrialImport)
    result.terminal_record_path.write_bytes(
        result.terminal_record_path.read_bytes() + b"tamper",
    )

    with pytest.raises(ProposalTrialImportError, match="terminal|index|canonical"):
        finalize_governed_proposal_trial_import(
            ledger=AuthorityLedger(fixture.ledger.root),
            authorization=authorization,
            harbor_execution_receipt_path=execution.receipt_path,
            repo_root=tmp_path,
            artifacts_root=tmp_path / "different-root",
            import_id="proposal-import.terminal-tamper.second",
            authority_event_id="authority.scored-proposal-import.terminal-tamper.second",
        )


def test_rejects_model_drift_captured_inside_the_harbor_run_receipt(
    tmp_path: Path,
) -> None:
    def _change_model(payload: dict[str, object]) -> None:
        config = payload["config"]
        assert isinstance(config, dict)
        agent = config["agent"]
        assert isinstance(agent, dict)
        agent["model_name"] = "model-not-authorized"

    fixture, authorization, execution = _executed_proposal(
        tmp_path,
        result_mutator=_change_model,
    )

    with pytest.raises(ProposalTrialImportError, match="model|fixed-H0"):
        finalize_governed_proposal_trial_import(
            ledger=fixture.ledger,
            authorization=authorization,
            harbor_execution_receipt_path=execution.receipt_path,
            repo_root=tmp_path,
            artifacts_root=tmp_path / "host-artifacts",
            import_id="proposal-import.model-drift",
            authority_event_id="authority.scored-proposal-import.model-drift",
        )


def test_rejects_physical_job_tamper_before_import(
    tmp_path: Path,
) -> None:
    fixture, authorization, execution = _executed_proposal(tmp_path)
    assert execution.receipt.job_dir is not None
    target = (
        Path(execution.receipt.job_dir)
        / "trial.001"
        / "proposal-morph-boundary"
        / "sealed-artifacts"
        / "workspace"
        / "output.md"
    )
    target.write_bytes(target.read_bytes() + b"tamper")

    with pytest.raises(ProposalTrialImportError, match="job files changed"):
        finalize_governed_proposal_trial_import(
            ledger=fixture.ledger,
            authorization=authorization,
            harbor_execution_receipt_path=execution.receipt_path,
            repo_root=tmp_path,
            artifacts_root=tmp_path / "host-artifacts",
            import_id="proposal-import.physical-drift",
            authority_event_id="authority.scored-proposal-import.physical-drift",
        )


@pytest.mark.parametrize(
    "target",
    ("source", "derived_task"),
)
def test_rejects_source_or_derived_task_drift_before_import(
    tmp_path: Path,
    target: str,
) -> None:
    fixture, authorization, execution = _executed_proposal(tmp_path)
    task_root = (
        Path(authorization.dispatch.host_config.source_task_dir)
        if target == "source"
        else Path(authorization.dispatch.derived_task_path)
    )
    instruction = task_root / "instruction.md"
    instruction.write_bytes(instruction.read_bytes() + b"\ndrift\n")

    with pytest.raises(ProposalTrialImportError, match="task|package|changed"):
        finalize_governed_proposal_trial_import(
            ledger=fixture.ledger,
            authorization=authorization,
            harbor_execution_receipt_path=execution.receipt_path,
            repo_root=tmp_path,
            artifacts_root=tmp_path / "host-artifacts",
            import_id=f"proposal-import.{target}-drift",
            authority_event_id=f"authority.scored-proposal-import.{target}-drift",
        )


def test_rejects_missing_task_review_basis_before_import(
    tmp_path: Path,
) -> None:
    fixture, authorization, execution = _executed_proposal(tmp_path)
    reference = next(
        item for item in authorization.freeze_authority_event.basis if ".structural-split." in item.artifact_id
    )
    fixture.ledger.resolve_basis(reference).content_path.unlink()

    with pytest.raises(ProposalTrialImportError, match="basis|freeze|task-review"):
        finalize_governed_proposal_trial_import(
            ledger=AuthorityLedger(fixture.ledger.root),
            authorization=authorization,
            harbor_execution_receipt_path=execution.receipt_path,
            repo_root=tmp_path,
            artifacts_root=tmp_path / "host-artifacts",
            import_id="proposal-import.missing-task-review",
            authority_event_id="authority.scored-proposal-import.missing-task-review",
        )


def test_rejects_provider_dispatch_event_drift_before_import(
    tmp_path: Path,
) -> None:
    fixture, authorization, execution = _executed_proposal(tmp_path)
    event_payload = authorization.provider_dispatch_event.model_dump(
        mode="json",
        exclude={"content_sha256"},
    )
    event_payload["reasons"] = [
        *event_payload["reasons"],
        "drifted after execution",
    ]
    drifted = replace(
        authorization,
        provider_dispatch_event=AuthorityEvent.model_validate(event_payload),
    )

    with pytest.raises(ProposalTrialImportError, match="event drift|dispatch"):
        finalize_governed_proposal_trial_import(
            ledger=AuthorityLedger(fixture.ledger.root),
            authorization=drifted,
            harbor_execution_receipt_path=execution.receipt_path,
            repo_root=tmp_path,
            artifacts_root=tmp_path / "host-artifacts",
            import_id="proposal-import.event-drift",
            authority_event_id="authority.scored-proposal-import.event-drift",
        )


def test_replay_rejects_node_origin_drift(
    tmp_path: Path,
) -> None:
    fixture, authorization, execution = _executed_proposal(tmp_path)
    result = finalize_governed_proposal_trial_import(
        ledger=fixture.ledger,
        authorization=authorization,
        harbor_execution_receipt_path=execution.receipt_path,
        repo_root=tmp_path,
        artifacts_root=tmp_path / "host-artifacts",
        import_id="proposal-import.origin-drift",
        authority_event_id="authority.scored-proposal-import.origin-drift",
    )
    assert isinstance(result, GovernedProposalTrialImport)
    result.authority.node_receipts[0].basis.origin_path.unlink()

    with pytest.raises(ProposalTrialImportError, match="origin|basis"):
        replay_governed_proposal_trial_import(
            ledger=AuthorityLedger(fixture.ledger.root),
            authorization=authorization,
            result=result,
        )


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        (OptimizationSplit.CALIBRATION, "calibration"),
        (OptimizationSplit.TRAINING, "discovery"),
        (OptimizationSplit.DEVELOPMENT, "repair_gate"),
        (OptimizationSplit.STRUCTURAL_HOLDOUT, "holdout"),
    ),
)
def test_maps_proposal_splits_to_closed_trial_splits(
    source: OptimizationSplit,
    expected: str,
) -> None:
    assert meta_split(source) == expected


def _executed_proposal(
    tmp_path: Path,
    *,
    candidate_failure: bool = False,
    result_mutator: Callable[[dict[str, object]], None] | None = None,
) -> tuple[
    _DispatchFixture,
    GovernedProposalDispatchAuthorization,
    ProposalHarborExecution,
]:
    fixture = _dispatch_fixture(
        tmp_path / "fixture",
        agent_capability_id="aecbench.adapter.rlm-output-commit",
        include_tool_binding=False,
        repo_root=tmp_path,
    )
    authorization = _authorize(fixture)
    execution = _run_fixture(
        fixture,
        authorization,
        tmp_path,
        candidate_failure=candidate_failure,
        result_mutator=result_mutator,
    )
    return fixture, authorization, execution


def _run_fixture(
    fixture: _DispatchFixture,
    authorization: GovernedProposalDispatchAuthorization,
    project_root: Path,
    *,
    candidate_failure: bool = False,
    result_mutator: Callable[[dict[str, object]], None] | None = None,
) -> ProposalHarborExecution:
    executor = _ProposalTrialExecutor(
        fixture=fixture,
        project_root=project_root,
        candidate_failure=candidate_failure,
        result_mutator=result_mutator,
    )
    result = run_governed_proposal_harbor(
        ledger=fixture.ledger,
        authorization=authorization,
        project_root=project_root,
        jobs_root=project_root / "jobs" / "proposal",
        artifacts_root=project_root / "execution-artifacts",
        executor=executor,
    )
    if executor.exception is not None:
        raise executor.exception
    return result


def _selected_coordinate_seed(fixture: _DispatchFixture) -> int:
    selected = fixture.bundle.compilation.candidate_ref
    coordinate = next(
        item
        for item in fixture.bundle.compilation.proposal_freeze.candidate_manifest.coordinates
        if item.coordinate_id == selected.generation_coordinate_id
    )
    return coordinate.seed


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()
