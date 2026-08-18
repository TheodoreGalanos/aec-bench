# ABOUTME: Exercises the content-addressed repair-only specification and runner over the real Harbor workflow seam.
# ABOUTME: Proves one generic typed diagnosis can execute without the surrounding adaptive-cycle stages.

from __future__ import annotations

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.contracts.harness_kernel import KernelManifest
from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.evolution.repair_lifecycle import (
    CompiledRepairCandidate,
    RepairLoopError,
    RepairLoopStatus,
    RepairRunResult,
)
from aec_bench.experimentation.qualification.adaptive_diagnosis import (
    AdaptiveDiagnosisPolicy,
    HarnessMaxTurnsDiagnosisRule,
)
from aec_bench.experimentation.qualification.repair_run import (
    RepairAttemptClaim,
    RepairAttemptClaimError,
    RepairAttemptCompletion,
    RepairRunSpec,
    prepare_repair_run_spec,
    run_repair,
)
from aec_bench.experimentation.qualification.repair_runtime import (
    RepairAttemptPlan,
    RepairEvidenceUsePolicy,
    RepairRuntime,
    RepairRuntimeExecution,
    RepairTerminalRecord,
    RepairVerifierPolicy,
    StoredRepairArtifact,
)
from aec_bench.harness.kernel_catalogue import KernelRuntimeRegistry
from aec_bench.ledger.reader import read_trial_record
from tests.experimentation.qualification.test_repair_runtime import (
    ChildDispatchFailingHarborExecutor,
    RewardByTurnsHarborExecutor,
    _build_runtime,
)


def test_repair_run_spec_is_strict_content_addressed_and_binds_its_parent(tmp_path: Path) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
    )

    spec = _spec(fixture)

    assert RepairRunSpec.model_validate_json(spec.model_dump_json()) == spec
    assert len(spec.content_sha256) == 64
    assert spec.evidence_use_policy == RepairEvidenceUsePolicy.exploratory_matched_repair()
    missing_policy = spec.model_dump(
        mode="python",
        exclude={"content_sha256", "evidence_use_policy"},
    )
    with pytest.raises(ValidationError, match="evidence_use_policy"):
        RepairRunSpec.model_validate(missing_policy)
    widened_policy = spec.model_dump(mode="python", exclude={"content_sha256"})
    widened_policy["evidence_use_policy"]["generalized_causal_effects_supported"] = True
    with pytest.raises(ValidationError, match="generalized_causal_effects_supported"):
        RepairRunSpec.model_validate(widened_policy)
    motif_eligible_policy = spec.model_dump(mode="python", exclude={"content_sha256"})
    motif_eligible_policy["evidence_use_policy"] = (
        RepairEvidenceUsePolicy.calibration_gated_adaptive_cycle().model_dump(mode="python")
    )
    with pytest.raises(ValidationError, match="standalone repair spec"):
        RepairRunSpec.model_validate(motif_eligible_policy)
    with pytest.raises(ValidationError, match="repair parent does not match its request"):
        RepairRunSpec.model_validate(
            spec.model_dump(mode="python", exclude={"content_sha256"})
            | {"parent": spec.parent.model_copy(update={"candidate_id": "candidate.other"})}
        )
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RepairRunSpec.model_validate(spec.model_dump(mode="python", exclude={"content_sha256"}) | {"mock_mode": True})
    infeasible = spec.model_dump(mode="python", exclude={"content_sha256"})
    infeasible["diagnosis_rule"]["rules"][0]["max_turns"] = 1
    with pytest.raises(ValidationError, match="must strictly increase binding max_turns"):
        RepairRunSpec.model_validate(infeasible)


def test_repair_runner_executes_one_typed_paired_repair_without_adaptive_cycle(tmp_path: Path) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
    )
    executor = RewardByTurnsHarborExecutor(emit_turn_limit_failure=True)

    result = run_repair(
        spec=_spec(fixture),
        registry=fixture.registry,
        workflow=fixture.workflow,
        artifacts_root=tmp_path / "repair-run-artifacts",
        executor=executor,
    )

    assert result.result.status is RepairLoopStatus.ACCEPTED
    assert result.terminal.path.is_file()
    assert result.terminal.path.parent.name == result.terminal.reference.sha256
    assert executor.calls == [(17, 1), (29, 1), (17, 2), (29, 2)]


def test_repair_runner_rejects_kernel_drift_before_claiming_the_attempt(tmp_path: Path) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
    )
    spec = _spec(fixture)
    manifest = fixture.registry.manifest
    drifted_registry = KernelRuntimeRegistry(
        manifest=KernelManifest(
            kernel_id=manifest.kernel_id,
            version="99.0.0",
            capabilities=manifest.capabilities,
            implementation=manifest.implementation,
        ),
        primitives=fixture.registry.primitives,
    )
    artifacts_root = tmp_path / "kernel-drift-artifacts"
    executor = RewardByTurnsHarborExecutor(emit_turn_limit_failure=True)

    with pytest.raises(ValueError, match="installed fixed kernel"):
        run_repair(
            spec=spec,
            registry=drifted_registry,
            workflow=fixture.workflow,
            artifacts_root=artifacts_root,
            executor=executor,
        )

    assert not (artifacts_root / "repair-attempt-claims").exists()
    assert executor.calls == []


def test_repair_runner_claims_attempt_and_persists_terminal_completion_receipt(
    tmp_path: Path,
) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
    )
    spec = _spec(fixture)
    artifacts_root = tmp_path / "claimed-repair-artifacts"

    result = run_repair(
        spec=spec,
        registry=fixture.registry,
        workflow=fixture.workflow,
        artifacts_root=artifacts_root,
        executor=RewardByTurnsHarborExecutor(emit_turn_limit_failure=True),
    )

    claim_path, completion_path = _only_attempt_claim_paths(artifacts_root)
    claim = RepairAttemptClaim.model_validate_json(claim_path.read_text(encoding="utf-8"))
    completion = RepairAttemptCompletion.model_validate_json(completion_path.read_text(encoding="utf-8"))
    assert claim.loop_id == spec.request.loop_id
    assert claim.attempt_id == spec.request.attempt_id
    assert claim.repair_run_spec_content_sha256 == spec.content_sha256
    assert completion.claim_content_sha256 == claim.content_sha256
    assert completion.repair_run_spec == claim.repair_run_spec
    assert completion.attempt_plan == result.attempt_plan.reference
    assert completion.terminal == result.terminal.reference
    plan = RepairAttemptPlan.model_validate_json(result.attempt_plan.path.read_text(encoding="utf-8"))
    terminal = RepairTerminalRecord.model_validate_json(result.terminal.path.read_text(encoding="utf-8"))
    assert plan.evidence_use_policy == spec.evidence_use_policy
    assert terminal.evidence_use_policy == spec.evidence_use_policy
    assert completion.evidence_use_policy == spec.evidence_use_policy


def test_repair_runner_completes_child_evidence_incomplete_attempt(
    tmp_path: Path,
) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
    )
    spec = _spec(fixture)
    artifacts_root = tmp_path / "incomplete-child-repair-artifacts"

    result = run_repair(
        spec=spec,
        registry=fixture.registry,
        workflow=fixture.workflow,
        artifacts_root=artifacts_root,
        executor=ChildDispatchFailingHarborExecutor(emit_turn_limit_failure=True),
    )

    _claim_path, completion_path = _only_attempt_claim_paths(artifacts_root)
    completion = RepairAttemptCompletion.model_validate_json(completion_path.read_text(encoding="utf-8"))
    terminal = RepairTerminalRecord.model_validate_json(result.terminal.path.read_text(encoding="utf-8"))
    assert result.result.status is RepairLoopStatus.CHILD_EVIDENCE_INCOMPLETE
    assert terminal.result.status is RepairLoopStatus.CHILD_EVIDENCE_INCOMPLETE
    assert completion.terminal_status is RepairLoopStatus.CHILD_EVIDENCE_INCOMPLETE
    assert completion.terminal == result.terminal.reference


def test_standalone_exploratory_repair_cannot_enter_motif_evidence(tmp_path: Path) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
    )
    execution = run_repair(
        spec=_spec(fixture),
        registry=fixture.registry,
        workflow=fixture.workflow,
        artifacts_root=tmp_path / "exploratory-repair-artifacts",
        executor=RewardByTurnsHarborExecutor(emit_turn_limit_failure=True),
    )

    from aec_bench.experimentation.qualification.motif_learning import capture_accepted_repair_evidence

    with pytest.raises(ValueError, match="does not permit motif evidence capture"):
        capture_accepted_repair_evidence(execution)


def test_repair_runner_rejects_tampered_completion_evidence_use_policy(tmp_path: Path) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
    )
    spec = _spec(fixture)
    artifacts_root = tmp_path / "tampered-policy-artifacts"
    first_executor = RewardByTurnsHarborExecutor(emit_turn_limit_failure=True)
    run_repair(
        spec=spec,
        registry=fixture.registry,
        workflow=fixture.workflow,
        artifacts_root=artifacts_root,
        executor=first_executor,
    )
    _claim_path, completion_path = _only_attempt_claim_paths(artifacts_root)
    completion = RepairAttemptCompletion.model_validate_json(completion_path.read_text(encoding="utf-8"))
    tampered = RepairAttemptCompletion(
        **completion.model_dump(
            mode="python",
            exclude={"content_sha256", "evidence_use_policy"},
        ),
        evidence_use_policy=RepairEvidenceUsePolicy.calibration_gated_adaptive_cycle(),
    )
    completion_path.write_text(
        json.dumps(tampered.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    retry_executor = RewardByTurnsHarborExecutor(emit_turn_limit_failure=True)

    with pytest.raises(RepairAttemptClaimError, match="evidence-use policy"):
        run_repair(
            spec=spec,
            registry=fixture.registry,
            workflow=fixture.workflow,
            artifacts_root=artifacts_root,
            executor=retry_executor,
        )

    assert retry_executor.calls == []


def test_repair_runner_rejects_terminal_evidence_use_policy_not_in_spec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
    )
    spec = _spec(fixture)
    execute = RepairRuntime.execute

    def forge_terminal_policy(runtime: RepairRuntime) -> RepairRuntimeExecution:
        execution = execute(runtime)
        terminal = RepairTerminalRecord.model_validate_json(execution.terminal.path.read_text(encoding="utf-8"))
        forged = RepairTerminalRecord(
            **terminal.model_dump(
                mode="python",
                exclude={"content_sha256", "evidence_use_policy"},
            ),
            evidence_use_policy=RepairEvidenceUsePolicy.calibration_gated_adaptive_cycle(),
        )
        encoded = (json.dumps(forged.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode()
        path = tmp_path / "forged-policy-terminal.json"
        path.write_bytes(encoded)
        reference = ArtifactReference(
            kind="repair-terminal",
            path=str(path),
            sha256=hashlib.sha256(encoded).hexdigest(),
            media_type="application/json",
        )
        return RepairRuntimeExecution(
            result=execution.result,
            attempt_plan=execution.attempt_plan,
            run_artifacts=execution.run_artifacts,
            terminal=StoredRepairArtifact(path=path, reference=reference),
        )

    monkeypatch.setattr(RepairRuntime, "execute", forge_terminal_policy)

    with pytest.raises(RepairAttemptClaimError, match="evidence-use policy"):
        run_repair(
            spec=spec,
            registry=fixture.registry,
            workflow=fixture.workflow,
            artifacts_root=tmp_path / "terminal-policy-artifacts",
            executor=RewardByTurnsHarborExecutor(emit_turn_limit_failure=True),
        )


def test_repeated_repair_run_refuses_before_new_executor_calls(tmp_path: Path) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
    )
    spec = _spec(fixture)
    artifacts_root = tmp_path / "repeated-repair-artifacts"
    executor = RewardByTurnsHarborExecutor(emit_turn_limit_failure=True)

    run_repair(
        spec=spec,
        registry=fixture.registry,
        workflow=fixture.workflow,
        artifacts_root=artifacts_root,
        executor=executor,
    )
    calls_after_first_run = tuple(executor.calls)

    with pytest.raises(RepairAttemptClaimError, match="already completed"):
        run_repair(
            spec=spec,
            registry=fixture.registry,
            workflow=fixture.workflow,
            artifacts_root=artifacts_root,
            executor=executor,
        )

    assert tuple(executor.calls) == calls_after_first_run


def test_concurrent_repair_run_refuses_second_claim_before_its_executor_calls(
    tmp_path: Path,
) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
    )
    spec = _spec(fixture)
    artifacts_root = tmp_path / "concurrent-repair-artifacts"
    started = threading.Event()
    release = threading.Event()

    class BlockingExecutor(RewardByTurnsHarborExecutor):
        def execute(self, *, command: list[str], cwd: Path) -> int:
            started.set()
            if not release.wait(timeout=10):
                raise RuntimeError("test did not release the claimed repair execution")
            return super().execute(command=command, cwd=cwd)

    first_executor = BlockingExecutor(emit_turn_limit_failure=True)
    second_executor = RewardByTurnsHarborExecutor(emit_turn_limit_failure=True)
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(
            run_repair,
            spec=spec,
            registry=fixture.registry,
            workflow=fixture.workflow,
            artifacts_root=artifacts_root,
            executor=first_executor,
        )
        assert started.wait(timeout=10)
        try:
            with pytest.raises(RepairAttemptClaimError, match="incomplete or active"):
                run_repair(
                    spec=spec,
                    registry=fixture.registry,
                    workflow=fixture.workflow,
                    artifacts_root=artifacts_root,
                    executor=second_executor,
                )
        finally:
            release.set()
        first.result(timeout=20)

    assert second_executor.calls == []
    assert first_executor.calls == [(17, 1), (29, 1), (17, 2), (29, 2)]


def test_repair_runner_refuses_different_spec_reusing_claimed_attempt_identity(
    tmp_path: Path,
) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
    )
    spec = _spec(fixture)
    artifacts_root = tmp_path / "divergent-repair-artifacts"
    executor = RewardByTurnsHarborExecutor(emit_turn_limit_failure=True)
    run_repair(
        spec=spec,
        registry=fixture.registry,
        workflow=fixture.workflow,
        artifacts_root=artifacts_root,
        executor=executor,
    )
    calls_after_first_run = tuple(executor.calls)
    divergent_spec = RepairRunSpec(
        **spec.model_dump(
            mode="python",
            exclude={"content_sha256", "policy_id"},
        ),
        policy_id="policy.repair-only.divergent",
    )

    with pytest.raises(RepairAttemptClaimError, match="different exact RepairRunSpec"):
        run_repair(
            spec=divergent_spec,
            registry=fixture.registry,
            workflow=fixture.workflow,
            artifacts_root=artifacts_root,
            executor=executor,
        )

    assert tuple(executor.calls) == calls_after_first_run


def test_repair_runner_refuses_unsafe_resume_from_incomplete_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
    )
    spec = _spec(fixture)
    artifacts_root = tmp_path / "orphaned-repair-artifacts"
    executor = RewardByTurnsHarborExecutor(emit_turn_limit_failure=True)
    execute = RepairRuntime.execute

    def interrupt_after_claim(_runtime: RepairRuntime) -> None:
        raise RuntimeError("simulated process interruption after attempt claim")

    monkeypatch.setattr(RepairRuntime, "execute", interrupt_after_claim)
    with pytest.raises(RuntimeError, match="simulated process interruption"):
        run_repair(
            spec=spec,
            registry=fixture.registry,
            workflow=fixture.workflow,
            artifacts_root=artifacts_root,
            executor=executor,
        )
    monkeypatch.setattr(RepairRuntime, "execute", execute)

    with pytest.raises(RepairAttemptClaimError, match="incomplete or active"):
        run_repair(
            spec=spec,
            registry=fixture.registry,
            workflow=fixture.workflow,
            artifacts_root=artifacts_root,
            executor=executor,
        )

    assert executor.calls == []
    _claim_path, completion_path = _only_attempt_claim_paths(artifacts_root, require_completion=False)
    assert not completion_path.exists()


def test_new_attempt_repeats_complete_pair_after_interrupted_parent_under_same_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
    )
    first_spec = _spec(fixture)
    artifacts_root = tmp_path / "interrupted-parent-artifacts"

    first_executor = RewardByTurnsHarborExecutor(emit_turn_limit_failure=True)
    verify = RepairRuntime._verify

    def interrupt_after_parent_verification(
        self: RepairRuntime,
        candidate: CompiledRepairCandidate,
        run: RepairRunResult,
    ) -> None:
        verify(self, candidate, run)
        raise RuntimeError("simulated process interruption after complete parent arm")

    monkeypatch.setattr(RepairRuntime, "_verify", interrupt_after_parent_verification)
    with pytest.raises(RepairLoopError, match="after complete parent arm"):
        run_repair(
            spec=first_spec,
            registry=fixture.registry,
            workflow=fixture.workflow,
            artifacts_root=artifacts_root,
            executor=first_executor,
        )
    monkeypatch.setattr(RepairRuntime, "_verify", verify)

    first_record_bytes = {path: path.read_bytes() for path in sorted(fixture.workflow.ledger_root.rglob("*.json"))}
    first_records = tuple(
        read_trial_record(path) for path in sorted(fixture.workflow.ledger_root.rglob("trial-*.json"))
    )
    assert len(first_records) == 2
    assert first_executor.calls == [(17, 1), (29, 1)]

    second_request = first_spec.request.model_copy(update={"attempt_id": f"{first_spec.request.loop_id}.attempt-2"})
    second_spec = RepairRunSpec(
        **first_spec.model_dump(mode="python", exclude={"content_sha256", "request"}),
        request=second_request,
    )
    second_executor = RewardByTurnsHarborExecutor(emit_turn_limit_failure=True)
    second_result = run_repair(
        spec=second_spec,
        registry=fixture.registry,
        workflow=fixture.workflow,
        artifacts_root=artifacts_root,
        executor=second_executor,
    )

    claim_paths = tuple(sorted((artifacts_root / "repair-attempt-claims").glob("*/claim.json")))
    completion_paths = tuple(path.with_name("completion.json") for path in claim_paths)
    records = tuple(
        read_trial_record(path) for path in sorted(fixture.workflow.ledger_root.rglob("trial-*.json"))
    )
    assert second_result.result.status is RepairLoopStatus.ACCEPTED
    assert second_executor.calls == [(17, 1), (29, 1), (17, 2), (29, 2)]
    assert len(claim_paths) == 2
    assert sum(path.is_file() for path in completion_paths) == 1
    assert all(path.read_bytes() == content for path, content in first_record_bytes.items())
    assert len(records) == 6
    assert {
        record.meta_harness_provenance.repair_attempt_id
        for record in records
        if record.meta_harness_provenance is not None
    } == {first_spec.request.attempt_id, second_spec.request.attempt_id}


def test_repair_runner_refuses_corrupt_attempt_claim_before_executor_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
    )
    spec = _spec(fixture)
    artifacts_root = tmp_path / "corrupt-claim-repair-artifacts"
    executor = RewardByTurnsHarborExecutor(emit_turn_limit_failure=True)
    execute = RepairRuntime.execute
    monkeypatch.setattr(
        RepairRuntime,
        "execute",
        lambda _runtime: (_ for _ in ()).throw(RuntimeError("simulated process interruption")),
    )
    with pytest.raises(RuntimeError, match="simulated process interruption"):
        run_repair(
            spec=spec,
            registry=fixture.registry,
            workflow=fixture.workflow,
            artifacts_root=artifacts_root,
            executor=executor,
        )
    monkeypatch.setattr(RepairRuntime, "execute", execute)
    claim_path, _completion_path = _only_attempt_claim_paths(artifacts_root, require_completion=False)
    claim_path.write_text("{not-json\n", encoding="utf-8")

    with pytest.raises(RepairAttemptClaimError, match="claim is corrupt"):
        run_repair(
            spec=spec,
            registry=fixture.registry,
            workflow=fixture.workflow,
            artifacts_root=artifacts_root,
            executor=executor,
        )

    assert executor.calls == []


def test_repair_runner_refuses_corrupt_completion_receipt_before_new_executor_calls(
    tmp_path: Path,
) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
    )
    spec = _spec(fixture)
    artifacts_root = tmp_path / "corrupt-completion-repair-artifacts"
    executor = RewardByTurnsHarborExecutor(emit_turn_limit_failure=True)
    run_repair(
        spec=spec,
        registry=fixture.registry,
        workflow=fixture.workflow,
        artifacts_root=artifacts_root,
        executor=executor,
    )
    calls_after_first_run = tuple(executor.calls)
    _claim_path, completion_path = _only_attempt_claim_paths(artifacts_root)
    completion_path.write_text("{not-json\n", encoding="utf-8")

    with pytest.raises(RepairAttemptClaimError, match="completion receipt is corrupt"):
        run_repair(
            spec=spec,
            registry=fixture.registry,
            workflow=fixture.workflow,
            artifacts_root=artifacts_root,
            executor=executor,
        )

    assert tuple(executor.calls) == calls_after_first_run


def test_repair_runner_refuses_cross_attempt_terminal_substitution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
    )
    source_spec = _spec(fixture)
    source_execution = run_repair(
        spec=source_spec,
        registry=fixture.registry,
        workflow=fixture.workflow,
        artifacts_root=tmp_path / "source-attempt-artifacts",
        executor=RewardByTurnsHarborExecutor(emit_turn_limit_failure=True),
    )
    target_request = source_spec.request.model_copy(
        update={
            "loop_id": "repair-runtime.substitution-target-loop",
            "attempt_id": "repair-runtime.substitution-target-attempt",
        }
    )
    target_spec = RepairRunSpec(
        **source_spec.model_dump(
            mode="python",
            exclude={"content_sha256", "request"},
        ),
        request=target_request,
    )
    target_artifacts = tmp_path / "target-attempt-artifacts"
    target_executor = RewardByTurnsHarborExecutor(emit_turn_limit_failure=True)

    def substitute_terminal(runtime: RepairRuntime) -> RepairRuntimeExecution:
        return RepairRuntimeExecution(
            result=source_execution.result,
            attempt_plan=runtime.attempt_plan,
            run_artifacts=source_execution.run_artifacts,
            terminal=source_execution.terminal,
        )

    monkeypatch.setattr(RepairRuntime, "execute", substitute_terminal)

    with pytest.raises(RepairAttemptClaimError, match="terminal result identity does not match"):
        run_repair(
            spec=target_spec,
            registry=fixture.registry,
            workflow=fixture.workflow,
            artifacts_root=target_artifacts,
            executor=target_executor,
        )

    assert target_executor.calls == []
    _claim_path, completion_path = _only_attempt_claim_paths(target_artifacts, require_completion=False)
    assert not completion_path.exists()


def test_prepare_repair_run_spec_pins_exact_task_and_world_snapshots(tmp_path: Path) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
    )
    task_dir = fixture.tasks_root / fixture.request.pairing.task_ids[0]
    (task_dir / "task-review.json").write_text(
        json.dumps(
            {
                "profile_id": "aec.task-review.civil.repair",
                "name": "Repair task review",
                "task_unit": "paired-repair-task",
                "logic_profile": {"agentic_review": {"required": True}},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    spec = _spec(fixture)

    assert tuple(snapshot.task_id for snapshot in spec.task_snapshots) == fixture.request.pairing.task_ids
    assert spec.task_snapshots[0].task_review is not None
    assert spec.task_snapshots[0].task_review.profile_id == "aec.task-review.civil.repair"


@pytest.mark.parametrize("drift_kind", ("task", "task_review"))
def test_repair_runner_rejects_task_review_drift_before_harbor_dispatch(
    tmp_path: Path,
    drift_kind: str,
) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
    )
    task_dir = fixture.tasks_root / fixture.request.pairing.task_ids[0]
    review_path = task_dir / "task-review.json"
    if drift_kind == "task_review":
        review_path.write_text(
            json.dumps(
                {
                    "profile_id": "aec.task-review.civil.repair",
                    "name": "Repair task review",
                    "task_unit": "paired-repair-task",
                    "logic_profile": {"agentic_review": {"required": True}},
                }
            )
            + "\n",
            encoding="utf-8",
        )
    spec = _spec(fixture)
    if drift_kind == "task":
        (task_dir / "instruction.md").write_text("Changed after repair preregistration.\n", encoding="utf-8")
    else:
        review_payload = json.loads(review_path.read_text(encoding="utf-8"))
        review_payload["name"] = "Changed repair task review"
        review_path.write_text(json.dumps(review_payload) + "\n", encoding="utf-8")
    executor = RewardByTurnsHarborExecutor(emit_turn_limit_failure=True)

    with pytest.raises(ValueError, match="repair spec task/task-review snapshots drifted before execution"):
        run_repair(
            spec=spec,
            registry=fixture.registry,
            workflow=fixture.workflow,
            artifacts_root=tmp_path / "drift-artifacts",
            executor=executor,
        )

    assert executor.calls == []


def test_repair_runtime_rechecks_preregistered_snapshots_at_compile_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
    )
    spec = _spec(fixture)
    task_instruction = fixture.tasks_root / fixture.request.pairing.task_ids[0] / "instruction.md"
    task_instruction.write_text("Changed after the top-level snapshot check.\n", encoding="utf-8")
    executor = RewardByTurnsHarborExecutor(emit_turn_limit_failure=True)
    monkeypatch.setattr(
        "aec_bench.experimentation.qualification.repair_run.resolve_task_snapshots",
        lambda **_kwargs: spec.task_snapshots,
    )

    with pytest.raises(RepairLoopError, match="repair spec task/task-review snapshots drifted before execution"):
        run_repair(
            spec=spec,
            registry=fixture.registry,
            workflow=fixture.workflow,
            artifacts_root=tmp_path / "compile-drift-artifacts",
            executor=executor,
        )

    assert executor.calls == []


def test_repair_attempt_and_terminal_bind_the_persisted_exact_spec(tmp_path: Path) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("fixture diagnosis must not run")),
    )
    spec = _spec(fixture)
    artifacts_root = tmp_path / "lineage-artifacts"

    result = run_repair(
        spec=spec,
        registry=fixture.registry,
        workflow=fixture.workflow,
        artifacts_root=artifacts_root,
        executor=RewardByTurnsHarborExecutor(emit_turn_limit_failure=True),
    )

    plan = RepairAttemptPlan.model_validate_json(result.attempt_plan.path.read_text(encoding="utf-8"))
    terminal = RepairTerminalRecord.model_validate_json(result.terminal.path.read_text(encoding="utf-8"))
    assert plan.repair_run_spec is not None
    persisted_spec_path = Path(plan.repair_run_spec.path)
    assert persisted_spec_path.is_relative_to(artifacts_root / "repair-specs")
    assert RepairRunSpec.model_validate_json(persisted_spec_path.read_text(encoding="utf-8")) == spec
    assert terminal.repair_run_spec == plan.repair_run_spec
    assert terminal.attempt_plan_sha256 == result.attempt_plan.reference.sha256


def _spec(fixture: RepairRuntime) -> RepairRunSpec:
    return prepare_repair_run_spec(
        request=fixture.request,
        parent=fixture.parent,
        verifier_policy=RepairVerifierPolicy(minimum_reward=0.8),
        evidence_use_policy=RepairEvidenceUsePolicy.exploratory_matched_repair(),
        diagnosis_rule=AdaptiveDiagnosisPolicy(rules=(HarnessMaxTurnsDiagnosisRule(binding_id="agent", max_turns=2),)),
        policy_id="policy.repair-only",
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        tasks_root=fixture.tasks_root,
        registry=fixture.registry,
    )


def _only_attempt_claim_paths(
    artifacts_root: Path,
    *,
    require_completion: bool = True,
) -> tuple[Path, Path]:
    claim_paths = tuple((artifacts_root / "repair-attempt-claims").glob("*/claim.json"))
    assert len(claim_paths) == 1
    claim_path = claim_paths[0]
    completion_path = claim_path.with_name("completion.json")
    if require_completion:
        assert completion_path.is_file()
    return claim_path, completion_path
