# ABOUTME: Exercises verifier-guided repair through real compilation, RunPlan execution, and TrialRecords.
# ABOUTME: Proves seeded paired reruns, typed Hx patches, artifact integrity, and world-drift rejection.

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

from aec_bench.adapters.base import AdapterFailureKind, AdapterStopReason
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityPrincipal,
    AuthorityPrincipalKind,
    BasisKind,
    TaintLabel,
)
from aec_bench.contracts.execution_program import (
    ActionNode,
    ExecutionProgramRef,
    JoinNode,
    LiteralValue,
    ProgramArgument,
    ProgramLimits,
    RetryPolicy,
    StopNode,
    StopOutcome,
)
from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    ComputeBindingConfig,
    HarnessBindingSpec,
    HarnessBudget,
    HarnessCompileRequest,
    HarnessSpec,
    HarnessTopologyRole,
    ResultImportBindingConfig,
    TaskSourceBindingConfig,
    VerificationBindingConfig,
)
from aec_bench.contracts.harness_kernel import KernelRef, canonical_json_sha256
from aec_bench.contracts.output_completion import (
    OutputCommitAttestation,
    OutputCompletionEvaluation,
    OutputCompletionReason,
)
from aec_bench.contracts.task_review_snapshot import ReviewSnapshot
from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.evolution.paired_repair import RepairAcceptancePolicy
from aec_bench.evolution.repair_lifecycle import (
    RepairCandidate,
    RepairFailureDomain,
    RepairLoopError,
    RepairLoopRequest,
    RepairLoopResult,
    RepairLoopStage,
    RepairLoopStatus,
    RepairOwner,
    RepairPairingSpec,
    RepairProgramTemplate,
    RepairRewardCoverage,
)
from aec_bench.experimentation.governance.authority_ledger import AuthorityLedger
from aec_bench.experimentation.qualification.motif_learning import capture_accepted_repair_evidence
from aec_bench.experimentation.qualification.repair_runtime import (
    DiagnosisFunction,
    HarnessAgentCapabilityPatch,
    HarnessAgentMaxTurnsPatch,
    ProgramCoalesceTaskBatchPatch,
    ProgramMaterializeDeclaredStageGraphPatch,
    ProgramMaxTotalAttemptsPatch,
    ProgramNodeRetryPatch,
    RepairAttemptPlan,
    RepairDeclaredStageGraphEvidence,
    RepairEvidenceUsePolicy,
    RepairNoPatchProposal,
    RepairOutputArtifactEvidence,
    RepairPatchProposal,
    RepairRunArtifactManifest,
    RepairRuntime,
    RepairRuntimeEvidence,
    RepairRuntimeExecution,
    RepairTerminalRecord,
    RepairVerifierPolicy,
    StoredRepairArtifact,
    _has_output_commit_attestation,
    _patch_agent_capability,
    _patch_program_retry,
    _repair_output_artifact_evidence,
    diagnose_harness_agent_capability,
    diagnose_harness_turn_limit,
    diagnose_program_attempt_limit,
    diagnose_program_batch_coalescing,
    diagnose_program_declared_stage_graph_materialization,
    diagnose_program_retry,
    materialize_program_declared_stage_graph,
)
from aec_bench.experimentation.qualification.run_bundle_runtime import (
    _operation_definition_for_dispatch,
    load_harbor_invocation_receipt,
)
from aec_bench.harness.harbor_dispatch import HarborCommandExecutor
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.harness.kernel_catalogue import (
    KernelRuntimeRegistry,
    default_kernel_registry,
)
from aec_bench.harness.program_execution import ProgramExecutionStatus
from tests.support.adaptive_harness import runtime_attestation_for_harbor_agent

_STRUCTURALLY_COMPLETE_OUTPUT = '# Result\n```json\n{"answer": 42}\n```\n'


class RewardByTurnsHarborExecutor:
    """Materialize real Harbor result files with reward determined by lowered Hx turns."""

    def __init__(
        self,
        *,
        include_cost: bool = True,
        emit_turn_limit_failure: bool = False,
        resource_stop: AdapterStopReason | None = None,
        include_runtime_turn_evidence: bool = True,
        verifier_error: str | None = None,
        reviewer_event_candidates: tuple[str, ...] = (),
    ) -> None:
        self.calls: list[tuple[int, int]] = []
        self._lock = threading.Lock()
        self.include_cost = include_cost
        self.emit_turn_limit_failure = emit_turn_limit_failure
        self.resource_stop = resource_stop
        self.include_runtime_turn_evidence = include_runtime_turn_evidence
        self.verifier_error = verifier_error
        self.reviewer_event_candidates = reviewer_event_candidates

    def execute(self, *, command: list[str], cwd: Path) -> int:
        config = yaml.safe_load(Path(command[-1]).read_text(encoding="utf-8"))
        agent = config["agents"][0]
        kwargs: dict[str, Any] = agent["kwargs"]
        turns = int(kwargs["max_turns"])
        seed = int(kwargs["execution_seed"])
        assert config["n_attempts"] == 1
        with self._lock:
            self.calls.append((seed, turns))
            call_index = len(self.calls)

        jobs_dir = Path(config["jobs_dir"])
        for task_index, task in enumerate(config["tasks"], start=1):
            stop_reason = self._stop_reason(kwargs=kwargs, turns=turns)
            failure_kind = (
                {
                    AdapterStopReason.ITERATION_CAP: AdapterFailureKind.TURN_LIMIT_REACHED,
                    AdapterStopReason.TOKEN_BUDGET: AdapterFailureKind.TOKEN_BUDGET_REACHED,
                    AdapterStopReason.SUBCALL_LIMIT: AdapterFailureKind.SUBCALL_LIMIT_REACHED,
                    AdapterStopReason.COST_BUDGET: AdapterFailureKind.COST_BUDGET_REACHED,
                    AdapterStopReason.BILLABLE_INPUT_BUDGET: AdapterFailureKind.BILLABLE_INPUT_BUDGET_REACHED,
                    AdapterStopReason.CONTEXT_LIMIT: AdapterFailureKind.CONTEXT_LIMIT_REACHED,
                }[stop_reason]
                if stop_reason is not None
                else None
            )
            trial_name = f"trial-repair-{call_index}-{task_index}"
            trial_dir = jobs_dir / f"job-repair-{call_index}" / trial_name
            (trial_dir / "artifacts" / "agent").mkdir(parents=True)
            (trial_dir / "verifier").mkdir(parents=True)
            (trial_dir / "artifacts" / "agent" / "output.md").write_text(
                _STRUCTURALLY_COMPLETE_OUTPUT,
                encoding="utf-8",
            )
            (trial_dir / "artifacts" / "agent" / "agent_result.json").write_text(
                json.dumps(
                    {
                        "status": "partial" if stop_reason is not None else "completed",
                        "usage_model_calls": turns,
                        "input_tokens": 10,
                        "output_tokens": 2,
                        "usage_cache_read_tokens": 0,
                        "usage_cache_write_tokens": 0,
                        "turns_used": turns if self.include_runtime_turn_evidence else None,
                        "max_turns": turns if self.include_runtime_turn_evidence else None,
                        "failure_kind": failure_kind.value if failure_kind is not None else None,
                        "stop_reason": stop_reason.value if stop_reason is not None else None,
                        "completion_reason": self._completion_reason(kwargs=kwargs, turns=turns),
                        "completion_assistance": self._completion_assistance(kwargs=kwargs, turns=turns),
                        "provider_error": f"{stop_reason.value} reached" if stop_reason is not None else None,
                    }
                ),
                encoding="utf-8",
            )
            reward = self._reward(kwargs=kwargs, turns=turns)
            (trial_dir / "verifier" / "reward.json").write_text(
                json.dumps({"reward": 0.0 if self.verifier_error else reward}),
                encoding="utf-8",
            )
            verifier_details = (
                {
                    "passed": False,
                    "reward_owner": "harbor_verifier",
                    "error": self.verifier_error,
                }
                if self.verifier_error
                else {
                    "gates": {
                        "task_result": {
                            "passed": reward >= 0.5,
                            "score": reward,
                        }
                    }
                }
            )
            (trial_dir / "verifier" / "details.json").write_text(
                json.dumps(verifier_details),
                encoding="utf-8",
            )
            if self.reviewer_event_candidates:
                (trial_dir / "reviewer").mkdir()
                (trial_dir / "reviewer" / "summary.json").write_text(
                    json.dumps(
                        {
                            "enabled": True,
                            "required": True,
                            "status": "complete",
                            "model_count": 1,
                            "complete_count": 1,
                            "error_count": 0,
                            "event_candidates": list(self.reviewer_event_candidates),
                            "models": [],
                        }
                    ),
                    encoding="utf-8",
                )
            (trial_dir / "result.json").write_text(
                json.dumps(
                    {
                        "trial_name": trial_name,
                        "task_checksum": "sha256-task",
                        "config": {
                            "task": {"path": str(task["path"])},
                            "agent": agent,
                            "environment": {"type": "docker", "kwargs": {}},
                            "job_id": f"harbor-job-repair-{call_index}",
                        },
                        "agent_info": {"name": "entrypoint", "version": "1.0.0"},
                        "agent_result": {
                            **({"cost_usd": self._cost_usd(kwargs=kwargs, turns=turns)} if self.include_cost else {}),
                            "metadata": {
                                "runtime_execution_attestation": runtime_attestation_for_harbor_agent(
                                    agent,
                                    instruction=self._effective_instruction(
                                        kwargs=kwargs,
                                        original=(cwd / str(task["path"]) / "instruction.md").read_text(
                                            encoding="utf-8"
                                        ),
                                    ),
                                )
                            },
                        },
                        "started_at": "2026-07-22T00:00:00Z",
                        "finished_at": "2026-07-22T00:00:01Z",
                    }
                ),
                encoding="utf-8",
            )
        return 0

    def _reward(self, *, kwargs: dict[str, Any], turns: int) -> float:
        del kwargs
        return 0.2 if turns == 1 else 0.9

    def _stop_reason(self, *, kwargs: dict[str, Any], turns: int) -> AdapterStopReason | None:
        del kwargs
        if self.resource_stop is not None:
            return self.resource_stop
        if self.emit_turn_limit_failure and turns == 1:
            return AdapterStopReason.ITERATION_CAP
        return None

    def _cost_usd(self, *, kwargs: dict[str, Any], turns: int) -> float:
        del kwargs, turns
        return 0.001

    def _completion_reason(self, *, kwargs: dict[str, Any], turns: int) -> str | None:
        del kwargs, turns
        return None

    def _completion_assistance(self, *, kwargs: dict[str, Any], turns: int) -> dict[str, object] | None:
        del kwargs, turns
        return None

    def _effective_instruction(self, *, kwargs: dict[str, Any], original: str) -> str:
        override = kwargs.get("kernel_instruction_override")
        if isinstance(override, dict) and isinstance(override.get("effective_instruction"), str):
            return str(override["effective_instruction"])
        return original


class CapabilityCompletionHarborExecutor(RewardByTurnsHarborExecutor):
    """Emit matched evidence where only the selected adapter capability changes completion."""

    def __init__(
        self,
        *,
        report_contract_completion_reason: bool = True,
        report_completion_assistance: bool = True,
    ) -> None:
        super().__init__()
        self.adapters: list[str] = []
        self.report_contract_completion_reason = report_contract_completion_reason
        self.report_completion_assistance = report_completion_assistance

    def _stop_reason(self, *, kwargs: dict[str, Any], turns: int) -> AdapterStopReason | None:
        del turns
        adapter = "rlm-contract" if "output_completion_contract" in kwargs else "rlm-explicit"
        self.adapters.append(adapter)
        return AdapterStopReason.ITERATION_CAP if adapter == "rlm-explicit" else None

    def _reward(self, *, kwargs: dict[str, Any], turns: int) -> float:
        del kwargs, turns
        return 0.9

    def _cost_usd(self, *, kwargs: dict[str, Any], turns: int) -> float:
        del turns
        return 0.001 if "output_completion_contract" in kwargs else 0.002

    def _completion_reason(self, *, kwargs: dict[str, Any], turns: int) -> str | None:
        del turns
        if self.report_contract_completion_reason and "output_completion_contract" in kwargs:
            return "output_contract_satisfied"
        return None

    def _completion_assistance(self, *, kwargs: dict[str, Any], turns: int) -> dict[str, object] | None:
        if not self.report_completion_assistance or "output_completion_contract" not in kwargs:
            return None
        return {
            "contract_satisfied": True,
            "reminder_sent": True,
            "reminder_turn": turns - 1,
            "explicit_final_turn": turns,
        }


class DeclaredStageHarborExecutor(RewardByTurnsHarborExecutor):
    """Emit exact declared-stage payloads while retaining real Harbor result boundaries."""

    def execute(self, *, command: list[str], cwd: Path) -> int:
        return_code = super().execute(command=command, cwd=cwd)
        config = yaml.safe_load(Path(command[-1]).read_text(encoding="utf-8"))
        agent = config["agents"][0]
        override = agent["kwargs"].get("kernel_instruction_override")
        if not isinstance(override, dict) or override.get("mode") != "declared_stage":
            return return_code
        task_id = str(override["task_id"])
        stage_id = str(override["stage_id"])
        outputs_by_stage = {
            "inventory": {"source_inventory": {"status": "catalogued"}},
            "authority": {"provenance_ledger": {"status": "governing"}},
            "decision": {"readiness_decision": "ready_with_carried_actions"},
        }
        output_paths = tuple(Path(config["jobs_dir"]).rglob("artifacts/agent/output.md"))
        assert len(output_paths) == 1
        output_paths[0].write_text(
            "# Stage result\n```json\n"
            + json.dumps(
                {
                    "schema_version": "aecbench.stage-output.v1",
                    "task_id": task_id,
                    "stage_id": stage_id,
                    "outputs": outputs_by_stage[stage_id],
                },
                sort_keys=True,
            )
            + "\n```\n",
            encoding="utf-8",
        )
        return return_code


class FailingHarborExecutor:
    """Fail after dispatch starts without inventing a Harbor TrialRecord."""

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, *, command: list[str], cwd: Path) -> int:
        del command, cwd
        self.calls += 1
        raise RuntimeError("Harbor process exited before writing trials")


class ChildDispatchFailingHarborExecutor(RewardByTurnsHarborExecutor):
    """Materialize the diagnostic parent, then fail every patched child dispatch."""

    def execute(self, *, command: list[str], cwd: Path) -> int:
        config = yaml.safe_load(Path(command[-1]).read_text(encoding="utf-8"))
        kwargs: dict[str, Any] = config["agents"][0]["kwargs"]
        turns = int(kwargs["max_turns"])
        seed = int(kwargs["execution_seed"])
        if turns > 1:
            with self._lock:
                self.calls.append((seed, turns))
            raise RuntimeError("Harbor child process exited before writing trials")
        return super().execute(command=command, cwd=cwd)


class SuccessfulTaskSelectedHarborExecutor(RewardByTurnsHarborExecutor):
    """Materialize successful evidence while retaining each px-selected task call."""

    def __init__(self) -> None:
        super().__init__()
        self.task_selections: list[tuple[str, ...]] = []

    def execute(self, *, command: list[str], cwd: Path) -> int:
        config = yaml.safe_load(Path(command[-1]).read_text(encoding="utf-8"))
        self.task_selections.append(tuple(str(task["path"]) for task in config["tasks"]))
        return super().execute(command=command, cwd=cwd)

    def _reward(self, *, kwargs: dict[str, Any], turns: int) -> float:
        del kwargs, turns
        return 0.9


def test_repair_runtime_executes_seeded_parent_child_pair_and_preserves_lineage(
    tmp_path: Path,
) -> None:
    runtime, executor = _runtime(tmp_path)

    execution = runtime.execute()

    result = execution.result
    assert result.status is RepairLoopStatus.ACCEPTED
    assert result.diagnosis is not None
    assert result.diagnosis.owner is RepairOwner.HARNESS
    assert result.decision is not None and result.decision.accepted
    assert executor.calls == [(17, 1), (29, 1), (17, 2), (29, 2)]
    assert len(execution.run_artifacts) == 2
    terminal_payload = json.loads(execution.terminal.path.read_text(encoding="utf-8"))
    assert terminal_payload["diagnosis_evidence"]["candidate_id"] == result.parent_candidate_id
    assert terminal_payload["patch_proposal"]["patch"] == {
        "binding_id": "agent",
        "kind": "harness_agent_max_turns",
        "max_turns": 2,
    }
    terminal = RepairTerminalRecord.model_validate(terminal_payload)
    assert terminal.diagnosis_evidence is not None
    parent_trial = terminal.diagnosis_evidence.trials[0]
    assert parent_trial.agent.status is AgentOutputStatus.COMPLETED
    assert parent_trial.agent.max_turns == 1
    assert parent_trial.agent.turns_used == 1
    assert parent_trial.agent.failure_kind is None
    assert parent_trial.verifier.breakdown == {"gates": {"task_result": {"passed": False, "score": 0.2}}}
    assert (
        parent_trial.verifier.breakdown_sha256
        == hashlib.sha256(
            json.dumps(
                parent_trial.verifier.breakdown,
                allow_nan=False,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
    )
    assert [item.status for item in terminal.diagnosis_evidence.program_executions] == [
        ProgramExecutionStatus.SUCCEEDED,
        ProgramExecutionStatus.SUCCEEDED,
    ]
    assert execution.attempt_plan.reference.sha256 in [
        artifact.artifact.sha256
        for run_artifact in execution.run_artifacts
        for record in runtime.verified_records(run_artifact.run_id)
        for artifact in (record.outputs.artifacts or [])
        if artifact.role == execution.attempt_plan.reference.kind
    ]

    parent = result.parent_verification
    child = result.child_verification
    assert child is not None
    assert [item.seed for item in parent.observations] == [17, 29]
    assert [item.seed for item in child.observations] == [17, 29]
    assert {item.outcome.reward for item in parent.observations} == {0.2}
    assert {item.outcome.reward for item in child.observations} == {0.9}
    assert all(
        item.outcome.kernel_ref == runtime.registry.manifest.ref for item in (*parent.observations, *child.observations)
    )


def test_accepted_repair_receives_authority_only_after_terminal_persistence(
    tmp_path: Path,
) -> None:
    artifacts_root = tmp_path / "meta-harness-artifacts"
    authority_ledger = AuthorityLedger(
        tmp_path / "authority",
        candidate_roots=(artifacts_root,),
    )
    runtime = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda evidence: RepairPatchProposal(
            owner=RepairOwner.HARNESS,
            code="insufficient_turn_budget",
            message=f"{len(evidence.trials)} verifier outcomes failed under the Hx turn limit.",
            patch=HarnessAgentMaxTurnsPatch(binding_id="agent", max_turns=2),
        ),
        authority_ledger=authority_ledger,
    )

    execution = runtime.execute()

    assert execution.result.status is RepairLoopStatus.ACCEPTED
    assert execution.terminal.path.exists()
    assert execution.authority_error is None
    assert execution.authority_event is not None
    assert execution.authority_event.event.action is AuthorityAction.REPAIR_ACCEPTANCE
    assert execution.authority_event.event.subject_sha256 == execution.terminal.reference.sha256
    terminal_basis_reference = next(
        basis
        for basis in execution.authority_event.event.basis
        if basis.artifact_id == execution.authority_event.event.subject_id
    )
    assert terminal_basis_reference.artifact_sha256 == execution.terminal.reference.sha256
    assert (
        authority_ledger.resolve_basis(terminal_basis_reference).content_path.read_bytes()
        == execution.terminal.path.read_bytes()
    )
    assert (
        authority_ledger.resolve_authority_event(
            event_id=execution.authority_event.event.event_id,
            content_sha256=execution.authority_event.event.content_sha256,
        )
        == execution.authority_event
    )


def test_repair_acceptance_authority_failure_preserves_terminal_evidence(
    tmp_path: Path,
) -> None:
    artifacts_root = tmp_path / "meta-harness-artifacts"
    authority_ledger = AuthorityLedger(
        tmp_path / "authority",
        candidate_roots=(artifacts_root,),
    )
    runtime = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda evidence: RepairPatchProposal(
            owner=RepairOwner.HARNESS,
            code="insufficient_turn_budget",
            message=f"{len(evidence.trials)} verifier outcomes failed under the Hx turn limit.",
            patch=HarnessAgentMaxTurnsPatch(binding_id="agent", max_turns=2),
        ),
        authority_ledger=authority_ledger,
    )
    host_runtime = AuthorityPrincipal(
        principal_id="host.runtime",
        kind=AuthorityPrincipalKind.HOST_RUNTIME,
    )
    authority_ledger.observe_basis(
        kind=BasisKind.EVIDENCE,
        artifact_id=f"repair-attempt-plan.{runtime.request.loop_id}.{runtime.request.attempt_id}",
        content=b"conflicting repair plan identity\n",
        producer=host_runtime,
        producer_process_id="test-conflicting-plan",
        observed_by=host_runtime,
        channel="repair-runtime",
        operation_id="repair-plan-persistence",
        invocation_id=runtime.request.attempt_id,
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )

    execution = runtime.execute()

    assert execution.result.status is RepairLoopStatus.ACCEPTED
    assert execution.terminal.path.exists()
    assert execution.authority_event is None
    assert execution.authority_error is not None
    assert execution.authority_error.startswith("repair_acceptance_authority_failed:")


def test_repair_runtime_executes_capability_repair_with_cost_non_inferiority_gate(
    tmp_path: Path,
) -> None:
    registry = default_kernel_registry()
    executor = CapabilityCompletionHarborExecutor()
    runtime = _build_runtime(
        tmp_path,
        executor=executor,
        diagnosis=lambda evidence: diagnose_harness_agent_capability(
            evidence,
            binding_id="agent",
            expected_capability_ref=registry.capability("aecbench.adapter.rlm-uncached").ref,
            replacement_capability_ref=registry.capability("aecbench.adapter.rlm-output-contract").ref,
        ),
        acceptance_policy=RepairAcceptancePolicy(
            minimum_mean_reward_delta=-0.01,
            require_positive_lower_bound=False,
            maximum_cost_ratio=0.75,
            bootstrap_replicates=32,
        ),
        agent_capability_id="aecbench.adapter.rlm-uncached",
        agent_max_turns=2,
    )

    execution = runtime.execute()

    assert execution.result.status is RepairLoopStatus.ACCEPTED
    assert executor.adapters == ["rlm-explicit", "rlm-explicit", "rlm-contract", "rlm-contract"]
    assert execution.result.decision is not None
    assert execution.result.decision.cost_ratio == pytest.approx(0.5)
    terminal = RepairTerminalRecord.model_validate_json(execution.terminal.path.read_text(encoding="utf-8"))
    assert terminal.patch_proposal is not None
    assert isinstance(terminal.patch_proposal.patch, HarnessAgentCapabilityPatch)
    assert terminal.diagnosis_evidence is not None
    assert all(trial.agent.output_artifact is not None for trial in terminal.diagnosis_evidence.trials)
    assert all(
        trial.agent.output_artifact.size_bytes == len(_STRUCTURALLY_COMPLETE_OUTPUT.encode("utf-8"))
        for trial in terminal.diagnosis_evidence.trials
        if trial.agent.output_artifact is not None
    )
    assert all(
        trial.agent.output_artifact.completion_evaluation.complete
        for trial in terminal.diagnosis_evidence.trials
        if trial.agent.output_artifact is not None
    )

    for run_artifact in execution.run_artifacts:
        records = runtime.verified_records(run_artifact.run_id)
        assert len(records) == 2
        for record in records:
            provenance = record.meta_harness_provenance
            assert provenance is not None
            assert provenance.repair_attempt_id == runtime.request.attempt_id
            assert provenance.repair_iteration == runtime.request.iteration
            assert provenance.repair_decision == execution.attempt_plan.reference
            assert provenance.execution_seed in runtime.request.pairing.seeds
            if run_artifact.candidate_id == runtime.request.child_candidate_id:
                assert provenance.parent_plan_run_id is not None


def test_capability_repair_rejects_child_that_completed_without_exercising_output_contract(
    tmp_path: Path,
) -> None:
    registry = default_kernel_registry()
    executor = CapabilityCompletionHarborExecutor(report_contract_completion_reason=False)
    runtime = _build_runtime(
        tmp_path,
        executor=executor,
        diagnosis=lambda evidence: diagnose_harness_agent_capability(
            evidence,
            binding_id="agent",
            expected_capability_ref=registry.capability("aecbench.adapter.rlm-uncached").ref,
            replacement_capability_ref=registry.capability("aecbench.adapter.rlm-output-contract").ref,
        ),
        acceptance_policy=RepairAcceptancePolicy(
            minimum_mean_reward_delta=-0.01,
            require_positive_lower_bound=False,
            maximum_cost_ratio=0.75,
            bootstrap_replicates=32,
        ),
        agent_capability_id="aecbench.adapter.rlm-uncached",
        agent_max_turns=2,
    )

    execution = runtime.execute()

    assert execution.result.status is RepairLoopStatus.REJECTED
    assert execution.result.child_verification is not None
    assert "completion_capability_not_exercised" in execution.result.child_verification.diagnostics
    assert execution.result.decision is not None
    assert "child_verifier_failed" in execution.result.decision.reasons


def test_capability_repair_rejects_completion_reason_without_assistance_evidence(
    tmp_path: Path,
) -> None:
    registry = default_kernel_registry()
    executor = CapabilityCompletionHarborExecutor(report_completion_assistance=False)
    runtime = _build_runtime(
        tmp_path,
        executor=executor,
        diagnosis=lambda evidence: diagnose_harness_agent_capability(
            evidence,
            binding_id="agent",
            expected_capability_ref=registry.capability("aecbench.adapter.rlm-uncached").ref,
            replacement_capability_ref=registry.capability("aecbench.adapter.rlm-output-contract").ref,
        ),
        acceptance_policy=RepairAcceptancePolicy(
            minimum_mean_reward_delta=-0.01,
            require_positive_lower_bound=False,
            maximum_cost_ratio=0.75,
            bootstrap_replicates=32,
        ),
        agent_capability_id="aecbench.adapter.rlm-uncached",
        agent_max_turns=2,
    )

    execution = runtime.execute()

    assert execution.result.status is RepairLoopStatus.REJECTED
    assert execution.result.child_verification is not None
    assert "completion_capability_not_exercised" in execution.result.child_verification.diagnostics


def test_repair_runtime_persists_child_evidence_incomplete_terminal(
    tmp_path: Path,
) -> None:
    executor = ChildDispatchFailingHarborExecutor(emit_turn_limit_failure=True)
    runtime = _build_runtime(
        tmp_path,
        executor=executor,
        diagnosis=lambda evidence: diagnose_harness_turn_limit(
            evidence,
            binding_id="agent",
            max_turns=2,
        ),
    )

    execution = runtime.execute()

    assert execution.result.status is RepairLoopStatus.CHILD_EVIDENCE_INCOMPLETE
    assert len(execution.run_artifacts) == 2
    assert execution.result.child_verification is not None
    assert execution.result.child_verification.reward_coverage is RepairRewardCoverage.NONE
    assert execution.result.attempt is None
    assert execution.result.decision is None
    terminal = RepairTerminalRecord.model_validate_json(execution.terminal.path.read_text(encoding="utf-8"))
    assert terminal.result.status is RepairLoopStatus.CHILD_EVIDENCE_INCOMPLETE
    assert executor.calls == [(17, 1), (29, 1), (17, 2), (29, 2)]


def test_repair_runtime_rejects_unknown_cost_instead_of_treating_it_as_free(
    tmp_path: Path,
) -> None:
    executor = RewardByTurnsHarborExecutor(include_cost=False)
    authority_ledger = AuthorityLedger(
        tmp_path / "authority",
        candidate_roots=(tmp_path / "meta-harness-artifacts",),
    )
    runtime = _build_runtime(
        tmp_path,
        executor=executor,
        diagnosis=lambda evidence: RepairPatchProposal(
            owner=RepairOwner.HARNESS,
            code="insufficient_turn_budget",
            message=f"{len(evidence.trials)} verifier outcomes failed under the Hx turn limit.",
            patch=HarnessAgentMaxTurnsPatch(binding_id="agent", max_turns=2),
        ),
        authority_ledger=authority_ledger,
    )

    with pytest.raises(RepairLoopError) as raised:
        runtime.execute()

    assert raised.value.diagnostic.stage is RepairLoopStage.VERIFY
    assert raised.value.diagnostic.code == "verification_failed"
    assert str(raised.value) == "Harbor invocation receipts do not match successful scored px attempts"


def test_motif_capture_rejects_forged_accepted_repair_with_unknown_cost(
    tmp_path: Path,
) -> None:
    runtime, _ = _runtime(tmp_path)
    execution = runtime.execute()
    attempt = execution.result.attempt
    decision = execution.result.decision
    parent = execution.result.parent_verification
    child = execution.result.child_verification
    assert attempt is not None
    assert decision is not None and decision.accepted
    assert child is not None
    forged_attempt = attempt.model_copy(
        update={
            "parent_outcomes": tuple(outcome.model_copy(update={"cost": None}) for outcome in attempt.parent_outcomes),
            "child_outcomes": tuple(outcome.model_copy(update={"cost": None}) for outcome in attempt.child_outcomes),
        }
    )
    forged_decision = decision.model_copy(
        update={
            "parent_mean_cost": None,
            "child_mean_cost": None,
            "cost_ratio": None,
        }
    )
    forged_parent = parent.model_copy(
        update={
            "observations": tuple(
                observation.model_copy(update={"outcome": observation.outcome.model_copy(update={"cost": None})})
                for observation in parent.observations
            )
        }
    )
    forged_child = child.model_copy(
        update={
            "observations": tuple(
                observation.model_copy(update={"outcome": observation.outcome.model_copy(update={"cost": None})})
                for observation in child.observations
            )
        }
    )
    forged_result = RepairLoopResult.model_validate(
        {
            **execution.result.model_dump(mode="python"),
            "parent_verification": forged_parent,
            "child_verification": forged_child,
            "attempt": forged_attempt,
            "decision": forged_decision,
        }
    )
    forged_execution = _forged_terminal_execution(
        tmp_path,
        execution=execution,
        result=forged_result,
        suffix="unknown-cost",
    )

    with pytest.raises(ValueError, match="acceptance policy"):
        capture_accepted_repair_evidence(forged_execution)


def test_motif_capture_rejects_rehashed_accepted_terminal_with_failed_child(
    tmp_path: Path,
) -> None:
    runtime, _ = _runtime(tmp_path)
    execution = runtime.execute()
    child = execution.result.child_verification
    assert child is not None
    forged_result = execution.result.model_copy(
        update={"child_verification": child.model_copy(update={"passed": False})}
    )
    forged_execution = _forged_terminal_execution(
        tmp_path,
        execution=execution,
        result=forged_result,
        suffix="failed-child",
    )

    with pytest.raises(ValueError, match="passing child verification"):
        capture_accepted_repair_evidence(forged_execution)


@pytest.mark.parametrize("forgery", ["partial", "mismatched"])
def test_motif_capture_rejects_rehashed_terminal_with_unbound_verification_observations(
    tmp_path: Path,
    forgery: str,
) -> None:
    runtime, _ = _runtime(tmp_path)
    execution = runtime.execute()
    child = execution.result.child_verification
    assert child is not None
    if forgery == "partial":
        forged_child = child.model_copy(
            update={
                "passed": False,
                "reward_coverage": RepairRewardCoverage.PARTIAL,
                "observations": child.observations[:1],
            }
        )
        forged_result = execution.result.model_copy(update={"child_verification": forged_child})
        expected = "complete reward coverage"
    else:
        first = child.observations[0]
        forged_observations = (
            first.model_copy(update={"outcome": first.outcome.model_copy(update={"reward": 0.7})}),
            *child.observations[1:],
        )
        forged_result = execution.result.model_copy(
            update={"child_verification": child.model_copy(update={"observations": forged_observations})}
        )
        expected = "child outcomes must equal"
    forged_execution = _forged_terminal_execution(
        tmp_path,
        execution=execution,
        result=forged_result,
        suffix=f"{forgery}-observations",
    )

    with pytest.raises(ValueError, match=expected):
        capture_accepted_repair_evidence(forged_execution)


def test_motif_capture_recomputes_forged_accepted_decision_against_attempt_plan_policy(
    tmp_path: Path,
) -> None:
    runtime, _ = _runtime(tmp_path)
    execution = runtime.execute()
    attempt = execution.result.attempt
    child = execution.result.child_verification
    assert attempt is not None
    assert child is not None
    parent_rewards = {outcome.block_id: outcome.reward for outcome in attempt.parent_outcomes}
    forged_child_outcomes = tuple(
        outcome.model_copy(update={"reward": parent_rewards[outcome.block_id]}) for outcome in attempt.child_outcomes
    )
    forged_attempt = attempt.model_copy(update={"child_outcomes": forged_child_outcomes})
    forged_rewards = {outcome.block_id: outcome.reward for outcome in forged_child_outcomes}
    forged_observations = tuple(
        observation.model_copy(
            update={
                "outcome": observation.outcome.model_copy(
                    update={"reward": forged_rewards[observation.outcome.block_id]}
                )
            }
        )
        for observation in child.observations
    )
    forged_result = RepairLoopResult.model_validate(
        {
            **execution.result.model_dump(mode="python"),
            "attempt": forged_attempt,
            "child_verification": child.model_copy(update={"observations": forged_observations}),
        }
    )
    forged_execution = _forged_terminal_execution(
        tmp_path,
        execution=execution,
        result=forged_result,
        suffix="decision-below-policy",
    )

    with pytest.raises(ValueError, match="acceptance policy"):
        capture_accepted_repair_evidence(forged_execution)


def test_motif_capture_requires_terminal_to_link_the_supplied_attempt_plan(tmp_path: Path) -> None:
    runtime, _ = _runtime(tmp_path)
    execution = runtime.execute()
    forged_execution = _forged_terminal_execution(
        tmp_path,
        execution=execution,
        result=execution.result,
        suffix="wrong-plan-link",
        attempt_plan_sha256="f" * 64,
    )

    with pytest.raises(ValueError, match="attempt plan"):
        capture_accepted_repair_evidence(forged_execution)


def test_motif_capture_requires_attempt_plan_request_to_match_result_lineage(tmp_path: Path) -> None:
    runtime, _ = _runtime(tmp_path)
    execution = runtime.execute()
    plan = RepairAttemptPlan.model_validate_json(execution.attempt_plan.path.read_text(encoding="utf-8"))
    forged_plan = RepairAttemptPlan(
        request=plan.request.model_copy(update={"loop_id": "loop.forged"}),
        parent=plan.parent,
        evidence_use_policy=plan.evidence_use_policy,
        repair_run_spec=plan.repair_run_spec,
    )
    encoded_plan = (json.dumps(forged_plan.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode()
    plan_path = tmp_path / "forged-repair-attempt-plan.json"
    plan_path.write_bytes(encoded_plan)
    plan_reference = execution.attempt_plan.reference.__class__(
        kind="repair-attempt-plan",
        path=str(plan_path),
        sha256=hashlib.sha256(encoded_plan).hexdigest(),
        media_type="application/json",
    )
    forged_attempt_plan = execution.attempt_plan.__class__(path=plan_path, reference=plan_reference)
    forged_execution = _forged_terminal_execution(
        tmp_path,
        execution=execution,
        result=execution.result,
        suffix="wrong-plan-lineage",
        attempt_plan=forged_attempt_plan,
        attempt_plan_sha256=plan_reference.sha256,
    )

    with pytest.raises(ValueError, match="request/result lineage"):
        capture_accepted_repair_evidence(forged_execution)


@pytest.mark.parametrize("artifact_name", ["attempt plan", "repair terminal"])
def test_motif_capture_rejects_stored_artifact_path_that_differs_from_its_reference(
    tmp_path: Path,
    artifact_name: str,
) -> None:
    runtime, _ = _runtime(tmp_path)
    execution = runtime.execute()
    if artifact_name == "attempt plan":
        copied_path = tmp_path / "copied-attempt-plan.json"
        copied_path.write_bytes(execution.attempt_plan.path.read_bytes())
        forged_execution = RepairRuntimeExecution(
            result=execution.result,
            attempt_plan=StoredRepairArtifact(path=copied_path, reference=execution.attempt_plan.reference),
            run_artifacts=execution.run_artifacts,
            terminal=execution.terminal,
        )
    else:
        copied_path = tmp_path / "copied-repair-terminal.json"
        copied_path.write_bytes(execution.terminal.path.read_bytes())
        forged_execution = RepairRuntimeExecution(
            result=execution.result,
            attempt_plan=execution.attempt_plan,
            run_artifacts=execution.run_artifacts,
            terminal=execution.terminal.__class__(path=copied_path, reference=execution.terminal.reference),
        )

    with pytest.raises(ValueError, match=f"{artifact_name} path"):
        capture_accepted_repair_evidence(forged_execution)


def _forged_terminal_execution(
    tmp_path: Path,
    *,
    execution: RepairRuntimeExecution,
    result: RepairLoopResult,
    suffix: str,
    attempt_plan: StoredRepairArtifact | None = None,
    attempt_plan_sha256: str | None = None,
) -> RepairRuntimeExecution:
    selected_plan = attempt_plan or execution.attempt_plan
    terminal_payload = json.loads(execution.terminal.path.read_text(encoding="utf-8"))
    terminal_payload["result"] = result.model_dump(mode="json")
    terminal_payload["attempt_plan_sha256"] = attempt_plan_sha256 or selected_plan.reference.sha256
    terminal_payload["content_sha256"] = canonical_json_sha256(
        {key: value for key, value in terminal_payload.items() if key != "content_sha256"}
    )
    encoded = (json.dumps(terminal_payload, indent=2, sort_keys=True) + "\n").encode()
    terminal_path = tmp_path / f"forged-repair-terminal-{suffix}.json"
    terminal_path.write_bytes(encoded)
    terminal_reference = execution.terminal.reference.__class__(
        kind="repair-terminal",
        path=str(terminal_path),
        sha256=hashlib.sha256(encoded).hexdigest(),
        media_type="application/json",
    )
    return RepairRuntimeExecution(
        result=result,
        attempt_plan=selected_plan,
        run_artifacts=execution.run_artifacts,
        terminal=execution.terminal.__class__(path=terminal_path, reference=terminal_reference),
    )


def test_repair_runtime_rejects_tampered_persisted_run_artifact(tmp_path: Path) -> None:
    runtime, _ = _runtime(tmp_path)
    dependencies = runtime.dependencies
    compiled = dependencies.compiler(runtime.parent, runtime.request.pairing)
    run = dependencies.runner(compiled, runtime.request.pairing)
    artifact = runtime.run_artifact(run.run_id)
    artifact.path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="run artifact hash mismatch"):
        dependencies.verifier(compiled, run)


def test_repair_runtime_rejects_tampered_attempt_plan_before_execution(tmp_path: Path) -> None:
    runtime, executor = _runtime(tmp_path)
    compiled = runtime.dependencies.compiler(runtime.parent, runtime.request.pairing)
    runtime.attempt_plan.path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="repair attempt plan artifact hash mismatch"):
        runtime.dependencies.runner(compiled, runtime.request.pairing)

    assert executor.calls == []


def test_repair_runtime_rejects_tampered_trial_record_bytes(tmp_path: Path) -> None:
    runtime, _ = _runtime(tmp_path)
    dependencies = runtime.dependencies
    compiled = dependencies.compiler(runtime.parent, runtime.request.pairing)
    run = dependencies.runner(compiled, runtime.request.pairing)
    artifact_payload = json.loads(runtime.run_artifact(run.run_id).path.read_text(encoding="utf-8"))
    trial_path = Path(artifact_payload["executions"][0]["trial_records"][0]["path"])
    trial_path.write_text(trial_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="TrialRecord artifact hash"):
        dependencies.verifier(compiled, run)


def test_repair_output_evidence_rejects_contract_bytes_changed_after_import(tmp_path: Path) -> None:
    runtime, _ = _runtime(tmp_path)
    dependencies = runtime.dependencies
    compiled = dependencies.compiler(runtime.parent, runtime.request.pairing)
    run = dependencies.runner(compiled, runtime.request.pairing)
    record = runtime.verified_records(run.run_id)[0]

    assert (
        _repair_output_artifact_evidence(
            record,
            repo_root=runtime.workflow.repo_root,
            tasks_root=runtime.tasks_root,
        )
        is not None
    )

    contract_path = runtime.tasks_root / record.task.task_id / "environment" / "output_contract.json"
    contract_path.write_bytes(contract_path.read_bytes() + b"\n")

    assert (
        _repair_output_artifact_evidence(
            record,
            repo_root=runtime.workflow.repo_root,
            tasks_root=runtime.tasks_root,
        )
        is None
    )


def test_output_commit_evidence_matches_independently_reconstructed_artifact() -> None:
    evaluation = OutputCompletionEvaluation(
        complete=True,
        reason=OutputCompletionReason.COMPLETE,
        present_top_level_keys=("answer",),
        final_json_block_count=1,
    )
    output_artifact = RepairOutputArtifactEvidence(
        path="jobs/trial/artifacts/agent/output.md",
        sha256="a" * 64,
        media_type="text/markdown",
        size_bytes=128,
        completion_contract_sha256="b" * 64,
        completion_contract_content_sha256="c" * 64,
        completion_evaluation=evaluation,
    )
    attestation = OutputCommitAttestation(
        schema_version="aecbench.output-commit-attestation.v1",
        mechanism="agent_explicit_output_commit",
        output_path="/workspace/output.md",
        output_sha256=output_artifact.sha256,
        output_size_bytes=output_artifact.size_bytes,
        completion_contract_sha256=output_artifact.completion_contract_content_sha256,
        completion_evaluation=evaluation,
        initial_output_sha256=None,
        commit_turn=7,
    )
    result = {
        "completion_reason": "output_contract_committed",
        "completion_assistance": None,
        "completion_commit": attestation.model_dump(mode="json"),
        "turns_used": 7,
    }

    assert _has_output_commit_attestation(result, output_artifact) is True

    for field_name, replacement in (
        ("output_sha256", "d" * 64),
        ("output_size_bytes", 129),
        ("completion_contract_sha256", "e" * 64),
        ("commit_turn", 6),
    ):
        mismatched = attestation.model_dump(mode="json")
        mismatched[field_name] = replacement
        mismatched.pop("content_sha256")
        assert (
            _has_output_commit_attestation(
                {**result, "completion_commit": mismatched},
                output_artifact,
            )
            is False
        )


def test_fixed_output_commit_harness_requires_attestation_on_the_parent_run(
    tmp_path: Path,
) -> None:
    runtime = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("diagnosis must not run")),
        agent_capability_id="aecbench.adapter.rlm-output-commit",
        agent_max_turns=2,
    )
    candidate = runtime.dependencies.compiler(runtime.parent, runtime.request.pairing)
    run = runtime.dependencies.runner(candidate, runtime.request.pairing)

    verification = runtime.dependencies.verifier(candidate, run)

    assert verification.passed is False
    assert "completion_capability_not_exercised" in verification.diagnostics


def test_repair_runtime_rejects_task_review_drift_before_child_execution(tmp_path: Path) -> None:
    runtime, _ = _runtime(tmp_path)
    dependencies = runtime.dependencies
    parent = dependencies.compiler(runtime.parent, runtime.request.pairing)
    task_instruction = runtime.tasks_root / runtime.request.pairing.task_ids[0] / "instruction.md"
    task_instruction.write_text("Changed after the paired parent compile.\n", encoding="utf-8")
    child = runtime.apply_patch(
        RepairPatchProposal(
            owner=RepairOwner.HARNESS,
            code="insufficient_turn_budget",
            message="The verifier evidence attributes the failure to Hx turns.",
            patch=HarnessAgentMaxTurnsPatch(binding_id="agent", max_turns=2),
        )
    )

    with pytest.raises(ValueError, match="task/task-review snapshots changed within paired repair"):
        dependencies.compiler(child, runtime.request.pairing)

    assert parent.bundle.task_snapshots != ()


def test_agent_capability_patch_replaces_only_the_expected_agent_capability(tmp_path: Path) -> None:
    runtime, _ = _runtime(tmp_path, agent_capability_id="aecbench.adapter.rlm-uncached")
    parent_request = runtime.parent.harness_request
    parent_binding = parent_request.spec.binding("agent")
    assert parent_binding is not None
    replacement = runtime.registry.capability("aecbench.adapter.rlm-output-contract").ref

    child_request = _patch_agent_capability(
        parent_request,
        HarnessAgentCapabilityPatch(
            binding_id="agent",
            expected_capability_ref=parent_binding.capability_ref,
            replacement_capability_ref=replacement,
        ),
        iteration=1,
    )

    child_binding = child_request.spec.binding("agent")
    assert child_binding is not None
    assert child_binding.capability_ref == replacement
    assert child_binding.configuration == parent_binding.configuration
    assert child_binding.depends_on == parent_binding.depends_on
    assert child_binding.topology_role == parent_binding.topology_role
    assert child_binding.contract_ids == parent_binding.contract_ids
    assert tuple(binding for binding in child_request.spec.bindings if binding.binding_id != "agent") == tuple(
        binding for binding in parent_request.spec.bindings if binding.binding_id != "agent"
    )
    assert child_request.spec.budget == parent_request.spec.budget
    assert child_request.spec.recursion_policy == parent_request.spec.recursion_policy


def test_agent_capability_patch_rejects_stale_expected_capability(tmp_path: Path) -> None:
    runtime, _ = _runtime(tmp_path)
    parent_request = runtime.parent.harness_request

    with pytest.raises(ValueError, match="expected capability"):
        _patch_agent_capability(
            parent_request,
            HarnessAgentCapabilityPatch(
                binding_id="agent",
                expected_capability_ref=runtime.registry.capability("aecbench.adapter.rlm-uncached").ref,
                replacement_capability_ref=runtime.registry.capability("aecbench.adapter.rlm-output-contract").ref,
            ),
            iteration=1,
        )


@pytest.mark.parametrize(
    ("expected_id", "replacement_id"),
    (
        ("aecbench.adapter.direct", "aecbench.adapter.tool-loop"),
        ("aecbench.adapter.rlm", "aecbench.adapter.rlm-output-contract"),
        ("aecbench.adapter.rlm-output-contract", "aecbench.adapter.rlm-uncached"),
    ),
)
def test_agent_capability_patch_rejects_non_allowlisted_transition(
    expected_id: str,
    replacement_id: str,
) -> None:
    registry = default_kernel_registry()

    with pytest.raises(ValueError, match="rlm-uncached.*rlm-output-contract"):
        HarnessAgentCapabilityPatch(
            binding_id="agent",
            expected_capability_ref=registry.capability(expected_id).ref,
            replacement_capability_ref=registry.capability(replacement_id).ref,
        )


def test_repair_runtime_rejects_candidate_kernel_drift_at_compile_boundary(tmp_path: Path) -> None:
    runtime, _ = _runtime(tmp_path)
    kernel = runtime.registry.manifest.ref
    wrong_kernel = KernelRef(
        kernel_id=kernel.kernel_id,
        version="different-version",
    )
    wrong_parent = RepairCandidate(
        candidate_id=runtime.parent.candidate_id,
        parent_candidate_id=runtime.parent.parent_candidate_id,
        iteration=runtime.parent.iteration,
        harness_request=HarnessCompileRequest(
            request_id=runtime.parent.harness_request.request_id,
            kernel_ref=wrong_kernel,
            spec=runtime.parent.harness_request.spec,
        ),
        program_template=runtime.parent.program_template,
    )

    with pytest.raises(ValueError, match="installed fixed kernel"):
        runtime.dependencies.compiler(wrong_parent, runtime.request.pairing)


@pytest.mark.parametrize("drift", ["tasks", "seeds", "budget", "repetitions"])
def test_repair_runtime_rejects_pairing_drift_before_execution(
    tmp_path: Path,
    drift: str,
) -> None:
    runtime, executor = _runtime(tmp_path)
    compiled = runtime.dependencies.compiler(runtime.parent, runtime.request.pairing)

    with pytest.raises(ValueError, match="pairing changed"):
        runtime.dependencies.runner(compiled, _drift_pairing(runtime.request.pairing, drift))

    assert executor.calls == []


def test_retry_patch_targeting_non_retryable_run_batch_is_rejected_at_compile(
    tmp_path: Path,
) -> None:
    runtime, _ = _runtime(tmp_path)
    runtime.dependencies.compiler(runtime.parent, runtime.request.pairing)
    child = runtime.apply_patch(
        RepairPatchProposal(
            owner=RepairOwner.PROGRAM,
            code="transient_execution_failure",
            message="The selected operation would require a bounded retry.",
            patch=ProgramNodeRetryPatch(
                node_id="run",
                retry=RetryPolicy(
                    max_attempts=2,
                    retry_on=("pre_dispatch_capacity_timeout",),
                ),
            ),
        )
    )

    with pytest.raises(ValueError, match="operation does not support retry"):
        runtime.dependencies.compiler(child, runtime.request.pairing)


def test_program_retry_patch_requires_at_least_two_attempts() -> None:
    with pytest.raises(ValueError, match="at least two attempts"):
        ProgramNodeRetryPatch(
            node_id="run",
            retry=RetryPolicy(
                max_attempts=1,
                retry_on=("pre_dispatch_capacity_timeout",),
            ),
        )


def test_program_retry_patch_rejects_effect_unsafe_error_codes() -> None:
    with pytest.raises(ValueError, match="prohibited retry-safe error codes"):
        ProgramNodeRetryPatch(
            node_id="run",
            retry=RetryPolicy(
                max_attempts=2,
                retry_on=("handler_exception",),
            ),
        )


@pytest.mark.parametrize("replacement_attempts", [2, 3])
def test_program_retry_patch_must_strictly_increase_effective_attempts(
    replacement_attempts: int,
) -> None:
    template = RepairProgramTemplate(
        program_id="program.retry-increase",
        version="1.0.0",
        nodes=(
            ActionNode(
                node_id="run",
                operation_id="run_batch",
                retry=RetryPolicy(
                    max_attempts=3,
                    retry_on=("pre_dispatch_capacity_timeout",),
                ),
            ),
            StopNode(node_id="stop", depends_on=("run",), outcome=StopOutcome.SUCCEEDED),
        ),
    )

    with pytest.raises(ValueError, match="must strictly increase effective attempts"):
        _patch_program_retry(
            template,
            ProgramNodeRetryPatch(
                node_id="run",
                retry=RetryPolicy(
                    max_attempts=replacement_attempts,
                    retry_on=("pre_dispatch_capacity_timeout",),
                ),
            ),
        )


def test_program_retry_diagnosis_requires_at_least_two_attempts(tmp_path: Path) -> None:
    runtime, _ = _runtime(tmp_path)
    terminal = RepairTerminalRecord.model_validate_json(runtime.execute().terminal.path.read_text(encoding="utf-8"))
    assert terminal.diagnosis_evidence is not None

    with pytest.raises(ValueError, match="at least two attempts"):
        diagnose_program_retry(
            terminal.diagnosis_evidence,
            node_id="run",
            retry=RetryPolicy(
                max_attempts=1,
                retry_on=("pre_dispatch_capacity_timeout",),
            ),
            retryable_error_codes=("pre_dispatch_capacity_timeout",),
        )


def test_repair_runtime_persists_unowned_diagnosis_without_running_a_child(
    tmp_path: Path,
) -> None:
    executor = RewardByTurnsHarborExecutor()
    runtime = _build_runtime(
        tmp_path,
        executor=executor,
        diagnosis=lambda evidence: RepairNoPatchProposal(
            failure_domain=RepairFailureDomain.UNDETERMINED,
            code="healthy_runtime_low_reward",
            message="Low verifier reward alone cannot identify a mutable repair owner.",
            evidence_codes=evidence.diagnostic_codes,
        ),
    )

    execution = runtime.execute()

    assert execution.result.status is RepairLoopStatus.NO_APPLICABLE_REPAIR
    assert execution.result.diagnosis is not None
    assert execution.result.diagnosis.owner is None
    assert execution.result.diagnosis.failure_domain is RepairFailureDomain.UNDETERMINED
    assert execution.result.child_verification is None
    assert len(execution.run_artifacts) == 1
    assert executor.calls == [(17, 1), (29, 1)]
    terminal = RepairTerminalRecord.model_validate_json(execution.terminal.path.read_text(encoding="utf-8"))
    assert terminal.diagnosis_evidence is not None
    assert terminal.patch_proposal is None


def test_dispatched_catchall_program_failure_persists_and_abstains_without_a_child(
    tmp_path: Path,
) -> None:
    executor = FailingHarborExecutor()
    runtime = _build_runtime(
        tmp_path,
        executor=executor,
        diagnosis=lambda evidence: diagnose_program_attempt_limit(
            evidence,
            max_total_attempts=2,
        ),
    )

    execution = runtime.execute()

    assert execution.result.status is RepairLoopStatus.NO_APPLICABLE_REPAIR
    assert execution.result.diagnosis is not None
    assert execution.result.diagnosis.failure_domain is RepairFailureDomain.RUNTIME
    assert execution.result.diagnosis.owner is None
    assert execution.result.child_verification is None
    assert executor.calls == 2
    assert len(execution.run_artifacts) == 1
    manifest = RepairRunArtifactManifest.model_validate_json(
        execution.run_artifacts[0].path.read_text(encoding="utf-8")
    )
    assert len(manifest.executions) == 2
    assert all(item.program_execution.status is ProgramExecutionStatus.FAILED for item in manifest.executions)
    assert all(item.program_execution.error_code == "harbor_workflow_failed" for item in manifest.executions)
    assert all(item.trial_records == () for item in manifest.executions)
    assert all(item.budget.unaccounted_dispatches == 1 for item in manifest.executions)
    terminal = RepairTerminalRecord.model_validate_json(execution.terminal.path.read_text(encoding="utf-8"))
    assert terminal.diagnosis_evidence is not None
    assert terminal.diagnosis_evidence.trials == ()
    assert len(terminal.diagnosis_evidence.program_executions) == 2
    assert "program_failure:harbor_workflow_failed" in terminal.diagnosis_evidence.diagnostic_codes


def test_program_attempt_limit_repair_recovers_a_partial_real_task_matrix_without_scoring(
    tmp_path: Path,
) -> None:
    runtime, executor, task_ids = _attempt_limit_runtime(tmp_path)

    execution = runtime.execute()

    result = execution.result
    assert result.status is RepairLoopStatus.RECOVERED_UNSCORED
    assert result.diagnosis is not None
    assert result.diagnosis.owner is RepairOwner.PROGRAM
    assert result.attempt is None
    assert result.decision is None
    assert result.recovery_attempt is not None
    assert result.recovery_decision is not None and result.recovery_decision.recovered
    assert result.parent_verification.reward_coverage is RepairRewardCoverage.PARTIAL
    assert result.child_verification is not None
    assert result.child_verification.reward_coverage is RepairRewardCoverage.COMPLETE
    assert len(result.parent_verification.observations) == 1
    assert len(result.child_verification.observations) == 2
    assert [item.status.value for item in result.parent_verification.execution_observations] == ["failed"]
    assert [item.status.value for item in result.child_verification.execution_observations] == ["succeeded"]
    assert executor.task_selections == [
        (f"tasks/{task_ids[0]}",),
        (f"tasks/{task_ids[0]}",),
        (f"tasks/{task_ids[1]}",),
    ]

    manifests = {
        artifact.candidate_id: RepairRunArtifactManifest.model_validate_json(artifact.path.read_text(encoding="utf-8"))
        for artifact in execution.run_artifacts
    }
    parent = manifests[runtime.request.parent_candidate_id]
    child = manifests[runtime.request.child_candidate_id]
    assert parent.kernel_ref == child.kernel_ref == runtime.registry.manifest.ref
    assert parent.harness_ref == child.harness_ref
    assert parent.program_ref != child.program_ref
    assert parent.pairing == child.pairing == runtime.request.pairing
    assert parent.executions[0].program_execution.status is ProgramExecutionStatus.FAILED
    assert parent.executions[0].program_execution.error_code == "global_attempt_budget_exhausted"
    assert parent.executions[0].program_execution.total_attempts == 1
    assert len(parent.executions[0].trial_records) == 1
    assert len(parent.executions[0].harbor_invocation_receipts) == 1
    assert child.executions[0].program_execution.status is ProgramExecutionStatus.SUCCEEDED
    assert child.executions[0].program_execution.total_attempts == 2
    assert len(child.executions[0].trial_records) == 2
    assert len(child.executions[0].harbor_invocation_receipts) == 2
    assert parent.executions[0].budget.status == child.executions[0].budget.status == "within_budget"

    parent_receipt = load_harbor_invocation_receipt(Path(parent.executions[0].harbor_invocation_receipts[0].path))
    child_receipts = tuple(
        load_harbor_invocation_receipt(Path(reference.path))
        for reference in child.executions[0].harbor_invocation_receipts
    )
    assert parent_receipt.run_id == parent.executions[0].run_id
    assert parent_receipt.bundle_id == parent.executions[0].execution_bundle_id
    assert [receipt.program_node_id for receipt in child_receipts] == ["run-alpha", "run-beta"]
    assert {reference.path for receipt in child_receipts for reference in receipt.imported_trial_records} == {
        reference.path for reference in child.executions[0].trial_records
    }

    assert len(runtime.verified_records(parent.run_id)) == 1
    assert len(runtime.verified_records(child.run_id)) == 2
    terminal = RepairTerminalRecord.model_validate_json(execution.terminal.path.read_text(encoding="utf-8"))
    assert terminal.patch_proposal is not None
    assert terminal.patch_proposal.patch == ProgramMaxTotalAttemptsPatch(max_total_attempts=2)
    assert terminal.diagnosis_evidence is not None
    assert len(terminal.diagnosis_evidence.trials) == 1
    assert terminal.diagnosis_evidence.trials[0].task_id == task_ids[0]


def test_program_batch_coalescing_patch_preserves_fixed_hx_and_all_program_limits(
    tmp_path: Path,
) -> None:
    runtime, _, task_ids = _batch_coalescing_runtime(tmp_path)
    parent = runtime.dependencies.compiler(runtime.parent, runtime.request.pairing)
    proposal = RepairPatchProposal(
        owner=RepairOwner.PROGRAM,
        code="program_task_batch_coalescing_required",
        message="The exact serial task pair fits one existing batch operation.",
        patch=ProgramCoalesceTaskBatchPatch(
            expected_program_ref=parent.program.ref,
            source_node_ids=("run-primary", "run-secondary"),
            replacement_node_id="run-coalesced",
            task_refs=task_ids,
        ),
    )

    child_source = runtime.apply_patch(proposal)
    child = runtime.dependencies.compiler(child_source, runtime.request.pairing)

    assert child_source.harness_request == runtime.parent.harness_request
    assert child_source.program_template.limits == runtime.parent.program_template.limits
    assert child.harness == parent.harness
    assert child.bundle.harness.kernel_ref == parent.bundle.harness.kernel_ref
    assert child.program.limits == parent.program.limits
    assert child.program.limits.max_total_attempts == 1
    assert child_source.program_template.nodes == (
        ActionNode(
            node_id="run-coalesced",
            operation_id="run_batch",
            arguments=(ProgramArgument(name="task_refs", value=LiteralValue(value=list(task_ids))),),
        ),
        StopNode(
            node_id="stop",
            depends_on=("run-coalesced",),
            outcome=StopOutcome.SUCCEEDED,
        ),
    )


def test_program_batch_coalescing_patch_rejects_a_stale_compiled_program_hash(
    tmp_path: Path,
) -> None:
    runtime, _, task_ids = _batch_coalescing_runtime(tmp_path)
    runtime.dependencies.compiler(runtime.parent, runtime.request.pairing)

    with pytest.raises(ValueError, match="expected program"):
        runtime.apply_patch(
            RepairPatchProposal(
                owner=RepairOwner.PROGRAM,
                code="program_task_batch_coalescing_required",
                message="The exact serial task pair fits one existing batch operation.",
                patch=ProgramCoalesceTaskBatchPatch(
                    expected_program_ref=ExecutionProgramRef(program_id="stale", version="1.0.0"),
                    source_node_ids=("run-primary", "run-secondary"),
                    replacement_node_id="run-coalesced",
                    task_refs=task_ids,
                ),
            )
        )


def test_declared_stage_graph_patch_compiles_the_exact_graph_without_changing_hx(
    tmp_path: Path,
) -> None:
    runtime = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda evidence: diagnose_program_declared_stage_graph_materialization(evidence),
        limits=ProgramLimits(max_nodes=16, max_total_attempts=8, max_parallelism=4),
    )
    task_id = runtime.request.pairing.task_ids[0]
    _write_declared_stage_review(runtime.tasks_root / task_id)
    parent = runtime.dependencies.compiler(runtime.parent, runtime.request.pairing)
    snapshot = parent.bundle.task_snapshots[0]
    assert isinstance(parent.bundle.review, ReviewSnapshot)
    review = next(item for item in parent.bundle.review.tasks if item.task_id == task_id)
    assert review.stage_graph is not None
    task_graph = RepairDeclaredStageGraphEvidence(
        task_id=task_id,
        task_snapshot=snapshot,
        review=review,
    )
    patch = ProgramMaterializeDeclaredStageGraphPatch(
        expected_program_ref=parent.program.ref,
        task_graphs=(task_graph,),
    )
    proposal = RepairPatchProposal(
        owner=RepairOwner.PROGRAM,
        code="program_declared_stage_graph_unmaterialized",
        message="Materialize the exact pinned task graph.",
        patch=patch,
    )

    child_source = runtime.apply_patch(proposal)
    child = runtime.dependencies.compiler(child_source, runtime.request.pairing)

    expected_program = materialize_program_declared_stage_graph(
        runtime.parent.program_template,
        patch,
    )
    assert child_source.program_template.nodes == expected_program.nodes
    assert child_source.program_template.limits == expected_program.limits
    assert child_source.program_template.version != expected_program.version
    assert child_source.harness_request == runtime.parent.harness_request
    assert child_source.program_template.limits == runtime.parent.program_template.limits
    assert child.harness == parent.harness
    assert child.bundle.harness.kernel_ref == parent.bundle.harness.kernel_ref
    assert child.bundle.task_snapshots == parent.bundle.task_snapshots
    stage_actions = tuple(
        node for node in child.program.nodes if isinstance(node, ActionNode) and node.operation_id == "run_stage"
    )
    assert [
        next(
            argument.value.value
            for argument in node.arguments
            if argument.name == "stage_id" and isinstance(argument.value, LiteralValue)
        )
        for node in stage_actions
    ] == ["inventory", "authority", "decision"]
    decision = stage_actions[-1]
    assert len(decision.depends_on) == 1
    decision_inputs = next(node for node in child.program.nodes if node.node_id == decision.depends_on[0])
    assert isinstance(decision_inputs, JoinNode)
    assert {source.node_id for source in decision_inputs.sources} == {
        stage_actions[0].node_id,
        stage_actions[1].node_id,
    }
    finalizer = next(
        node for node in child.program.nodes if isinstance(node, ActionNode) and node.operation_id == "finalize_task"
    )
    all_stages = next(node for node in child.program.nodes if node.node_id == finalizer.depends_on[0])
    assert isinstance(all_stages, JoinNode)
    assert {source.node_id for source in all_stages.sources} == {node.node_id for node in stage_actions}


def test_declared_stage_graph_patch_rejects_stale_program_or_task_graph_identity(
    tmp_path: Path,
) -> None:
    runtime = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda evidence: diagnose_program_declared_stage_graph_materialization(evidence),
        limits=ProgramLimits(max_nodes=16, max_total_attempts=8),
    )
    task_id = runtime.request.pairing.task_ids[0]
    _write_declared_stage_review(runtime.tasks_root / task_id)
    parent = runtime.dependencies.compiler(runtime.parent, runtime.request.pairing)
    snapshot = parent.bundle.task_snapshots[0]
    assert isinstance(parent.bundle.review, ReviewSnapshot)
    review = next(item for item in parent.bundle.review.tasks if item.task_id == task_id)
    assert review.stage_graph is not None
    task_graph = RepairDeclaredStageGraphEvidence(
        task_id=task_id,
        task_snapshot=snapshot,
        review=review,
    )

    with pytest.raises(ValueError, match="expected program"):
        runtime.apply_patch(
            RepairPatchProposal(
                owner=RepairOwner.PROGRAM,
                code="program_declared_stage_graph_unmaterialized",
                message="Reject stale program identity.",
                patch=ProgramMaterializeDeclaredStageGraphPatch(
                    expected_program_ref=ExecutionProgramRef(program_id="stale", version="1.0.0"),
                    task_graphs=(task_graph,),
                ),
            )
        )

    with pytest.raises(ValueError, match="task-review evidence"):
        runtime.apply_patch(
            RepairPatchProposal(
                owner=RepairOwner.PROGRAM,
                code="program_declared_stage_graph_unmaterialized",
                message="Reject stale task identity.",
                patch=ProgramMaterializeDeclaredStageGraphPatch(
                    expected_program_ref=parent.program.ref,
                    task_graphs=(
                        task_graph.model_copy(
                            update={"review": review.model_copy(update={"profile_id": "stale-review"})}
                        ),
                    ),
                ),
            )
        )


def test_declared_stage_graph_repair_runs_one_scored_finalization_per_task_and_seed(
    tmp_path: Path,
) -> None:
    runtime = _build_runtime(
        tmp_path,
        executor=DeclaredStageHarborExecutor(),
        diagnosis=diagnose_program_declared_stage_graph_materialization,
        limits=ProgramLimits(max_nodes=16, max_total_attempts=8, max_parallelism=4),
    )
    task_id = runtime.request.pairing.task_ids[0]
    _write_declared_stage_review(runtime.tasks_root / task_id)

    execution = runtime.execute()

    compiled_child = runtime._compiled[runtime.request.child_candidate_id]
    stage_operation = compiled_child.harness.program_surface.operation("run_stage")
    stage_definition = runtime.registry.operation_definition("run_stage")
    finalize_operation = compiled_child.harness.program_surface.operation("finalize_task")
    finalize_definition = runtime.registry.operation_definition("finalize_task")
    assert stage_operation is not None
    assert stage_definition is not None
    assert (
        _operation_definition_for_dispatch(
            registry=runtime.registry,
            operation=stage_operation,
        )
        == stage_definition
    )
    assert finalize_operation is not None
    assert finalize_definition is not None
    assert (
        _operation_definition_for_dispatch(
            registry=runtime.registry,
            operation=finalize_operation,
        )
        == finalize_definition
    )
    assert execution.result.status is RepairLoopStatus.REJECTED
    terminal = RepairTerminalRecord.model_validate_json(execution.terminal.path.read_text(encoding="utf-8"))
    assert terminal.patch_proposal is not None
    assert isinstance(
        terminal.patch_proposal.patch,
        ProgramMaterializeDeclaredStageGraphPatch,
    )
    manifests = {
        artifact.candidate_id: RepairRunArtifactManifest.model_validate_json(artifact.path.read_text(encoding="utf-8"))
        for artifact in execution.run_artifacts
    }
    parent = manifests[runtime.request.parent_candidate_id]
    child = manifests[runtime.request.child_candidate_id]
    assert parent.harness_ref == child.harness_ref
    assert all(item.program_execution.total_attempts == 1 for item in parent.executions)
    assert all(item.program_execution.total_attempts == 4 for item in child.executions)
    assert all(len(item.trial_records) == 1 for item in child.executions)
    assert all(len(item.harbor_invocation_receipts) == 1 for item in child.executions)
    for seed in child.executions:
        receipt = load_harbor_invocation_receipt(Path(seed.harbor_invocation_receipts[0].path))
        assert receipt.program_node_id == "task-001.finalize"
        assert len(receipt.imported_trial_records) == 1


def test_legacy_registry_without_definitions_runs_scored_task_finalization(
    tmp_path: Path,
) -> None:
    runtime = _build_runtime(
        tmp_path,
        executor=DeclaredStageHarborExecutor(),
        diagnosis=diagnose_program_declared_stage_graph_materialization,
        limits=ProgramLimits(max_nodes=16, max_total_attempts=8, max_parallelism=4),
    )
    task_id = runtime.request.pairing.task_ids[0]
    _write_declared_stage_review(runtime.tasks_root / task_id)
    current = runtime.registry
    runtime.registry = KernelRuntimeRegistry(
        manifest=current.manifest,
        primitives=current.primitives,
        package_fingerprint=current.package_fingerprint,
    )

    assert runtime.registry.operation_definition("run_stage") is None
    assert runtime.registry.operation_definition("finalize_task") is None

    execution = runtime.execute()

    assert execution.result.status is RepairLoopStatus.REJECTED
    child = next(
        RepairRunArtifactManifest.model_validate_json(artifact.path.read_text(encoding="utf-8"))
        for artifact in execution.run_artifacts
        if artifact.candidate_id == runtime.request.child_candidate_id
    )
    assert all(len(item.trial_records) == 1 for item in child.executions)
    for seed in child.executions:
        receipt = load_harbor_invocation_receipt(Path(seed.harbor_invocation_receipts[0].path))
        assert receipt.program_node_id == "task-001.finalize"


def test_program_batch_coalescing_recovers_with_one_attempt_and_one_child_invocation(
    tmp_path: Path,
) -> None:
    runtime, executor, task_ids = _batch_coalescing_runtime(tmp_path)

    execution = runtime.execute()

    result = execution.result
    assert result.status is RepairLoopStatus.RECOVERED_UNSCORED
    assert result.diagnosis is not None and result.diagnosis.owner is RepairOwner.PROGRAM
    assert result.parent_verification.reward_coverage is RepairRewardCoverage.PARTIAL
    assert result.child_verification is not None
    assert result.child_verification.reward_coverage is RepairRewardCoverage.COMPLETE
    assert executor.task_selections == [
        (f"tasks/{task_ids[0]}",),
        (f"tasks/{task_ids[0]}", f"tasks/{task_ids[1]}"),
    ]

    manifests = {
        artifact.candidate_id: RepairRunArtifactManifest.model_validate_json(artifact.path.read_text(encoding="utf-8"))
        for artifact in execution.run_artifacts
    }
    parent = manifests[runtime.request.parent_candidate_id]
    child = manifests[runtime.request.child_candidate_id]
    assert parent.harness_ref == child.harness_ref
    assert parent.pairing == child.pairing == runtime.request.pairing
    assert parent.executions[0].program_execution.error_code == "global_attempt_budget_exhausted"
    assert parent.executions[0].program_execution.total_attempts == 1
    assert len(parent.executions[0].trial_records) == 1
    assert len(parent.executions[0].harbor_invocation_receipts) == 1
    assert child.executions[0].program_execution.status is ProgramExecutionStatus.SUCCEEDED
    assert child.executions[0].program_execution.total_attempts == 1
    assert len(child.executions[0].trial_records) == 2
    assert len(child.executions[0].harbor_invocation_receipts) == 1
    child_receipt = load_harbor_invocation_receipt(Path(child.executions[0].harbor_invocation_receipts[0].path))
    assert child_receipt.program_node_id == "run-coalesced"
    assert {reference.path for reference in child_receipt.imported_trial_records} == {
        reference.path for reference in child.executions[0].trial_records
    }

    terminal = RepairTerminalRecord.model_validate_json(execution.terminal.path.read_text(encoding="utf-8"))
    assert terminal.patch_proposal is not None
    assert isinstance(terminal.patch_proposal.patch, ProgramCoalesceTaskBatchPatch)
    assert terminal.patch_proposal.patch.expected_program_ref == parent.program_ref


def test_repair_runtime_revalidates_bound_harbor_invocation_receipts(
    tmp_path: Path,
) -> None:
    runtime, _, _ = _attempt_limit_runtime(tmp_path)
    execution = runtime.execute()
    parent_artifact = next(
        artifact for artifact in execution.run_artifacts if artifact.candidate_id == runtime.request.parent_candidate_id
    )
    parent = RepairRunArtifactManifest.model_validate_json(parent_artifact.path.read_text(encoding="utf-8"))
    receipt = load_harbor_invocation_receipt(Path(parent.executions[0].harbor_invocation_receipts[0].path))
    job_file = Path(receipt.job_dir) / receipt.job_files[0].relative_path
    job_file.write_bytes(job_file.read_bytes() + b"tampered")

    with pytest.raises(ValueError, match="Harbor job file inventory or hashes changed"):
        runtime.verified_records(parent.run_id)


def test_program_attempt_limit_patch_requires_a_strict_increase_within_the_fixed_harness_budget(
    tmp_path: Path,
) -> None:
    runtime, _, _ = _attempt_limit_runtime(tmp_path)
    runtime.dependencies.compiler(runtime.parent, runtime.request.pairing)

    with pytest.raises(ValueError, match="must strictly increase"):
        runtime.apply_patch(
            RepairPatchProposal(
                owner=RepairOwner.PROGRAM,
                code="program_attempt_limit_exhausted",
                message="The program exhausted its one allowed operation attempt.",
                patch=ProgramMaxTotalAttemptsPatch(max_total_attempts=1),
            )
        )

    over_budget = runtime.apply_patch(
        RepairPatchProposal(
            owner=RepairOwner.PROGRAM,
            code="program_attempt_limit_exhausted",
            message="The program exhausted its one allowed operation attempt.",
            patch=ProgramMaxTotalAttemptsPatch(max_total_attempts=3),
        )
    )
    with pytest.raises(ValueError, match="attempts exceed the compiled harness budget"):
        runtime.dependencies.compiler(over_budget, runtime.request.pairing)


def test_repair_runtime_classifies_verifier_error_artifact_as_verifier_failure(
    tmp_path: Path,
) -> None:
    executor = RewardByTurnsHarborExecutor(verifier_error="verifier process exited unexpectedly")
    runtime = _build_runtime(
        tmp_path,
        executor=executor,
        diagnosis=lambda evidence: diagnose_harness_turn_limit(
            evidence,
            binding_id="agent",
            max_turns=2,
        ),
    )

    execution = runtime.execute()

    assert execution.result.status is RepairLoopStatus.NO_APPLICABLE_REPAIR
    assert execution.result.diagnosis is not None
    assert execution.result.diagnosis.failure_domain is RepairFailureDomain.VERIFIER
    assert execution.result.diagnosis.owner is None
    terminal = RepairTerminalRecord.model_validate_json(execution.terminal.path.read_text(encoding="utf-8"))
    assert terminal.diagnosis_evidence is not None
    assert "verifier_execution_failed" in terminal.diagnosis_evidence.diagnostic_codes
    assert all(
        trial.verifier.completed
        and trial.verifier.breakdown is not None
        and trial.verifier.breakdown["error"] == "verifier process exited unexpectedly"
        for trial in terminal.diagnosis_evidence.trials
    )


@pytest.mark.parametrize(
    "stop_reason",
    (AdapterStopReason.TOKEN_BUDGET, AdapterStopReason.CONTEXT_LIMIT),
)
def test_repair_runtime_does_not_patch_hx_for_real_imported_non_iteration_stops(
    tmp_path: Path,
    stop_reason: AdapterStopReason,
) -> None:
    executor = RewardByTurnsHarborExecutor(resource_stop=stop_reason)
    runtime = _build_runtime(
        tmp_path,
        executor=executor,
        diagnosis=lambda evidence: diagnose_harness_turn_limit(
            evidence,
            binding_id="agent",
            max_turns=2,
        ),
    )

    execution = runtime.execute()

    assert execution.result.status is RepairLoopStatus.NO_APPLICABLE_REPAIR
    assert execution.result.diagnosis is not None
    assert execution.result.diagnosis.failure_domain is RepairFailureDomain.RUNTIME
    assert len(executor.calls) == 2
    terminal = RepairTerminalRecord.model_validate_json(execution.terminal.path.read_text(encoding="utf-8"))
    assert terminal.diagnosis_evidence is not None
    assert all(trial.agent.stop_reason is stop_reason for trial in terminal.diagnosis_evidence.trials)
    assert "harness_turn_limit_reached" not in terminal.diagnosis_evidence.diagnostic_codes


def test_repair_runtime_patches_only_real_imported_exact_iteration_exhaustion(
    tmp_path: Path,
) -> None:
    executor = RewardByTurnsHarborExecutor(emit_turn_limit_failure=True)
    runtime = _build_runtime(
        tmp_path,
        executor=executor,
        diagnosis=lambda evidence: diagnose_harness_turn_limit(
            evidence,
            binding_id="agent",
            max_turns=2,
        ),
    )

    execution = runtime.execute()

    assert execution.result.status is RepairLoopStatus.ACCEPTED
    assert execution.result.diagnosis is not None
    assert execution.result.diagnosis.owner is RepairOwner.HARNESS
    assert len(executor.calls) == 4
    terminal = RepairTerminalRecord.model_validate_json(execution.terminal.path.read_text(encoding="utf-8"))
    assert terminal.diagnosis_evidence is not None
    assert "harness_turn_limit_reached" in terminal.diagnosis_evidence.diagnostic_codes
    assert all(
        trial.agent.stop_reason is AdapterStopReason.ITERATION_CAP
        and trial.agent.turns_used == trial.agent.max_turns == 1
        for trial in terminal.diagnosis_evidence.trials
    )


def test_repair_runtime_does_not_infer_effective_turn_cap_from_hx_configuration(
    tmp_path: Path,
) -> None:
    executor = RewardByTurnsHarborExecutor(
        emit_turn_limit_failure=True,
        include_runtime_turn_evidence=False,
    )
    runtime = _build_runtime(
        tmp_path,
        executor=executor,
        diagnosis=lambda evidence: diagnose_harness_turn_limit(
            evidence,
            binding_id="agent",
            max_turns=2,
        ),
    )

    execution = runtime.execute()

    assert execution.result.status is RepairLoopStatus.NO_APPLICABLE_REPAIR
    assert execution.result.diagnosis is not None
    assert execution.result.diagnosis.failure_domain is RepairFailureDomain.RUNTIME
    assert len(executor.calls) == 2
    terminal = RepairTerminalRecord.model_validate_json(execution.terminal.path.read_text(encoding="utf-8"))
    assert terminal.diagnosis_evidence is not None
    assert all(trial.agent.max_turns is None for trial in terminal.diagnosis_evidence.trials)
    assert "runtime_stop_evidence_incomplete" in terminal.diagnosis_evidence.diagnostic_codes


@pytest.mark.parametrize("event_candidate", ["verifier_language_gap", "task_interface_gap"])
def test_repair_runtime_classifies_reviewer_interface_events_as_task_world_failure(
    tmp_path: Path,
    event_candidate: str,
) -> None:
    executor = RewardByTurnsHarborExecutor(reviewer_event_candidates=(event_candidate,))
    runtime = _build_runtime(
        tmp_path,
        executor=executor,
        diagnosis=lambda evidence: diagnose_harness_turn_limit(
            evidence,
            binding_id="agent",
            max_turns=2,
        ),
    )

    execution = runtime.execute()

    assert execution.result.status is RepairLoopStatus.NO_APPLICABLE_REPAIR
    assert execution.result.diagnosis is not None
    assert execution.result.diagnosis.failure_domain is RepairFailureDomain.TASK_WORLD
    assert execution.result.diagnosis.owner is None
    terminal = RepairTerminalRecord.model_validate_json(execution.terminal.path.read_text(encoding="utf-8"))
    assert terminal.diagnosis_evidence is not None
    assert "task_world_interface_mismatch" in terminal.diagnosis_evidence.diagnostic_codes
    for trial in terminal.diagnosis_evidence.trials:
        breakdown = trial.verifier.breakdown
        assert breakdown is not None
        reviewer = breakdown.get("llm_reviewer")
        assert isinstance(reviewer, dict)
        assert reviewer.get("event_candidates") == [event_candidate]


def test_harness_turn_diagnosis_requires_positive_cap_exhaustion_evidence(
    tmp_path: Path,
) -> None:
    runtime, _ = _runtime(tmp_path)
    terminal = RepairTerminalRecord.model_validate_json(runtime.execute().terminal.path.read_text(encoding="utf-8"))
    assert terminal.diagnosis_evidence is not None
    healthy_low_reward = terminal.diagnosis_evidence

    refused = diagnose_harness_turn_limit(
        healthy_low_reward,
        binding_id="agent",
        max_turns=4,
    )

    assert isinstance(refused, RepairNoPatchProposal)
    assert refused.failure_domain is RepairFailureDomain.UNDETERMINED

    payload = healthy_low_reward.model_dump(mode="json", exclude={"content_sha256"})
    for trial in payload["trials"]:
        trial["agent"].update(
            {
                "status": "partial",
                "failure_kind": "turn_limit_reached",
                "stop_reason": AdapterStopReason.ITERATION_CAP.value,
                "provider_error": "turn limit reached",
                "turns_used": 1,
                "max_turns": 1,
            }
        )
        trial["error_codes"] = sorted(
            {
                *trial["error_codes"],
                "agent_execution_failed",
                "agent_failure:turn_limit_reached",
                "harness_turn_limit_reached",
            }
        )
    payload["diagnostic_codes"] = sorted(
        {
            *payload["diagnostic_codes"],
            "agent_execution_failed",
            "agent_failure:turn_limit_reached",
            "harness_turn_limit_reached",
        }
    )
    exhausted = RepairRuntimeEvidence.model_validate(payload)

    proposal = diagnose_harness_turn_limit(
        exhausted,
        binding_id="agent",
        max_turns=4,
    )

    assert isinstance(proposal, RepairPatchProposal)
    assert proposal.owner is RepairOwner.HARNESS
    assert proposal.patch == HarnessAgentMaxTurnsPatch(binding_id="agent", max_turns=4)

    conflicted_payload = exhausted.model_dump(mode="json", exclude={"content_sha256"})
    conflicted_payload["diagnostic_codes"] = sorted(
        {*conflicted_payload["diagnostic_codes"], "task_world_interface_mismatch"}
    )
    conflicted = RepairRuntimeEvidence.model_validate(conflicted_payload)

    refused_conflict = diagnose_harness_turn_limit(
        conflicted,
        binding_id="agent",
        max_turns=4,
    )

    assert isinstance(refused_conflict, RepairNoPatchProposal)
    assert refused_conflict.failure_domain is RepairFailureDomain.TASK_WORLD


def test_program_retry_diagnosis_requires_a_matching_failed_program_node(
    tmp_path: Path,
) -> None:
    runtime, _ = _runtime(tmp_path)
    terminal = RepairTerminalRecord.model_validate_json(runtime.execute().terminal.path.read_text(encoding="utf-8"))
    assert terminal.diagnosis_evidence is not None
    healthy_low_reward = terminal.diagnosis_evidence

    refused = diagnose_program_retry(
        healthy_low_reward,
        node_id="run",
        retry=RetryPolicy(
            max_attempts=2,
            retry_on=("pre_dispatch_capacity_timeout",),
        ),
        retryable_error_codes=("pre_dispatch_capacity_timeout",),
    )

    assert isinstance(refused, RepairNoPatchProposal)
    assert refused.failure_domain is RepairFailureDomain.UNDETERMINED

    payload = healthy_low_reward.model_dump(mode="json", exclude={"content_sha256"})
    for program in payload["program_executions"]:
        program.update(
            {
                "status": "failed",
                "error_code": "pre_dispatch_capacity_timeout",
                "error_message": "Capacity was unavailable before dispatch started.",
                "failed_nodes": [
                    {
                        "node_id": "run",
                        "error_code": "pre_dispatch_capacity_timeout",
                        "error_message": "Capacity was unavailable before dispatch started.",
                    }
                ],
            }
        )
    payload["diagnostic_codes"] = sorted({*payload["diagnostic_codes"], "program_execution_failed"})
    failed_program = RepairRuntimeEvidence.model_validate(payload)

    proposal = diagnose_program_retry(
        failed_program,
        node_id="run",
        retry=RetryPolicy(
            max_attempts=2,
            retry_on=("pre_dispatch_capacity_timeout",),
        ),
        retryable_error_codes=("pre_dispatch_capacity_timeout",),
    )

    assert isinstance(proposal, RepairPatchProposal)
    assert proposal.owner is RepairOwner.PROGRAM
    assert proposal.patch == ProgramNodeRetryPatch(
        node_id="run",
        retry=RetryPolicy(
            max_attempts=2,
            retry_on=("pre_dispatch_capacity_timeout",),
        ),
    )


def test_program_retry_diagnosis_rejects_a_policy_different_from_its_evidence_allowlist(
    tmp_path: Path,
) -> None:
    runtime, _ = _runtime(tmp_path)
    terminal = RepairTerminalRecord.model_validate_json(runtime.execute().terminal.path.read_text(encoding="utf-8"))
    assert terminal.diagnosis_evidence is not None

    with pytest.raises(ValueError, match="must install exactly its declared retryable error codes"):
        diagnose_program_retry(
            terminal.diagnosis_evidence,
            node_id="run",
            retry=RetryPolicy(max_attempts=2, retry_on=("different_transient",)),
            retryable_error_codes=("pre_dispatch_capacity_timeout",),
        )


def test_program_retry_diagnosis_rejects_the_catch_all_harbor_failure_code(
    tmp_path: Path,
) -> None:
    runtime, _ = _runtime(tmp_path)
    terminal = RepairTerminalRecord.model_validate_json(runtime.execute().terminal.path.read_text(encoding="utf-8"))
    assert terminal.diagnosis_evidence is not None

    with pytest.raises(ValueError, match="catch-all Harbor failure"):
        diagnose_program_retry(
            terminal.diagnosis_evidence,
            node_id="run",
            retry=RetryPolicy(max_attempts=2, retry_on=("harbor_workflow_failed",)),
            retryable_error_codes=("harbor_workflow_failed",),
        )


def test_repair_patch_proposal_rejects_unknown_patch_shape() -> None:
    with pytest.raises(ValueError, match="repair patch"):
        RepairPatchProposal.model_validate(
            {
                "owner": "program",
                "code": "unsupported",
                "message": "Arbitrary executable patches are prohibited.",
                "patch": {"kind": "shell_script", "source": "exit 0"},
            }
        )


@pytest.mark.parametrize(
    "failure_domain",
    [RepairFailureDomain.HARNESS, RepairFailureDomain.PROGRAM],
)
def test_no_patch_proposal_can_name_a_known_mutable_domain_without_claiming_an_owner(
    failure_domain: RepairFailureDomain,
) -> None:
    proposal = RepairNoPatchProposal(
        failure_domain=failure_domain,
        code="no_allowlisted_patch",
        message="Evidence identifies the domain but no allowlisted patch applies.",
        evidence_codes=("verified_failure",),
    )

    assert proposal.failure_domain is failure_domain


def test_no_patch_proposal_still_requires_unique_evidence_codes() -> None:
    with pytest.raises(ValueError, match="evidence codes must be unique"):
        RepairNoPatchProposal(
            failure_domain=RepairFailureDomain.PROGRAM,
            code="no_allowlisted_patch",
            message="Evidence identifies the domain but no allowlisted patch applies.",
            evidence_codes=("verified_failure", "verified_failure"),
        )


def _runtime(
    tmp_path: Path,
    *,
    agent_capability_id: str = "aecbench.adapter.tool-loop",
) -> tuple[RepairRuntime, RewardByTurnsHarborExecutor]:
    executor = RewardByTurnsHarborExecutor()
    runtime = _build_runtime(
        tmp_path,
        executor=executor,
        diagnosis=lambda evidence: RepairPatchProposal(
            owner=RepairOwner.HARNESS,
            code="insufficient_turn_budget",
            message=f"{len(evidence.trials)} verifier outcomes failed under the Hx turn limit.",
            patch=HarnessAgentMaxTurnsPatch(binding_id="agent", max_turns=2),
        ),
        agent_capability_id=agent_capability_id,
    )
    return runtime, executor


def _build_runtime(
    tmp_path: Path,
    *,
    executor: HarborCommandExecutor,
    diagnosis: DiagnosisFunction,
    limits: ProgramLimits | None = None,
    acceptance_policy: RepairAcceptancePolicy | None = None,
    agent_capability_id: str = "aecbench.adapter.tool-loop",
    agent_max_turns: int = 1,
    task_ids: tuple[str, ...] | None = None,
    authority_ledger: AuthorityLedger | None = None,
) -> RepairRuntime:
    registry = default_kernel_registry()
    tasks_root = tmp_path / "tasks"
    resolved_task_ids = task_ids or ("civil/calculation/runtime-repair",)
    for task_id in resolved_task_ids:
        _write_task(tasks_root, task_id)
    budget = HarnessBudget()
    pairing = RepairPairingSpec(
        split="repair_gate",
        task_ids=resolved_task_ids,
        seeds=(17, 29),
        budget=budget,
        repetitions=2,
    )
    parent = _parent_candidate(
        task_ids=resolved_task_ids,
        budget=budget,
        limits=limits,
        agent_capability_id=agent_capability_id,
        agent_max_turns=agent_max_turns,
    )
    request = RepairLoopRequest(
        loop_id="repair-runtime.loop",
        attempt_id="repair-runtime.attempt-1",
        iteration=1,
        parent_candidate_id=parent.candidate_id,
        child_candidate_id="candidate.child",
        pairing=pairing,
        acceptance_policy=acceptance_policy
        or RepairAcceptancePolicy(
            minimum_mean_reward_delta=0.1,
            bootstrap_replicates=32,
        ),
    )
    return RepairRuntime(
        request=request,
        parent=parent,
        registry=registry,
        workflow=SynchronousHarborWorkflow(
            project_root=tmp_path,
            repo_root=tmp_path,
            tasks_root=tasks_root,
            ledger_root=tmp_path / "ledger",
            jobs_root=tmp_path / "jobs",
        ),
        artifacts_root=tmp_path / "meta-harness-artifacts",
        policy_id="policy.repair.runtime",
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        verifier_policy=RepairVerifierPolicy(
            minimum_reward=0.5,
            require_complete_provenance=True,
        ),
        evidence_use_policy=RepairEvidenceUsePolicy.calibration_gated_adaptive_cycle(),
        diagnosis=diagnosis,
        executor=executor,
        authority_ledger=authority_ledger,
    )


def test_runtime_rejects_motif_eligible_policy_with_standalone_spec_reference(
    tmp_path: Path,
) -> None:
    fixture = _build_runtime(
        tmp_path,
        executor=RewardByTurnsHarborExecutor(),
        diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("diagnosis must not run")),
    )
    spec_path = tmp_path / "standalone-repair-spec.json"
    spec_bytes = b"{}\n"
    spec_path.write_bytes(spec_bytes)
    spec_reference = ArtifactReference(
        kind="repair-run-spec",
        path=str(spec_path),
        sha256=hashlib.sha256(spec_bytes).hexdigest(),
        media_type="application/json",
    )

    with pytest.raises(ValueError, match="standalone repair runtime"):
        RepairRuntime(
            request=fixture.request,
            parent=fixture.parent,
            registry=fixture.registry,
            workflow=fixture.workflow,
            artifacts_root=tmp_path / "forbidden-standalone-runtime",
            policy_id=fixture.policy_id,
            harness_generator_sha256=fixture.harness_generator_sha256,
            program_generator_sha256=fixture.program_generator_sha256,
            verifier_policy=fixture.verifier_policy,
            evidence_use_policy=RepairEvidenceUsePolicy.calibration_gated_adaptive_cycle(),
            diagnosis=lambda _evidence: (_ for _ in ()).throw(AssertionError("diagnosis must not run")),
            repair_run_spec=spec_reference,
            executor=RewardByTurnsHarborExecutor(),
        )


def _attempt_limit_runtime(
    tmp_path: Path,
) -> tuple[RepairRuntime, SuccessfulTaskSelectedHarborExecutor, tuple[str, str]]:
    registry = default_kernel_registry()
    tasks_root = tmp_path / "tasks"
    task_ids = (
        "civil/calculation/runtime-repair-alpha",
        "civil/calculation/runtime-repair-beta",
    )
    for task_id in task_ids:
        _write_task(tasks_root, task_id)
    budget = HarnessBudget(
        max_total_attempts=2,
        max_parallelism=1,
    )
    nodes = (
        ActionNode(
            node_id="run-alpha",
            operation_id="run_batch",
            arguments=(
                ProgramArgument(
                    name="task_ref",
                    value=LiteralValue(value=task_ids[0]),
                ),
            ),
        ),
        ActionNode(
            node_id="run-beta",
            depends_on=("run-alpha",),
            operation_id="run_batch",
            arguments=(
                ProgramArgument(
                    name="task_ref",
                    value=LiteralValue(value=task_ids[1]),
                ),
            ),
        ),
        StopNode(
            node_id="stop",
            depends_on=("run-beta",),
            outcome=StopOutcome.SUCCEEDED,
        ),
    )
    parent = _parent_candidate(
        task_ids=task_ids,
        budget=budget,
        nodes=nodes,
        limits=ProgramLimits(max_total_attempts=1, max_parallelism=1),
    )
    pairing = RepairPairingSpec(
        split="repair_gate",
        task_ids=task_ids,
        seeds=(17,),
        budget=budget,
        repetitions=1,
    )
    request = RepairLoopRequest(
        loop_id="repair-runtime.attempt-limit-loop",
        attempt_id="repair-runtime.attempt-limit-1",
        iteration=1,
        parent_candidate_id=parent.candidate_id,
        child_candidate_id="candidate.attempt-limit-child",
        pairing=pairing,
        acceptance_policy=RepairAcceptancePolicy(
            minimum_mean_reward_delta=0.1,
            bootstrap_replicates=32,
        ),
    )
    executor = SuccessfulTaskSelectedHarborExecutor()
    runtime = RepairRuntime(
        request=request,
        parent=parent,
        registry=registry,
        workflow=SynchronousHarborWorkflow(
            project_root=tmp_path,
            repo_root=tmp_path,
            tasks_root=tasks_root,
            ledger_root=tmp_path / "ledger",
            jobs_root=tmp_path / "jobs",
        ),
        artifacts_root=tmp_path / "meta-harness-artifacts",
        policy_id="policy.repair.program-attempt-limit",
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        verifier_policy=RepairVerifierPolicy(
            minimum_reward=0.5,
            require_complete_provenance=True,
        ),
        evidence_use_policy=RepairEvidenceUsePolicy.calibration_gated_adaptive_cycle(),
        diagnosis=lambda evidence: diagnose_program_attempt_limit(
            evidence,
            max_total_attempts=2,
        ),
        executor=executor,
    )
    return runtime, executor, task_ids


def _batch_coalescing_runtime(
    tmp_path: Path,
) -> tuple[RepairRuntime, SuccessfulTaskSelectedHarborExecutor, tuple[str, str]]:
    registry = default_kernel_registry()
    tasks_root = tmp_path / "tasks"
    task_ids = (
        "civil/calculation/runtime-batch-alpha",
        "civil/calculation/runtime-batch-beta",
    )
    for task_id in task_ids:
        _write_task(tasks_root, task_id)
    budget = HarnessBudget(
        max_agent_turns=2,
        max_total_attempts=1,
        max_parallelism=1,
    )
    nodes = (
        ActionNode(
            node_id="run-primary",
            operation_id="run_batch",
            arguments=(ProgramArgument(name="task_ref", value=LiteralValue(value=task_ids[0])),),
        ),
        ActionNode(
            node_id="run-secondary",
            depends_on=("run-primary",),
            operation_id="run_batch",
            arguments=(ProgramArgument(name="task_ref", value=LiteralValue(value=task_ids[1])),),
        ),
        StopNode(
            node_id="stop",
            depends_on=("run-secondary",),
            outcome=StopOutcome.SUCCEEDED,
        ),
    )
    parent = _parent_candidate(
        task_ids=task_ids,
        budget=budget,
        nodes=nodes,
        limits=ProgramLimits(max_total_attempts=1, max_parallelism=1),
    )
    pairing = RepairPairingSpec(
        split="repair_gate",
        task_ids=task_ids,
        seeds=(17,),
        budget=budget,
        repetitions=1,
    )
    request = RepairLoopRequest(
        loop_id="repair-runtime.batch-coalescing-loop",
        attempt_id="repair-runtime.batch-coalescing-1",
        iteration=1,
        parent_candidate_id=parent.candidate_id,
        child_candidate_id="candidate.batch-coalescing-child",
        pairing=pairing,
        acceptance_policy=RepairAcceptancePolicy(
            minimum_mean_reward_delta=0.1,
            bootstrap_replicates=32,
        ),
    )
    executor = SuccessfulTaskSelectedHarborExecutor()
    runtime = RepairRuntime(
        request=request,
        parent=parent,
        registry=registry,
        workflow=SynchronousHarborWorkflow(
            project_root=tmp_path,
            repo_root=tmp_path,
            tasks_root=tasks_root,
            ledger_root=tmp_path / "ledger",
            jobs_root=tmp_path / "jobs",
        ),
        artifacts_root=tmp_path / "meta-harness-artifacts",
        policy_id="policy.repair.program-batch-coalescing",
        harness_generator_sha256="1" * 64,
        program_generator_sha256="2" * 64,
        verifier_policy=RepairVerifierPolicy(
            minimum_reward=0.5,
            require_complete_provenance=True,
        ),
        evidence_use_policy=RepairEvidenceUsePolicy.calibration_gated_adaptive_cycle(),
        diagnosis=lambda evidence: diagnose_program_batch_coalescing(
            evidence,
            source_node_ids=("run-primary", "run-secondary"),
            replacement_node_id="run-coalesced",
            task_refs=task_ids,
        ),
        executor=executor,
    )
    return runtime, executor, task_ids


def _drift_pairing(pairing: RepairPairingSpec, drift: str) -> RepairPairingSpec:
    if drift == "tasks":
        return RepairPairingSpec(
            split=pairing.split,
            task_ids=("civil/calculation/different",),
            seeds=pairing.seeds,
            budget=pairing.budget,
            repetitions=pairing.repetitions,
        )
    if drift == "seeds":
        return RepairPairingSpec(
            split=pairing.split,
            task_ids=pairing.task_ids,
            seeds=(31, 43),
            budget=pairing.budget,
            repetitions=pairing.repetitions,
        )
    if drift == "budget":
        return RepairPairingSpec(
            split=pairing.split,
            task_ids=pairing.task_ids,
            seeds=pairing.seeds,
            budget=pairing.budget.model_copy(update={"max_tool_calls": pairing.budget.max_tool_calls + 1}),
            repetitions=pairing.repetitions,
        )
    return RepairPairingSpec(
        split=pairing.split,
        task_ids=pairing.task_ids,
        seeds=(pairing.seeds[0],),
        budget=pairing.budget,
        repetitions=1,
    )


def _parent_candidate(
    *,
    task_ids: tuple[str, ...],
    budget: HarnessBudget,
    nodes: tuple[ActionNode | StopNode, ...] | None = None,
    limits: ProgramLimits | None = None,
    agent_capability_id: str = "aecbench.adapter.tool-loop",
    agent_max_turns: int = 1,
) -> RepairCandidate:
    registry = default_kernel_registry()
    capability = registry.capability
    recipe = HarnessSpec(
        summary="Run an exact task through the fixed kernel for paired repair.",
        budget=budget,
        bindings=(
            HarnessBindingSpec(
                binding_id="tasks",
                capability_ref=capability("aecbench.tasks.registry").ref,
                topology_role=HarnessTopologyRole.SOURCE,
                configuration=TaskSourceBindingConfig(task_refs=task_ids),
            ),
            HarnessBindingSpec(
                binding_id="agent",
                capability_ref=capability(agent_capability_id).ref,
                depends_on=("tasks",),
                topology_role=HarnessTopologyRole.ORCHESTRATOR,
                configuration=AgentBindingConfig(
                    agent_name="repair-agent",
                    model="claude-test-model",
                    max_turns=agent_max_turns,
                    timeout_seconds=300,
                ),
            ),
            HarnessBindingSpec(
                binding_id="compute",
                capability_ref=capability("aecbench.backend.harbor.docker").ref,
                depends_on=("agent",),
                topology_role=HarnessTopologyRole.SERVICE,
                configuration=ComputeBindingConfig(max_concurrency=1),
            ),
            HarnessBindingSpec(
                binding_id="verify",
                capability_ref=capability("aecbench.verifier.task").ref,
                depends_on=("compute",),
                topology_role=HarnessTopologyRole.GATE,
                configuration=VerificationBindingConfig(enabled=True, required=True),
            ),
            HarnessBindingSpec(
                binding_id="import",
                capability_ref=capability("aecbench.results.trial-record").ref,
                depends_on=("verify",),
                topology_role=HarnessTopologyRole.SINK,
                configuration=ResultImportBindingConfig(
                    ledger_namespace="repair-runtime",
                ),
            ),
        ),
    )
    return RepairCandidate(
        candidate_id="candidate.parent",
        parent_candidate_id=None,
        iteration=0,
        harness_request=HarnessCompileRequest(
            request_id="compile.repair.parent",
            kernel_ref=registry.manifest.ref,
            spec=recipe,
        ),
        program_template=RepairProgramTemplate(
            program_id="program.repair",
            version="1.0.0",
            nodes=nodes
            or (
                ActionNode(node_id="run", operation_id="run_batch"),
                StopNode(
                    node_id="stop",
                    depends_on=("run",),
                    outcome=StopOutcome.SUCCEEDED,
                ),
            ),
            limits=limits or ProgramLimits(),
        ),
    )


def _write_task(tasks_root: Path, task_id: str) -> None:
    task_dir = tasks_root / task_id
    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "tests").mkdir()
    (task_dir / "task.toml").write_text(
        """
[metadata]
difficulty = "easy"
visibility = "public"
tags = ["repair-runtime"]

[agent]
timeout_sec = 300
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (task_dir / "instruction.md").write_text("Write /workspace/output.md.\n", encoding="utf-8")
    (task_dir / "environment" / "Dockerfile").write_text("FROM python:3.13-slim\n", encoding="utf-8")
    (task_dir / "environment" / "output_contract.json").write_text(
        json.dumps(
            {
                "schema_version": "aecbench.output-completion-contract.v1",
                "output_path": "/workspace/output.md",
                "format": "markdown_final_fenced_json",
                "required_top_level_keys": ["answer"],
                "require_single_final_json_block": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    verifier = task_dir / "tests" / "test.sh"
    verifier.write_text(
        "#!/bin/sh\n"
        "# ABOUTME: Verifies that the repair-runtime fixture produced an output artifact.\n"
        "# ABOUTME: Emits a deterministic reward through Harbor's verifier contract.\n"
        "test -s /workspace/output.md\n",
        encoding="utf-8",
    )
    verifier.chmod(0o755)


def _write_declared_stage_review(task_dir: Path) -> None:
    (task_dir / "task-review.json").write_text(
        json.dumps(
            {
                "profile_id": "aec.task-review.civil.repair-runtime-staged",
                "name": "Repair runtime staged review",
                "task_unit": "generated-task-instance",
                "logic_profile": {"agentic_review": {"required": True}},
                "stages": [
                    {
                        "id": "inventory",
                        "consumes": ["document_register"],
                        "produces": ["source_inventory"],
                    },
                    {
                        "id": "authority",
                        "consumes": ["source_inventory"],
                        "produces": ["provenance_ledger"],
                    },
                    {
                        "id": "decision",
                        "consumes": ["source_inventory", "provenance_ledger"],
                        "produces": ["readiness_decision"],
                    },
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
