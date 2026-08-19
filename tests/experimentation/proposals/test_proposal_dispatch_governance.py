# ABOUTME: Tests host-governed proposal compilation and Harbor dispatch authority.
# ABOUTME: Proves identity joins, origin closure, and fresh-ledger replay without provider calls.

from __future__ import annotations

import hashlib
import importlib
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol, cast

import pytest

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityEvent,
    AuthorityPrincipal,
    AuthorityPrincipalKind,
)
from aec_bench.contracts.harness_kernel import canonical_json_sha256
from aec_bench.contracts.output_completion import OutputCompletionContract
from aec_bench.contracts.program_proposal.candidate import ProgramCandidateRef
from aec_bench.contracts.program_proposal.study import MatchedEvaluationCoordinate
from aec_bench.contracts.program_proposal.types import ProgramCandidateKind
from aec_bench.contracts.proposal_execution.compilation import ProposalCompilationRejection
from aec_bench.contracts.task_definition import TaskDefinition, Visibility
from aec_bench.experimentation.governance.authority_ledger import AuthorityLedger
from aec_bench.experimentation.proposals.decomposition_optimization import (
    CandidateExecutionAssignment,
    DecompositionExecutionSchedule,
    build_decomposition_execution_schedule,
)
from aec_bench.experimentation.proposals.freezing import (
    GovernedProposalFreezeResult,
)
from aec_bench.experimentation.proposals.harbor import (
    ProposalHarborDispatchInput,
    build_proposal_harbor_job_config,
)
from aec_bench.experimentation.proposals.program_compilation import (
    ProposalRunSessionBundle,
    compile_governed_proposal,
)
from aec_bench.experimentation.proposals.proposal_dispatch import (
    GovernedProposalDispatch,
    GovernedProposalDispatchAuthorization,
    ProposalDispatchGovernanceError,
    authorize_governed_proposal_dispatch,
    replay_governed_proposal_dispatch,
)
from aec_bench.experimentation.proposals.runtime_archive import build_proposal_runtime_archive
from aec_bench.experimentation.proposals.session_config import ProposalSessionHostConfig
from aec_bench.experimentation.proposals.task_package import (
    ProposalTaskPackageIdentity,
    ProposalTaskPackageManifest,
    build_proposal_task_package,
    source_task_package_sha256,
)
from aec_bench.tasks.loader import load_task_definition

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PACKAGE_ROOT = _PROJECT_ROOT / "src" / "aec_bench"


class _CompilationFixture(Protocol):
    ledger: AuthorityLedger
    host_runtime: AuthorityPrincipal


@dataclass(frozen=True)
class _DispatchFixture:
    ledger: AuthorityLedger
    host_runtime: AuthorityPrincipal
    governed_freeze: GovernedProposalFreezeResult
    execution_schedule: DecompositionExecutionSchedule
    execution_assignment: CandidateExecutionAssignment
    evaluation_coordinate: MatchedEvaluationCoordinate
    candidate_ref: ProgramCandidateRef
    bundle: ProposalRunSessionBundle
    host_config: ProposalSessionHostConfig
    dispatch: ProposalHarborDispatchInput
    harbor_job_config: dict[str, object]


def test_authorizes_exact_compile_and_dispatch_chain_and_replays_on_fresh_ledger(
    tmp_path: Path,
) -> None:
    fixture = _dispatch_fixture(tmp_path)

    authorized = _authorize(fixture)

    assert authorized.dispatch.bundle == fixture.bundle
    assert authorized.dispatch.evaluation_coordinate == fixture.evaluation_coordinate
    assert authorized.dispatch.execution_schedule_sha256 == fixture.execution_schedule.content_sha256
    assert authorized.dispatch.execution_assignment_sha256 == fixture.execution_assignment.content_sha256
    assert authorized.dispatch.candidate_ref == fixture.candidate_ref
    assert authorized.compile_event.action is AuthorityAction.COMPILE
    assert authorized.provider_dispatch_event.action is AuthorityAction.PROVIDER_DISPATCH
    assert authorized.compile_event.basis == (
        authorized.freeze_authority_basis,
        authorized.compilation_basis,
        authorized.execution_assignment_basis,
        authorized.execution_schedule_basis,
    )
    assert authorized.provider_dispatch_event.basis == (
        authorized.compile_event_basis,
        authorized.dispatch_basis,
    )
    freeze_parent_origins = {
        fixture.ledger.resolve_basis(reference).origin.content_sha256
        for reference in fixture.governed_freeze.authority_event.basis
    }
    assert set(authorized.freeze_authority_origin.parent_origin_sha256s) == freeze_parent_origins
    assert freeze_parent_origins.issubset(
        set(authorized.compilation_origin.parent_origin_sha256s),
    )
    assert authorized.compile_event_origin.content_sha256 in (authorized.dispatch_origin.parent_origin_sha256s)

    fresh_ledger = AuthorityLedger(fixture.ledger.root)
    assert (
        replay_governed_proposal_dispatch(
            ledger=fresh_ledger,
            authorization=authorized,
        )
        == authorized
    )


def test_authorizes_monolithic_incumbent_through_the_same_exact_dispatch_surface(
    tmp_path: Path,
) -> None:
    fixture = _dispatch_fixture(
        tmp_path,
        candidate_kind=ProgramCandidateKind.INCUMBENT,
    )

    authorized = _authorize(fixture)

    assert authorized.dispatch.candidate_ref.kind is ProgramCandidateKind.INCUMBENT
    assert authorized.dispatch.candidate_ref == fixture.governed_freeze.freeze.incumbent_candidate
    assert authorized.dispatch.bundle.compilation.budget_plan.aggregate_budget == (
        fixture.governed_freeze.freeze.problem_view.fixed_harness.aggregate_budget
    )
    assert authorized.dispatch.bundle.session_plan.planned_node_ids == ("finalize",)
    assert authorized.dispatch.evaluation_coordinate.seed == 701
    assert authorized.dispatch.evaluation_coordinate.repetition == 1
    assert (
        replay_governed_proposal_dispatch(
            ledger=AuthorityLedger(fixture.ledger.root),
            authorization=authorized,
        )
        == authorized
    )


def test_authorization_rechecks_freeze_before_observing_compile_or_dispatch(
    tmp_path: Path,
) -> None:
    fixture = _dispatch_fixture(tmp_path)
    stale = fixture.ledger.resolve_basis(
        fixture.governed_freeze.basis.proposal_policy,
    )
    stale.content_path.unlink()

    with pytest.raises(
        ProposalDispatchGovernanceError,
        match="freeze authority",
    ):
        _authorize(fixture)

    assert not (fixture.ledger.root / "basis-claims" / "authority_event").exists()


def test_authorization_rejects_wrong_candidate_bundle_and_host_config(
    tmp_path: Path,
) -> None:
    fixture = _dispatch_fixture(tmp_path)
    wrong_candidate = fixture.governed_freeze.freeze.realized_candidates[1]

    with pytest.raises(ProposalDispatchGovernanceError, match="candidate"):
        _authorize(fixture, candidate_ref=wrong_candidate)

    bundle_payload = fixture.bundle.model_dump(
        mode="json",
        exclude={"content_sha256"},
    )
    bundle_payload["bundle_id"] = "proposal-bundle.other"
    wrong_bundle = ProposalRunSessionBundle.model_validate(bundle_payload)
    with pytest.raises(ProposalDispatchGovernanceError, match="bundle"):
        _authorize(fixture, bundle=wrong_bundle)

    config_payload = fixture.host_config.model_dump(mode="json")
    config_payload["bundle_content_sha256"] = _sha("wrong-bundle")
    wrong_config = ProposalSessionHostConfig.model_validate(config_payload)
    with pytest.raises(ProposalDispatchGovernanceError, match="host configuration"):
        _authorize(fixture, host_config=wrong_config)


def test_authorization_rejects_wrong_runtime_task_and_noncanonical_job(
    tmp_path: Path,
) -> None:
    fixture = _dispatch_fixture(tmp_path)

    config_payload = fixture.host_config.model_dump(mode="json")
    config_payload["runtime_archive_sha256"] = _sha("wrong-runtime")
    wrong_runtime = ProposalSessionHostConfig.model_validate(config_payload)
    with pytest.raises(ProposalDispatchGovernanceError, match="runtime"):
        _authorize(
            fixture,
            host_config=wrong_runtime,
            dispatch=replace(fixture.dispatch, host_config=wrong_runtime),
        )

    wrong_task = TaskDefinition.model_validate(
        {
            **fixture.dispatch.derived_task.model_dump(mode="json"),
            "task_id": "civil/calculation/wrong-task",
        }
    )
    with pytest.raises(ProposalDispatchGovernanceError, match="task"):
        _authorize(
            fixture,
            dispatch=replace(fixture.dispatch, derived_task=wrong_task),
        )

    wrong_job = dict(fixture.harbor_job_config)
    wrong_job["n_attempts"] = 2
    with pytest.raises(ProposalDispatchGovernanceError, match="canonical Harbor job"):
        _authorize(fixture, harbor_job_config=wrong_job)

    wrong_coordinate = MatchedEvaluationCoordinate.model_validate(
        {
            **fixture.evaluation_coordinate.model_dump(
                mode="json",
                exclude={"content_sha256"},
            ),
            "review_lineage_id": _sha("wrong-review"),
        },
    )
    with pytest.raises(ProposalDispatchGovernanceError, match="evaluation coordinate"):
        _authorize(
            fixture,
            evaluation_coordinate=wrong_coordinate,
        )


@pytest.mark.parametrize(
    "changed_field",
    (
        "evaluation_coordinate",
        "execution_schedule_sha256",
        "execution_assignment_sha256",
    ),
)
def test_authorization_rejects_host_config_outside_exact_evaluation_assignment(
    tmp_path: Path,
    changed_field: str,
) -> None:
    fixture = _dispatch_fixture(tmp_path)
    if changed_field == "evaluation_coordinate":
        changed_value = MatchedEvaluationCoordinate.model_validate(
            {
                **fixture.evaluation_coordinate.model_dump(
                    mode="json",
                    exclude={"content_sha256"},
                ),
                "repetition": fixture.evaluation_coordinate.repetition + 1,
            },
        )
    else:
        changed_value = _sha(f"wrong-{changed_field}")
    changed_host_config = fixture.host_config.model_copy(
        update={changed_field: changed_value},
    )

    with pytest.raises(
        ProposalDispatchGovernanceError,
        match="host configuration evaluation coordinate or assignment",
    ):
        _authorize(
            fixture,
            host_config=changed_host_config,
            dispatch=replace(
                fixture.dispatch,
                host_config=changed_host_config,
            ),
        )


def test_governed_dispatch_contract_binds_host_config_to_frozen_assignment(
    tmp_path: Path,
) -> None:
    fixture = _dispatch_fixture(tmp_path)
    record = _authorize(fixture).dispatch
    payload = record.model_dump(mode="json", exclude={"content_sha256"})
    host_config = dict(payload["host_config"])
    host_config["execution_assignment_sha256"] = _sha("wrong-host-assignment")
    payload["host_config"] = host_config
    payload["host_config_sha256"] = canonical_json_sha256(host_config)

    with pytest.raises(
        ValueError,
        match="host configuration evaluation coordinate or assignment",
    ):
        GovernedProposalDispatch.model_validate(payload)


def test_authorization_requires_host_runtime_principal(
    tmp_path: Path,
) -> None:
    fixture = _dispatch_fixture(tmp_path)

    with pytest.raises(ProposalDispatchGovernanceError, match="host_runtime"):
        _authorize(
            fixture,
            host_runtime=AuthorityPrincipal(
                principal_id="candidate.dispatcher",
                kind=AuthorityPrincipalKind.CANDIDATE,
            ),
        )


def test_replay_fails_when_an_inherited_parent_origin_disappears(
    tmp_path: Path,
) -> None:
    fixture = _dispatch_fixture(tmp_path)
    authorized = _authorize(fixture)
    inherited = fixture.ledger.resolve_basis(
        fixture.governed_freeze.basis.problem_view,
    )
    inherited.origin_path.unlink()

    with pytest.raises(
        ProposalDispatchGovernanceError,
        match="origin closure",
    ):
        replay_governed_proposal_dispatch(
            ledger=AuthorityLedger(fixture.ledger.root),
            authorization=authorized,
        )


@pytest.mark.parametrize("event_name", ("compile", "provider_dispatch"))
def test_replay_rejects_authority_event_drift(
    tmp_path: Path,
    event_name: str,
) -> None:
    fixture = _dispatch_fixture(tmp_path)
    authorized = _authorize(fixture)
    selected = authorized.compile_event if event_name == "compile" else authorized.provider_dispatch_event
    payload = selected.model_dump(mode="json", exclude={"content_sha256"})
    payload["reasons"] = [*payload["reasons"], "drifted after authorization"]
    drifted = AuthorityEvent.model_validate(payload)
    changed: GovernedProposalDispatchAuthorization
    if event_name == "compile":
        changed = replace(authorized, compile_event=drifted)
    else:
        changed = replace(authorized, provider_dispatch_event=drifted)

    with pytest.raises(ProposalDispatchGovernanceError, match="event drift"):
        replay_governed_proposal_dispatch(
            ledger=AuthorityLedger(fixture.ledger.root),
            authorization=changed,
        )


def _authorize(
    fixture: _DispatchFixture,
    *,
    candidate_ref: ProgramCandidateRef | None = None,
    bundle: ProposalRunSessionBundle | None = None,
    host_config: ProposalSessionHostConfig | None = None,
    dispatch: ProposalHarborDispatchInput | None = None,
    harbor_job_config: dict[str, object] | None = None,
    host_runtime: AuthorityPrincipal | None = None,
    evaluation_coordinate: MatchedEvaluationCoordinate | None = None,
) -> GovernedProposalDispatchAuthorization:
    return authorize_governed_proposal_dispatch(
        ledger=fixture.ledger,
        dispatch_id="dispatch.candidate.1",
        compile_event_id="authority.compile.candidate.1",
        provider_dispatch_event_id="authority.provider-dispatch.candidate.1",
        governed_freeze=fixture.governed_freeze,
        execution_schedule=fixture.execution_schedule,
        execution_assignment=fixture.execution_assignment,
        evaluation_coordinate=(evaluation_coordinate or fixture.evaluation_coordinate),
        candidate_ref=candidate_ref or fixture.candidate_ref,
        bundle=bundle or fixture.bundle,
        host_config=host_config or fixture.host_config,
        dispatch=dispatch or fixture.dispatch,
        harbor_job_config=(harbor_job_config if harbor_job_config is not None else fixture.harbor_job_config),
        host_runtime=host_runtime or fixture.host_runtime,
        jobs_dir="jobs/proposal",
    )


def _dispatch_fixture(
    tmp_path: Path,
    *,
    agent_capability_id: str = "aecbench.adapter.tool-loop",
    include_tool_binding: bool = True,
    repo_root: Path | None = None,
    candidate_kind: ProgramCandidateKind = ProgramCandidateKind.PROPOSAL,
) -> _DispatchFixture:
    compilation_tests = importlib.import_module(
        "tests.experimentation.proposals.test_program_compilation",
    )
    graph_fixture = cast(
        Callable[
            ...,
            tuple[
                _CompilationFixture,
                GovernedProposalFreezeResult,
                object,
            ],
        ],
        compilation_tests._governed_graph_fixture,
    )
    incumbent_fixture = cast(
        Callable[
            ...,
            tuple[
                _CompilationFixture,
                GovernedProposalFreezeResult,
                object,
            ],
        ],
        compilation_tests._governed_incumbent_fixture,
    )
    compile_arguments = cast(
        Callable[..., dict[str, object]],
        compilation_tests._compile_arguments,
    )
    if candidate_kind is ProgramCandidateKind.INCUMBENT:
        fixture, governed, _graph = incumbent_fixture(
            tmp_path / "governed",
            agent_capability_id=agent_capability_id,
            include_tool_binding=include_tool_binding,
        )
        candidate_ref = governed.freeze.incumbent_candidate
        assert candidate_ref is not None
    else:
        fixture, governed, _graph = graph_fixture(
            tmp_path / "governed",
            shape="serial",
            agent_capability_id=agent_capability_id,
            include_tool_binding=include_tool_binding,
        )
        candidate_ref = governed.freeze.realized_candidates[0]
    compile_call = cast(Callable[..., object], compile_governed_proposal)
    compiled = compile_call(
        **compile_arguments(
            fixture,
            governed,
            candidate_ref=candidate_ref,
        ),
    )
    assert not isinstance(compiled, ProposalCompilationRejection)
    assert isinstance(compiled, ProposalRunSessionBundle)
    return _materialize_dispatch_fixture(
        tmp_path,
        fixture=fixture,
        governed=governed,
        compiled=compiled,
        repo_root=repo_root,
    )


def _materialize_dispatch_fixture(
    tmp_path: Path,
    *,
    fixture: _CompilationFixture,
    governed: GovernedProposalFreezeResult,
    compiled: ProposalRunSessionBundle,
    repo_root: Path | None = None,
) -> _DispatchFixture:
    """Materialize one compiled governed proposal into exact host dispatch inputs."""

    bundle_path = tmp_path / "proposal-session-bundle.json"
    bundle_path.write_text(compiled.model_dump_json(), encoding="utf-8")
    runtime_archive = build_proposal_runtime_archive(
        package_root=_PACKAGE_ROOT,
        archive_path=tmp_path / "proposal-runtime.tar.gz",
    )
    source_task_dir = fixture.ledger.root.parent / "tasks" / compiled.task_snapshot.task_id
    source_package_sha256 = source_task_package_sha256(source_task_dir)
    output_contract = OutputCompletionContract.model_validate(
        compiled.compilation.proposal_freeze.problem_view.output_contract,
    )
    derived = build_proposal_task_package(
        source_task_dir=source_task_dir,
        destination_task_dir=(
            tmp_path / "derived-task"
            if repo_root is None
            else Path(repo_root) / "tasks" / compiled.task_snapshot.task_id
        ),
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
        coordinate_id=(f"evaluation.{compiled.compilation.candidate_ref.candidate_id}.1"),
        task_id=governed.freeze.problem_view.task_id,
        task_revision=governed.freeze.problem_view.task_revision,
        split=governed.freeze.split,
        review_lineage_id=governed.freeze.selected_review_lineage_id,
        seed=701,
        repetition=1,
    )
    incumbent = governed.freeze.incumbent_candidate or ProgramCandidateRef(
        candidate_id="candidate.incumbent.schedule-control",
        kind=ProgramCandidateKind.INCUMBENT,
        candidate_artifact_sha256=_sha("incumbent.schedule-control"),
    )
    execution_schedule = build_decomposition_execution_schedule(
        schedule_id=f"schedule.{compiled.compilation.candidate_ref.candidate_id}",
        proposal_freeze=governed.freeze,
        incumbent_candidate=incumbent,
        coordinates=(evaluation_coordinate,),
        kernel_ref=compiled.compilation.kernel_ref,
        fixed_harness_ref=compiled.fixed_harness.ref,
        evaluation_regime_ref=governed.freeze.evaluation_regime_ref,
        aggregate_budget=compiled.fixed_harness.budget,
    )
    execution_assignment = next(
        assignment
        for assignment in execution_schedule.assignments
        if assignment.candidate == compiled.compilation.candidate_ref
    )
    host_config = ProposalSessionHostConfig(
        bundle_path=str(bundle_path.resolve()),
        bundle_file_sha256=hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
        bundle_content_sha256=compiled.content_sha256,
        source_task_dir=str(source_task_dir.resolve()),
        source_task_package_sha256=source_package_sha256,
        runtime_archive_path=str(runtime_archive.path.resolve()),
        runtime_archive_sha256=runtime_archive.archive_sha256,
        runtime_archive_content_sha256=runtime_archive.content_sha256,
        evaluation_coordinate=evaluation_coordinate,
        execution_schedule_sha256=execution_schedule.content_sha256,
        execution_assignment_sha256=execution_assignment.content_sha256,
    )
    manifest = ProposalTaskPackageManifest.model_validate_json(
        (derived.path / "proposal-task-package.json").read_bytes(),
    )
    observed_task = load_task_definition(
        derived.path,
        derived.path.parent.parent,
    )
    derived_task = observed_task.model_copy(
        update={"task_id": manifest.task_id},
    )
    dispatch = ProposalHarborDispatchInput(
        host_config=host_config,
        derived_task_path=derived.path.resolve(),
        derived_task=derived_task,
        derived_task_manifest=manifest,
    )
    harbor_job_config = cast(
        dict[str, object],
        build_proposal_harbor_job_config(
            dispatch=dispatch,
            jobs_dir="jobs/proposal",
        ),
    )
    return _DispatchFixture(
        ledger=fixture.ledger,
        host_runtime=fixture.host_runtime,
        governed_freeze=governed,
        execution_schedule=execution_schedule,
        execution_assignment=execution_assignment,
        evaluation_coordinate=evaluation_coordinate,
        candidate_ref=compiled.compilation.candidate_ref,
        bundle=compiled,
        host_config=host_config,
        dispatch=dispatch,
        harbor_job_config=harbor_job_config,
    )


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()
