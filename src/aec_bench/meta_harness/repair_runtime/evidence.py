# ABOUTME: Interprets imported runtime and verifier records into immutable repair evidence.
# ABOUTME: Extracts trusted execution signals without deciding or applying candidate patches.

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from pydantic import JsonValue

from aec_bench.adapters.base import AdapterCompletionReason, AdapterStopReason
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.execution_program import ActionNode, StopNode
from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.output_completion import (
    OutputCommitAttestation,
    OutputCompletionContract,
    evaluate_output_completion,
)
from aec_bench.contracts.run_bundle import RunBundle, TaskSnapshotRef
from aec_bench.contracts.trial_record import Completeness, TrialRecord
from aec_bench.evolution.paired_repair import RepairTrialOutcome
from aec_bench.evolution.repair_loop import (
    CompiledRepairCandidate,
    RepairExecutionObservation,
    RepairExecutionStatus,
    RepairPairingSpec,
    RepairProgramTemplate,
    RepairRewardCoverage,
    RepairRunObservation,
    RepairRunResult,
)
from aec_bench.meta_harness.program_runtime import NodeExecutionStatus
from aec_bench.meta_harness.repair_runtime.contracts import (
    RepairAgentExecutionEvidence,
    RepairMonolithicRunBatchEvidence,
    RepairOutputArtifactEvidence,
    RepairProgramExecutionEvidence,
    RepairProgramNodeFailureEvidence,
    RepairRunArtifactManifest,
    RepairSeedExecution,
    RepairTrialEvidence,
    RepairVerifierEvidence,
    RepairVerifierPolicy,
)
from aec_bench.meta_harness.repair_runtime.patching import (
    validate_program_declared_stage_graph_source,
)
from aec_bench.meta_harness.repair_runtime.persistence import StoredRepairRunArtifact
from aec_bench.meta_harness.run_bundle_runtime import RunBundleExecution


@dataclass(frozen=True)
class _SeedCapture:
    manifest: RepairSeedExecution
    bundle: RunBundle
    execution: RunBundleExecution


@dataclass(frozen=True)
class _RunCapture:
    compiled: CompiledRepairCandidate
    manifest: RepairRunArtifactManifest
    artifact: StoredRepairRunArtifact
    seeds: tuple[_SeedCapture, ...]


_TASK_WORLD_INTERFACE_EVENT_CANDIDATES = frozenset(
    {
        "task_interface_gap",
        "verifier_language_gap",
    }
)


def _repair_agent_evidence(
    record: TrialRecord,
    *,
    repo_root: Path,
    tasks_root: Path,
) -> RepairAgentExecutionEvidence:
    result = record.outputs.agent_result or {}
    output = record.outputs.agent_output
    max_turns = _evidence_int(result.get("max_turns"))
    output_artifact = _repair_output_artifact_evidence(
        record,
        repo_root=repo_root,
        tasks_root=tasks_root,
    )
    return RepairAgentExecutionEvidence(
        status=output.status if output is not None else AgentOutputStatus.EMPTY,
        failure_kind=_evidence_string(result.get("failure_kind")),
        stop_reason=result.get("stop_reason"),
        provider_error=_evidence_string(result.get("provider_error")),
        turns_used=_evidence_int(result.get("turns_used")),
        max_turns=max_turns,
        lifecycle_status=_evidence_string(result.get("lifecycle_status")),
        runtime_execution_attested=isinstance(result.get("runtime_execution_attestation"), dict),
        output_artifact=output_artifact,
        output_commit_attested=_has_output_commit_attestation(
            result,
            output_artifact,
        ),
    )


def _requires_output_contract_completion_evidence(candidate: CompiledRepairCandidate) -> bool:
    if candidate.parent_candidate_id is None:
        return False
    binding = candidate.harness.binding(candidate.bundle.harbor.agent_binding_id)
    return binding is not None and binding.capability_ref.capability_id == "aecbench.adapter.rlm-output-contract"


def _requires_output_commit_completion_evidence(candidate: CompiledRepairCandidate) -> bool:
    binding = candidate.harness.binding(candidate.bundle.harbor.agent_binding_id)
    return binding is not None and binding.capability_ref.capability_id == "aecbench.adapter.rlm-output-commit"


def _has_output_contract_completion_assistance(result: dict[str, Any] | None) -> bool:
    if result is None or result.get("completion_reason") != AdapterCompletionReason.OUTPUT_CONTRACT_SATISFIED.value:
        return False
    evidence = result.get("completion_assistance")
    if not isinstance(evidence, dict):
        return False
    reminder_turn = evidence.get("reminder_turn")
    explicit_final_turn = evidence.get("explicit_final_turn")
    if (
        evidence.get("contract_satisfied") is not True
        or evidence.get("reminder_sent") is not True
        or not isinstance(reminder_turn, int)
        or isinstance(reminder_turn, bool)
        or not isinstance(explicit_final_turn, int)
        or isinstance(explicit_final_turn, bool)
        or reminder_turn < 1
        or explicit_final_turn <= reminder_turn
    ):
        return False
    turns_used = result.get("turns_used")
    return isinstance(turns_used, int) and not isinstance(turns_used, bool) and explicit_final_turn == turns_used


def _has_output_commit_attestation(
    result: dict[str, Any] | None,
    output_artifact: RepairOutputArtifactEvidence | None,
) -> bool:
    if (
        result is None
        or output_artifact is None
        or result.get("completion_reason") != AdapterCompletionReason.OUTPUT_CONTRACT_COMMITTED.value
        or result.get("completion_assistance") is not None
    ):
        return False
    raw_attestation = result.get("completion_commit")
    if not isinstance(raw_attestation, dict):
        return False
    try:
        attestation = OutputCommitAttestation.model_validate(raw_attestation)
    except ValueError:
        return False
    turns_used = result.get("turns_used")
    return (
        isinstance(turns_used, int)
        and not isinstance(turns_used, bool)
        and attestation.commit_turn == turns_used
        and Path(attestation.output_path).name == Path(output_artifact.path).name
        and attestation.output_sha256 == output_artifact.sha256
        and attestation.output_size_bytes == output_artifact.size_bytes
        and attestation.completion_contract_sha256 == output_artifact.completion_contract_content_sha256
        and attestation.completion_evaluation == output_artifact.completion_evaluation
    )


def _repair_output_artifact_evidence(
    record: TrialRecord,
    *,
    repo_root: Path,
    tasks_root: Path,
) -> RepairOutputArtifactEvidence | None:
    raw_output_path = record.outputs.raw_output_path
    declared_output = record.outputs.agent_output
    if raw_output_path is None or declared_output is None:
        return None
    root = repo_root.resolve()
    output = _resolve_output_artifact(
        raw_output_path=raw_output_path,
        declared_output_path=declared_output.output_path,
        root=root,
    )
    if output is None:
        return None
    relative, resolved, encoded = output
    contract_evidence = _load_bound_completion_contract(
        record,
        root=root,
        tasks_root=tasks_root,
        output_encoded=encoded,
    )
    if contract_evidence is None:
        return None
    contract_encoded, contract, output_text = contract_evidence
    if contract.output_path != declared_output.output_path:
        return None
    completion_evaluation = evaluate_output_completion(contract, output_text)
    media_type = {
        ".md": "text/markdown",
        ".jsonl": "application/x-ndjson",
    }.get(resolved.suffix.lower(), "application/octet-stream")
    return RepairOutputArtifactEvidence(
        path=relative.as_posix(),
        sha256=hashlib.sha256(encoded).hexdigest(),
        media_type=media_type,
        size_bytes=len(encoded),
        completion_contract_sha256=hashlib.sha256(contract_encoded).hexdigest(),
        completion_contract_content_sha256=canonical_content_sha256(contract.model_dump(mode="json")),
        completion_evaluation=completion_evaluation,
    )


def _resolve_output_artifact(
    *,
    raw_output_path: str,
    declared_output_path: str,
    root: Path,
) -> tuple[Path, Path, bytes] | None:
    path = Path(raw_output_path)
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError:
        return None
    if resolved.name != Path(declared_output_path).name or not resolved.is_file():
        return None
    encoded = resolved.read_bytes()
    if not encoded.strip():
        return None
    return relative, resolved, encoded


def _load_bound_completion_contract(
    record: TrialRecord,
    *,
    root: Path,
    tasks_root: Path,
    output_encoded: bytes,
) -> tuple[bytes, OutputCompletionContract, str] | None:
    task_root = tasks_root.resolve()
    contract_path = (task_root / record.task.task_id / "environment" / "output_contract.json").resolve()
    try:
        contract_path.relative_to(task_root)
    except ValueError:
        return None
    if not contract_path.is_file():
        return None
    contract_encoded = contract_path.read_bytes()
    try:
        contract_relative_path = contract_path.relative_to(root).as_posix()
    except ValueError:
        return None
    contract_references = tuple(
        reference
        for reference in record.inputs.input_files or ()
        if reference.path == contract_relative_path and reference.source == "output_completion_contract"
    )
    if len(contract_references) != 1 or contract_references[0].hash != hashlib.sha256(contract_encoded).hexdigest():
        return None
    try:
        contract = OutputCompletionContract.model_validate_json(contract_encoded)
        output_text = output_encoded.decode("utf-8")
    except (OSError, UnicodeError, ValueError):
        return None
    return contract_encoded, contract, output_text


def _is_exact_harness_turn_limit(evidence: RepairAgentExecutionEvidence) -> bool:
    return (
        evidence.failure_kind == "turn_limit_reached"
        and evidence.stop_reason is AdapterStopReason.ITERATION_CAP
        and evidence.runtime_execution_attested
        and evidence.turns_used is not None
        and evidence.max_turns is not None
        and evidence.turns_used == evidence.max_turns
    )


def _repair_verifier_evidence(record: TrialRecord) -> RepairVerifierEvidence:
    validity = record.evaluation.validity
    breakdown: dict[str, JsonValue] | None = None
    if record.evaluation.breakdown is not None:
        serialized = json.loads(
            json.dumps(
                record.evaluation.breakdown,
                allow_nan=False,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        if not isinstance(serialized, dict):
            raise ValueError("verifier breakdown must be a JSON object")
        breakdown = cast(dict[str, JsonValue], serialized)
    return RepairVerifierEvidence(
        output_parseable=validity.output_parseable,
        schema_valid=validity.schema_valid,
        completed=validity.verifier_completed,
        errors=tuple(validity.errors),
        breakdown=breakdown,
    )


def _verifier_execution_failed(evidence: RepairVerifierEvidence) -> bool:
    if not evidence.completed:
        return True
    if evidence.breakdown is None:
        return False
    error = evidence.breakdown.get("error")
    return isinstance(error, str) and bool(error.strip())


def _has_task_world_interface_event(evidence: RepairVerifierEvidence) -> bool:
    if evidence.breakdown is None:
        return False
    reviewer = evidence.breakdown.get("llm_reviewer")
    if not isinstance(reviewer, dict):
        return False
    candidates = reviewer.get("event_candidates")
    if not isinstance(candidates, list):
        return False
    return any(
        isinstance(candidate, str) and candidate in _TASK_WORLD_INTERFACE_EVENT_CANDIDATES for candidate in candidates
    )


def _repair_program_evidence(capture: _SeedCapture) -> RepairProgramExecutionEvidence:
    program = capture.execution.program
    failed_nodes = tuple(
        RepairProgramNodeFailureEvidence(
            node_id=node.node_id,
            error_code=node.error_code or "program_node_failed_without_code",
            error_message=node.error_message,
        )
        for node in program.node_evidence
        if node.status is NodeExecutionStatus.FAILED
    )
    return RepairProgramExecutionEvidence(
        repetition=capture.manifest.repetition,
        seed=capture.manifest.seed,
        status=program.status,
        error_code=program.error_code,
        error_message=program.error_message,
        total_attempts=program.total_attempts,
        failed_nodes=failed_nodes,
    )


def _repair_execution_observation(capture: _SeedCapture) -> RepairExecutionObservation:
    program = capture.execution.program
    failed_node = next(
        (node.node_id for node in program.node_evidence if node.status is NodeExecutionStatus.FAILED),
        None,
    )
    return RepairExecutionObservation(
        repetition=capture.manifest.repetition,
        seed=capture.manifest.seed,
        status=RepairExecutionStatus(program.status.value),
        error_code=program.error_code,
        failed_node_id=failed_node,
    )


def _interpret_records(
    *,
    candidate: CompiledRepairCandidate,
    run: RepairRunResult,
    capture: _RunCapture,
    records: tuple[TrialRecord, ...],
    repo_root: Path,
    tasks_root: Path,
    verifier_policy: RepairVerifierPolicy,
) -> tuple[
    tuple[RepairTrialEvidence, ...],
    tuple[RepairRunObservation, ...],
    tuple[str, ...],
]:
    records_by_run_and_task = {
        (record.meta_harness_provenance.run_id, record.task.task_id): record
        for record in records
        if record.meta_harness_provenance is not None
    }
    evidence: list[RepairTrialEvidence] = []
    observations: list[RepairRunObservation] = []
    all_diagnostics: list[str] = []
    require_completion_evidence = _requires_output_contract_completion_evidence(candidate)
    require_commit_evidence = _requires_output_commit_completion_evidence(candidate)
    for seed_capture in capture.seeds:
        repetition = seed_capture.manifest.repetition
        seed = seed_capture.manifest.seed
        for task_id in run.pairing.task_ids:
            record = records_by_run_and_task.get((seed_capture.manifest.run_id, task_id))
            if record is None:
                continue
            trial_evidence, observation, diagnostics = _interpret_trial_record(
                candidate=candidate,
                pairing=run.pairing,
                record=record,
                task_id=task_id,
                repetition=repetition,
                seed=seed,
                repo_root=repo_root,
                tasks_root=tasks_root,
                verifier_policy=verifier_policy,
                require_completion_evidence=require_completion_evidence,
                require_commit_evidence=require_commit_evidence,
            )
            evidence.append(trial_evidence)
            observations.append(observation)
            all_diagnostics.extend(diagnostics)
    return tuple(evidence), tuple(observations), tuple(sorted(set(all_diagnostics)))


def _interpret_trial_record(
    *,
    candidate: CompiledRepairCandidate,
    pairing: RepairPairingSpec,
    record: TrialRecord,
    task_id: str,
    repetition: int,
    seed: int,
    repo_root: Path,
    tasks_root: Path,
    verifier_policy: RepairVerifierPolicy,
    require_completion_evidence: bool,
    require_commit_evidence: bool,
) -> tuple[RepairTrialEvidence, RepairRunObservation, tuple[str, ...]]:
    validity = record.evaluation.validity
    valid = validity.output_parseable and validity.schema_valid and validity.verifier_completed
    complete = record.completeness is Completeness.COMPLETE
    agent_evidence = _repair_agent_evidence(
        record,
        repo_root=repo_root,
        tasks_root=tasks_root,
    )
    verifier_evidence = _repair_verifier_evidence(record)
    diagnostics = (
        *_agent_diagnostic_codes(
            record,
            agent_evidence=agent_evidence,
            require_completion_evidence=require_completion_evidence,
            require_commit_evidence=require_commit_evidence,
        ),
        *_verifier_diagnostic_codes(
            record,
            verifier_evidence=verifier_evidence,
            verifier_policy=verifier_policy,
            valid=valid,
            complete=complete,
        ),
    )
    estimated_cost = _estimated_trial_cost(record)
    if estimated_cost is None:
        diagnostics = (*diagnostics, "cost_evidence_incomplete")
    snapshot = _snapshot(candidate.bundle, task_id)
    world_lineage_sha256 = (
        snapshot.world.world_package_sha256 if snapshot.world is not None else snapshot.package_sha256
    )
    trial_evidence = RepairTrialEvidence(
        trial_id=record.trial_id,
        task_id=task_id,
        repetition=repetition,
        seed=seed,
        reward=record.evaluation.reward,
        complete=complete,
        valid=valid,
        agent=agent_evidence,
        verifier=verifier_evidence,
        resource_sha256=snapshot.package_sha256,
        world_lineage_sha256=world_lineage_sha256,
        estimated_cost_usd=estimated_cost,
        error_codes=diagnostics,
    )
    observation = RepairRunObservation(
        seed=seed,
        outcome=RepairTrialOutcome(
            block_id=_block_id(
                pairing=pairing,
                task_id=task_id,
                repetition=repetition,
                seed=seed,
            ),
            task_world_id=task_id,
            repetition=repetition,
            split=pairing.split,
            candidate_id=candidate.candidate_id,
            kernel_sha256=candidate.harness.kernel_ref.content_sha256,
            resource_sha256=snapshot.package_sha256,
            world_lineage_sha256=world_lineage_sha256,
            reward=record.evaluation.reward,
            complete=complete,
            valid=valid,
            cost=estimated_cost,
        ),
    )
    return trial_evidence, observation, diagnostics


def _agent_diagnostic_codes(
    record: TrialRecord,
    *,
    agent_evidence: RepairAgentExecutionEvidence,
    require_completion_evidence: bool,
    require_commit_evidence: bool,
) -> tuple[str, ...]:
    diagnostics: list[str] = []
    if agent_evidence.status is not AgentOutputStatus.COMPLETED:
        diagnostics.append("agent_execution_failed")
    if agent_evidence.failure_kind is not None:
        diagnostics.append(f"agent_failure:{agent_evidence.failure_kind}")
        if _is_exact_harness_turn_limit(agent_evidence):
            diagnostics.append("harness_turn_limit_reached")
        elif agent_evidence.failure_kind == "turn_limit_reached":
            diagnostics.append("runtime_stop_evidence_incomplete")
    if agent_evidence.stop_reason is not None:
        diagnostics.append(f"agent_stop:{agent_evidence.stop_reason.value}")
    if agent_evidence.lifecycle_status not in {None, "complete"}:
        diagnostics.append("lifecycle_execution_incomplete")
    if require_completion_evidence and not _has_output_contract_completion_assistance(record.outputs.agent_result):
        diagnostics.append("completion_capability_not_exercised")
    if require_commit_evidence and not agent_evidence.output_commit_attested:
        diagnostics.append("completion_capability_not_exercised")
    return tuple(diagnostics)


def _verifier_diagnostic_codes(
    record: TrialRecord,
    *,
    verifier_evidence: RepairVerifierEvidence,
    verifier_policy: RepairVerifierPolicy,
    valid: bool,
    complete: bool,
) -> tuple[str, ...]:
    diagnostics: list[str] = []
    if _verifier_execution_failed(verifier_evidence):
        diagnostics.append("verifier_execution_failed")
    if _has_task_world_interface_event(verifier_evidence):
        diagnostics.append("task_world_interface_mismatch")
    if verifier_policy.require_valid and not valid:
        diagnostics.append("invalid_verifier_evidence")
    if verifier_policy.require_complete_provenance and not complete:
        diagnostics.append("incomplete_trial_provenance")
    if record.evaluation.reward < verifier_policy.minimum_reward:
        diagnostics.append("reward_below_verifier_threshold")
    return tuple(diagnostics)


def _estimated_trial_cost(record: TrialRecord) -> float | None:
    if record.cost is None or record.cost.estimated_cost_usd is None:
        return None
    return float(record.cost.estimated_cost_usd)


def _reward_coverage(
    pairing: RepairPairingSpec,
    observations: tuple[RepairRunObservation, ...],
) -> RepairRewardCoverage:
    if not observations:
        return RepairRewardCoverage.NONE
    expected = len(pairing.task_ids) * pairing.repetitions
    if len(observations) == expected:
        return RepairRewardCoverage.COMPLETE
    return RepairRewardCoverage.PARTIAL


def _evidence_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("runtime diagnostic string evidence must be non-blank")
    return value


def _evidence_int(value: Any) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("runtime diagnostic integer evidence must be a non-negative integer")
    return value


def _monolithic_run_batch_evidence(
    nodes: tuple[object, ...],
    *,
    task_refs: tuple[str, ...],
) -> RepairMonolithicRunBatchEvidence | None:
    if len(nodes) != 2:
        return None
    run, stop = nodes
    if not isinstance(run, ActionNode) or not isinstance(stop, StopNode):
        return None
    template = RepairProgramTemplate(
        program_id="program.evidence-shape",
        version="1",
        nodes=(run, stop),
    )
    try:
        validate_program_declared_stage_graph_source(template, task_refs=task_refs)
    except ValueError:
        return None
    return RepairMonolithicRunBatchEvidence(
        run_node_id=run.node_id,
        stop_node_id=stop.node_id,
        task_refs=task_refs,
    )


def _snapshot(bundle: RunBundle, task_id: str) -> TaskSnapshotRef:
    matches = [snapshot for snapshot in bundle.task_snapshots if snapshot.task_id == task_id]
    if len(matches) != 1:
        raise ValueError(f"repair evidence task is absent from exact snapshots: {task_id}")
    return matches[0]


def _block_id(
    *,
    pairing: RepairPairingSpec,
    task_id: str,
    repetition: int,
    seed: int,
) -> str:
    identity = canonical_content_sha256(
        {
            "pairing": pairing.model_dump(mode="json"),
            "task_id": task_id,
            "repetition": repetition,
            "seed": seed,
        }
    )
    return f"repair-block.{identity[:24]}"
