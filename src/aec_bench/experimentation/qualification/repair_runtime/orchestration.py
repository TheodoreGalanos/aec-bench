# ABOUTME: Orchestrates the closed repair loop across compiler, Harbor, verifier, and authority boundaries.
# ABOUTME: Coordinates immutable contracts and canonical helpers without owning their implementations.

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityDecision,
    AuthorityEvent,
    AuthorityPrincipal,
    AuthorityPrincipalKind,
    BasisKind,
    TaintLabel,
)
from aec_bench.contracts.harness_kernel import FrozenStrictModel, canonical_json_sha256, validate_sha256
from aec_bench.contracts.run_bundle import RunBundle, TaskSnapshotRef
from aec_bench.contracts.trial_record import ArtifactReference, TrialRecord
from aec_bench.evolution.repair_lifecycle import (
    CompiledRepairCandidate,
    RepairCandidate,
    RepairDiagnosis,
    RepairFailureDomain,
    RepairLoopDependencies,
    RepairLoopRequest,
    RepairLoopResult,
    RepairLoopStatus,
    RepairOwner,
    RepairPairingSpec,
    RepairPatchRequest,
    RepairRewardCoverage,
    RepairRunObservation,
    RepairRunResult,
    VerifiedRepairRun,
    run_repair_loop,
)
from aec_bench.experimentation.governance.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerError,
    StoredAuthorityEvent,
    StoredBasis,
)
from aec_bench.experimentation.qualification.repair_runtime.contracts import (
    RepairAttemptPlan,
    RepairEvidenceUsePolicy,
    RepairNoPatchProposal,
    RepairPatchProposal,
    RepairRunArtifactManifest,
    RepairRuntimeEvidence,
    RepairSeedExecution,
    RepairTerminalRecord,
    RepairTrialEvidence,
    RepairVerifierPolicy,
)
from aec_bench.experimentation.qualification.repair_runtime.diagnosis import (
    _ACCEPTANCE_ONLY_DIAGNOSTIC_CODES,
    DiagnosisFunction,
)
from aec_bench.experimentation.qualification.repair_runtime.evidence import (
    _interpret_records as _interpret_imported_records,
)
from aec_bench.experimentation.qualification.repair_runtime.evidence import (
    _monolithic_run_batch_evidence,
    _repair_execution_observation,
    _repair_program_evidence,
    _reward_coverage,
    _RunCapture,
    _SeedCapture,
    _snapshot,
)
from aec_bench.experimentation.qualification.repair_runtime.patching import (
    _REPAIR_RULE_REGISTRY,
    _declared_stage_graph_evidence,
    _RepairPatchContext,
)
from aec_bench.experimentation.qualification.repair_runtime.persistence import (
    RepairRuntimeExecution,
    StoredRepairArtifact,
    StoredRepairRunArtifact,
    _artifact_identity,
    _file_reference,
    _verify_artifact_reference,
    _write_content_addressed,
)
from aec_bench.experimentation.qualification.run_bundle_runtime import (
    HarborInvocationReceipt,
    MetaHarnessStudyContext,
    RunBundleExecution,
    execute_run_bundle,
    load_harbor_invocation_receipt,
)
from aec_bench.harness.compilation import (
    compile_execution_program,
    compile_harness_instance,
    compile_run_bundle,
)
from aec_bench.harness.harbor_dispatch import HarborCommandExecutor
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.harness.kernel_catalogue import KernelRuntimeRegistry
from aec_bench.harness.program_execution import (
    OperationExecutionStatus,
    ProgramExecutionStatus,
)
from aec_bench.ledger.reader import read_trial_record


class RepairRuntime:
    """Concrete trusted-boundary adapter for one exact verifier-guided repair request."""

    def __init__(
        self,
        *,
        request: RepairLoopRequest,
        parent: RepairCandidate,
        registry: KernelRuntimeRegistry,
        workflow: SynchronousHarborWorkflow,
        artifacts_root: Path,
        policy_id: str,
        harness_generator_sha256: str,
        program_generator_sha256: str,
        verifier_policy: RepairVerifierPolicy,
        evidence_use_policy: RepairEvidenceUsePolicy,
        diagnosis: DiagnosisFunction,
        repair_run_spec: ArtifactReference | None = None,
        preregistered_task_snapshots: tuple[TaskSnapshotRef, ...] | None = None,
        executor: HarborCommandExecutor | None = None,
        authority_ledger: AuthorityLedger | None = None,
    ) -> None:
        self.request = RepairLoopRequest.model_validate(request.model_dump(mode="python"))
        self.parent = RepairCandidate.model_validate(parent.model_dump(mode="python"))
        if self.parent.candidate_id != self.request.parent_candidate_id:
            raise ValueError("configured repair parent does not match the loop request")
        if self.parent.harness_request.kernel_ref != registry.manifest.ref:
            raise ValueError("configured repair parent does not target the installed fixed kernel")
        self.registry = registry
        self.workflow = workflow
        self.tasks_root = Path(workflow.tasks_root)
        self.artifacts_root = Path(artifacts_root)
        self.policy_id = str(policy_id)
        if not self.policy_id.strip():
            raise ValueError("repair runtime policy id must be non-blank")
        self.harness_generator_sha256 = validate_sha256(harness_generator_sha256)
        self.program_generator_sha256 = validate_sha256(program_generator_sha256)
        self.verifier_policy = RepairVerifierPolicy.model_validate(verifier_policy.model_dump(mode="python"))
        self.evidence_use_policy = RepairEvidenceUsePolicy.model_validate(evidence_use_policy.model_dump(mode="python"))
        self.repair_run_spec = (
            ArtifactReference.model_validate(repair_run_spec.model_dump(mode="python"))
            if repair_run_spec is not None
            else None
        )
        if self.repair_run_spec is not None:
            _verify_artifact_reference(self.repair_run_spec, label="repair run spec")
            if self.evidence_use_policy != RepairEvidenceUsePolicy.exploratory_matched_repair():
                raise ValueError(
                    "standalone repair runtime requires the exploratory matched-repair evidence-use policy"
                )
        self.preregistered_task_snapshots = (
            tuple(
                TaskSnapshotRef.model_validate(snapshot.model_dump(mode="python"))
                for snapshot in preregistered_task_snapshots
            )
            if preregistered_task_snapshots is not None
            else None
        )
        self._diagnosis = diagnosis
        self._executor = executor
        self._authority_ledger = authority_ledger
        self._compiled: dict[str, CompiledRepairCandidate] = {}
        self._runs: dict[str, _RunCapture] = {}
        self._evidence: dict[tuple[str, str], RepairRuntimeEvidence] = {}
        self._proposals: dict[tuple[str, str], RepairPatchProposal] = {}
        self.attempt_plan = self._store_model(
            RepairAttemptPlan(
                request=self.request,
                parent=self.parent,
                evidence_use_policy=self.evidence_use_policy,
                repair_run_spec=self.repair_run_spec,
            ),
            kind="repair-attempt-plan",
            filename="repair-attempt-plan.json",
            namespace="repair-attempts",
        )

    @property
    def dependencies(self) -> RepairLoopDependencies:
        """Return the real compiler/runtime/verifier dependencies for the closed loop."""
        return RepairLoopDependencies(
            generator=self._generate,
            compiler=self._compile,
            runner=self._run,
            verifier=self._verify,
            diagnoser=self._diagnose,
            harness_patcher=self._patch_harness,
            program_patcher=self._patch_program,
        )

    def execute(self) -> RepairRuntimeExecution:
        """Execute and persist one complete repair attempt."""
        result = run_repair_loop(self.request, dependencies=self.dependencies)
        evidence = self._evidence.get((result.parent_candidate_id, result.parent_verification.run_id))
        proposal = self._proposals.get((result.parent_candidate_id, result.parent_verification.run_id))
        terminal = self._store_model(
            RepairTerminalRecord(
                attempt_plan_sha256=self.attempt_plan.reference.sha256,
                evidence_use_policy=self.evidence_use_policy,
                repair_run_spec=self.repair_run_spec,
                result=result,
                diagnosis_evidence=evidence if result.diagnosis is not None else None,
                patch_proposal=proposal if result.diagnosis is not None else None,
            ),
            kind="repair-terminal",
            filename="repair-terminal.json",
            namespace="repair-terminals",
        )
        authority_event: StoredAuthorityEvent | None = None
        authority_error: str | None = None
        run_artifacts = tuple(capture.artifact for capture in self._runs.values())
        if result.status is RepairLoopStatus.ACCEPTED and self._authority_ledger is not None:
            try:
                authority_event = self._record_repair_acceptance_authority(
                    result=result,
                    terminal=terminal,
                )
            except (AuthorityLedgerError, OSError, ValueError) as error:
                authority_error = f"repair_acceptance_authority_failed: {error}"
        return RepairRuntimeExecution(
            result=result,
            attempt_plan=self.attempt_plan,
            run_artifacts=run_artifacts,
            terminal=terminal,
            authority_event=authority_event,
            authority_error=authority_error,
        )

    def run_artifact(self, run_id: str) -> StoredRepairRunArtifact:
        """Return a completed run's persisted artifact without weakening verification."""
        try:
            return self._runs[run_id].artifact
        except KeyError as error:
            raise ValueError(f"unknown repair run: {run_id}") from error

    def verified_records(self, run_id: str) -> tuple[TrialRecord, ...]:
        """Re-verify persisted run and trial bytes before returning evidence records."""
        try:
            capture = self._runs[run_id]
        except KeyError as error:
            raise ValueError(f"unknown repair run: {run_id}") from error
        return self._verified_records(capture, capture.artifact.reference.sha256)

    def apply_patch(
        self,
        proposal: RepairPatchProposal,
        *,
        parent: RepairCandidate | None = None,
        child_candidate_id: str | None = None,
        iteration: int | None = None,
    ) -> RepairCandidate:
        """Materialize one typed patch while preserving fixed-K, task, and parent lineage."""
        source = parent or self.parent
        resolved = RepairPatchProposal.model_validate(proposal.model_dump(mode="python"))
        return self._materialize_patch(
            parent=source,
            proposal=resolved,
            child_candidate_id=child_candidate_id or self.request.child_candidate_id,
            iteration=iteration or self.request.iteration,
        )

    def _generate(self, request: RepairLoopRequest) -> RepairCandidate:
        if request != self.request:
            raise ValueError("repair generator received a different loop request")
        return self.parent

    def _compile(
        self,
        candidate: RepairCandidate,
        pairing: RepairPairingSpec,
    ) -> CompiledRepairCandidate:
        self._require_pairing(pairing)
        harness = compile_harness_instance(candidate.harness_request, registry=self.registry)
        source_program = candidate.program_template.bind(harness.ref)
        program = compile_execution_program(source_program, harness=harness, registry=self.registry)
        bundle = compile_run_bundle(
            bundle_id=f"{self.request.loop_id}.{candidate.candidate_id}",
            harness=harness,
            program=program,
            registry=self.registry,
            tasks_root=self.tasks_root,
            experiment_id=f"{self.request.loop_id}.{candidate.candidate_id}",
            repetitions=pairing.repetitions,
        )
        if self.preregistered_task_snapshots is not None and bundle.task_snapshots != self.preregistered_task_snapshots:
            raise ValueError("repair spec task/task-review snapshots drifted before execution")
        compiled = CompiledRepairCandidate(
            candidate_id=candidate.candidate_id,
            parent_candidate_id=candidate.parent_candidate_id,
            iteration=candidate.iteration,
            harness=harness,
            program=program,
            bundle=bundle,
        )
        if candidate.parent_candidate_id is not None:
            parent = self._compiled.get(candidate.parent_candidate_id)
            if parent is None:
                raise ValueError("repair child cannot compile before its exact parent")
            if bundle.task_snapshots != parent.bundle.task_snapshots:
                raise ValueError("task/task-review snapshots changed within paired repair")
            if bundle.kernel_ref != parent.bundle.kernel_ref:
                raise ValueError("fixed kernel changed within paired repair")
            if bundle.harness.budget != parent.bundle.harness.budget:
                raise ValueError("harness budget changed within paired repair")
        existing = self._compiled.get(candidate.candidate_id)
        if existing is not None and existing != compiled:
            raise ValueError("candidate id was recompiled to different executable content")
        self._compiled[candidate.candidate_id] = compiled
        return compiled

    def _run(
        self,
        candidate: CompiledRepairCandidate,
        pairing: RepairPairingSpec,
    ) -> RepairRunResult:
        self._require_pairing(pairing)
        if self.repair_run_spec is not None:
            _verify_artifact_reference(self.repair_run_spec, label="repair run spec")
        _verify_artifact_reference(self.attempt_plan.reference, label="repair attempt plan")
        if self._compiled.get(candidate.candidate_id) != candidate:
            raise ValueError("runner accepts only the exact candidate compiled by this repair runtime")
        run_id = f"{self.request.attempt_id}.{candidate.candidate_id}"
        if run_id in self._runs:
            raise ValueError("repair candidate requires a fresh run")

        parent_bundle_id: str | None = None
        if candidate.parent_candidate_id is not None:
            parent = self._compiled.get(candidate.parent_candidate_id)
            if parent is None:
                raise ValueError("repair child cannot run before its exact parent")
            parent_bundle_id = parent.bundle.bundle_id

        seed_captures: list[_SeedCapture] = []
        for repetition, seed in enumerate(pairing.seeds, start=1):
            execution_bundle = compile_run_bundle(
                bundle_id=f"{candidate.bundle.bundle_id}.paired-{repetition}",
                harness=candidate.harness,
                program=candidate.program,
                registry=self.registry,
                tasks_root=self.tasks_root,
                experiment_id=candidate.bundle.harbor.experiment_id,
                repetitions=1,
            )
            self._validate_execution_bundle(candidate, execution_bundle)
            seeded_run_id = f"{run_id}.r{repetition}.s{seed}"
            execution = execute_run_bundle(
                bundle=execution_bundle,
                registry=self.registry,
                workflow=self.workflow,
                artifacts_root=self.artifacts_root,
                study=MetaHarnessStudyContext(
                    run_id=seeded_run_id,
                    policy_id=self.policy_id,
                    harness_generator_sha256=self.harness_generator_sha256,
                    program_generator_sha256=self.program_generator_sha256,
                    split=pairing.split,
                    parent_bundle_id=parent_bundle_id,
                    execution_seed=seed,
                    repair_attempt_id=self.request.attempt_id,
                    repair_iteration=self.request.iteration,
                    repair_decision=self.attempt_plan.reference,
                ),
                executor=self._executor,
                authority_ledger=self._authority_ledger,
            )
            records = self._validate_seed_records(
                execution=execution,
                bundle=execution_bundle,
                seeded_run_id=seeded_run_id,
                seed=seed,
                parent_bundle_id=parent_bundle_id,
            )
            seed_captures.append(
                _SeedCapture(
                    manifest=RepairSeedExecution(
                        repetition=repetition,
                        seed=seed,
                        run_id=seeded_run_id,
                        execution_bundle_id=execution_bundle.bundle_id,
                        program_execution=execution.program,
                        budget=execution.budget,
                        trial_records=tuple(_file_reference(path) for path, _ in records),
                        harbor_invocation_receipts=tuple(
                            invocation.receipt.reference for invocation in execution.harbor_invocations
                        ),
                    ),
                    bundle=execution_bundle,
                    execution=execution,
                )
            )

        manifest = RepairRunArtifactManifest(
            attempt_id=self.request.attempt_id,
            iteration=self.request.iteration,
            run_id=run_id,
            candidate_id=candidate.candidate_id,
            parent_candidate_id=candidate.parent_candidate_id,
            kernel_ref=candidate.harness.kernel_ref,
            harness_ref=candidate.harness.ref,
            program_ref=candidate.program.ref,
            bundle_id=candidate.bundle.bundle_id,
            attempt_plan=self.attempt_plan.reference,
            pairing=pairing,
            executions=tuple(item.manifest for item in seed_captures),
        )
        stored = self._store_run_manifest(manifest)
        self._runs[run_id] = _RunCapture(
            compiled=candidate,
            manifest=manifest,
            artifact=stored,
            seeds=tuple(seed_captures),
        )
        return RepairRunResult(
            run_id=run_id,
            candidate_id=candidate.candidate_id,
            pairing=pairing,
            artifact_sha256=stored.reference.sha256,
        )

    def _verify(
        self,
        candidate: CompiledRepairCandidate,
        run: RepairRunResult,
    ) -> VerifiedRepairRun:
        capture = self._runs.get(run.run_id)
        if capture is None or capture.compiled != candidate:
            raise ValueError("verifier received an unknown or mismatched repair run")
        records = self._verified_records(capture, run.artifact_sha256)
        trial_evidence, observations, diagnostics = self._interpret_records(
            candidate=candidate,
            run=run,
            capture=capture,
            records=records,
        )
        program_executions = tuple(_repair_program_evidence(item) for item in capture.seeds)
        execution_observations = tuple(_repair_execution_observation(item) for item in capture.seeds)
        program_diagnostics: set[str] = set()
        for item in program_executions:
            if item.status is ProgramExecutionStatus.FAILED:
                program_diagnostics.add("program_execution_failed")
            elif item.status is ProgramExecutionStatus.STOPPED:
                program_diagnostics.add("program_execution_stopped")
            if item.error_code is not None:
                program_diagnostics.add(f"program_failure:{item.error_code}")
        diagnostics = tuple(sorted({*diagnostics, *program_diagnostics}))
        reward_coverage = _reward_coverage(run.pairing, observations)
        blocking_diagnostics = tuple(code for code in diagnostics if code not in _ACCEPTANCE_ONLY_DIAGNOSTIC_CODES)
        passed = reward_coverage is RepairRewardCoverage.COMPLETE and not blocking_diagnostics
        evidence = RepairRuntimeEvidence(
            candidate_id=candidate.candidate_id,
            run_id=run.run_id,
            kernel_ref=candidate.harness.kernel_ref,
            harness_ref=candidate.harness.ref,
            program_ref=candidate.program.ref,
            bundle_id=candidate.bundle.bundle_id,
            run_artifact_sha256=run.artifact_sha256,
            pairing=run.pairing,
            trials=trial_evidence,
            program_executions=program_executions,
            monolithic_run_batch=_monolithic_run_batch_evidence(
                candidate.program.nodes,
                task_refs=run.pairing.task_ids,
            ),
            declared_stage_graphs=_declared_stage_graph_evidence(candidate.bundle),
            program_limits=candidate.program.limits,
            verifier_minimum_reward=self.verifier_policy.minimum_reward,
            diagnostic_codes=diagnostics,
        )
        self._evidence[(candidate.candidate_id, run.run_id)] = evidence
        return VerifiedRepairRun(
            verification_id=f"verification.{run.artifact_sha256[:20]}",
            run_id=run.run_id,
            candidate_id=candidate.candidate_id,
            harness_ref=candidate.harness.ref,
            program_ref=candidate.program.ref,
            run_artifact_sha256=run.artifact_sha256,
            pairing=run.pairing,
            passed=passed,
            reward_coverage=reward_coverage,
            observations=observations,
            execution_observations=execution_observations,
            diagnostics=diagnostics,
        )

    def _diagnose(
        self,
        candidate: CompiledRepairCandidate,
        verification: VerifiedRepairRun,
    ) -> RepairDiagnosis:
        key = (candidate.candidate_id, verification.run_id)
        evidence = self._evidence.get(key)
        if evidence is None:
            raise ValueError("diagnosis requires freshly verified runtime evidence")
        if verification.passed or not evidence.diagnostic_codes:
            raise ValueError("passing verifier evidence cannot be repaired")
        raw_proposal = self._diagnosis(evidence)
        if isinstance(raw_proposal, RepairNoPatchProposal):
            no_patch = RepairNoPatchProposal.model_validate(raw_proposal.model_dump(mode="python"))
            if not set(no_patch.evidence_codes).issubset(evidence.diagnostic_codes):
                raise ValueError("no-patch diagnosis cites evidence absent from the verified parent run")
            return RepairDiagnosis(
                candidate_id=candidate.candidate_id,
                run_id=verification.run_id,
                failure_domain=no_patch.failure_domain,
                owner=None,
                code=no_patch.code,
                message=no_patch.message,
                evidence_codes=no_patch.evidence_codes,
            )
        patch_proposal = RepairPatchProposal.model_validate(raw_proposal)
        self._proposals[key] = patch_proposal
        return RepairDiagnosis(
            candidate_id=candidate.candidate_id,
            run_id=verification.run_id,
            failure_domain=RepairFailureDomain(patch_proposal.owner.value),
            owner=patch_proposal.owner,
            code=patch_proposal.code,
            message=patch_proposal.message,
            evidence_codes=evidence.diagnostic_codes,
        )

    def _patch_harness(self, request: RepairPatchRequest) -> RepairCandidate:
        return self._patch(request, expected_owner=RepairOwner.HARNESS)

    def _patch_program(self, request: RepairPatchRequest) -> RepairCandidate:
        return self._patch(request, expected_owner=RepairOwner.PROGRAM)

    def _patch(
        self,
        request: RepairPatchRequest,
        *,
        expected_owner: RepairOwner,
    ) -> RepairCandidate:
        key = (request.parent.candidate_id, request.diagnosis.run_id)
        proposal = self._proposals.get(key)
        if proposal is None:
            raise ValueError("patch requires a typed proposal derived from the verified parent run")
        if proposal.owner is not expected_owner or request.diagnosis.owner is not expected_owner:
            raise ValueError("patcher cannot mutate a surface it does not own")
        return self._materialize_patch(
            parent=request.parent,
            proposal=proposal,
            child_candidate_id=request.child_candidate_id,
            iteration=request.iteration,
        )

    def _materialize_patch(
        self,
        *,
        parent: RepairCandidate,
        proposal: RepairPatchProposal,
        child_candidate_id: str,
        iteration: int,
    ) -> RepairCandidate:
        patched = _REPAIR_RULE_REGISTRY.apply(
            _RepairPatchContext(
                parent=parent,
                compiled_parent=self._compiled.get(parent.candidate_id),
                iteration=iteration,
            ),
            proposal.patch,
        )
        return RepairCandidate(
            candidate_id=child_candidate_id,
            parent_candidate_id=parent.candidate_id,
            iteration=iteration,
            harness_request=patched.harness_request,
            program_template=patched.program_template,
        )

    def _validate_execution_bundle(
        self,
        candidate: CompiledRepairCandidate,
        execution_bundle: RunBundle,
    ) -> None:
        if (
            execution_bundle.kernel_ref != candidate.bundle.kernel_ref
            or execution_bundle.harness != candidate.harness
            or execution_bundle.program != candidate.program
            or execution_bundle.task_snapshots != candidate.bundle.task_snapshots
            or execution_bundle.harbor.task_refs != candidate.bundle.harbor.task_refs
            or execution_bundle.harbor.agent_binding_id != candidate.bundle.harbor.agent_binding_id
            or execution_bundle.harbor.compute_binding_id != candidate.bundle.harbor.compute_binding_id
            or execution_bundle.harbor.verification_binding_id != candidate.bundle.harbor.verification_binding_id
            or execution_bundle.harbor.result_import_binding_id != candidate.bundle.harbor.result_import_binding_id
            or execution_bundle.harbor.repetitions != 1
        ):
            raise ValueError("seed execution bundle drifted from the compiled paired candidate")

    def _validate_seed_records(
        self,
        *,
        execution: RunBundleExecution,
        bundle: RunBundle,
        seeded_run_id: str,
        seed: int,
        parent_bundle_id: str | None,
    ) -> tuple[tuple[Path, TrialRecord], ...]:
        paths = tuple(path for invocation in execution.harbor_invocations for path in invocation.imported_trial_paths)
        if len(paths) != len(set(paths)):
            raise ValueError("repair seed execution requires unique imported TrialRecords")
        loaded = tuple((path, read_trial_record(path)) for path in paths)
        task_ids = tuple(record.task.task_id for _, record in loaded)
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("repair seed execution requires at most one TrialRecord per task")
        if not set(task_ids).issubset(bundle.harbor.task_refs):
            raise ValueError("repair seed TrialRecords must belong to the exact paired tasks")
        if execution.program.status is ProgramExecutionStatus.SUCCEEDED and (
            len(loaded) != len(bundle.harbor.task_refs) or set(task_ids) != set(bundle.harbor.task_refs)
        ):
            raise ValueError("successful repair seed execution must cover the exact paired tasks")
        for _, record in loaded:
            provenance = record.meta_harness_provenance
            if provenance is None:
                raise ValueError("repair evidence requires meta-harness TrialRecord provenance")
            if (
                provenance.run_id != seeded_run_id
                or provenance.policy_id != self.policy_id
                or provenance.kernel_sha256 != canonical_json_sha256(bundle.kernel_ref.model_dump(mode="json"))
                or provenance.harness_sha256 != canonical_json_sha256(bundle.harness.model_dump(mode="json"))
                or provenance.program_sha256 != canonical_json_sha256(bundle.program.model_dump(mode="json"))
                or provenance.bundle_sha256 != canonical_json_sha256(bundle.model_dump(mode="json"))
                or provenance.split != self.request.pairing.split
                or provenance.execution_seed != seed
                or provenance.parent_bundle_id != parent_bundle_id
                or provenance.repair_attempt_id != self.request.attempt_id
                or provenance.repair_iteration != self.request.iteration
                or provenance.repair_decision != self.attempt_plan.reference
            ):
                raise ValueError("repair TrialRecord lineage does not match the exact seeded execution")
            snapshot = _snapshot(bundle, record.task.task_id)
            expected_world = (
                snapshot.task_review.review_sidecar_sha256
                if snapshot.task_review is not None
                else snapshot.package_sha256
            )
            if provenance.review_sidecar_sha256 != expected_world:
                raise ValueError("repair TrialRecord review lineage does not match its task snapshot")
            _verify_artifact_reference(
                provenance.candidate_manifest,
                label="candidate manifest",
            )
            assert provenance.repair_decision is not None
            _verify_artifact_reference(
                provenance.repair_decision,
                label="repair attempt plan",
            )
        return loaded

    def _verified_records(
        self,
        capture: _RunCapture,
        expected_artifact_sha256: str,
    ) -> tuple[TrialRecord, ...]:
        self._validate_persisted_run_artifact(
            capture,
            expected_artifact_sha256=expected_artifact_sha256,
        )
        records: list[TrialRecord] = []
        for seed_capture in capture.seeds:
            records.extend(self._verified_seed_records(capture, seed_capture))
        return tuple(records)

    def _validate_persisted_run_artifact(
        self,
        capture: _RunCapture,
        *,
        expected_artifact_sha256: str,
    ) -> None:
        encoded = capture.artifact.path.read_bytes()
        _verify_artifact_reference(self.attempt_plan.reference, label="repair attempt plan")
        actual_sha256 = hashlib.sha256(encoded).hexdigest()
        if actual_sha256 != expected_artifact_sha256 or actual_sha256 != capture.artifact.reference.sha256:
            raise ValueError("repair run artifact hash mismatch")
        loaded_manifest = RepairRunArtifactManifest.model_validate_json(encoded)
        if loaded_manifest != capture.manifest:
            raise ValueError("repair run artifact content does not match the executed run")

    def _verified_seed_records(
        self,
        capture: _RunCapture,
        seed_capture: _SeedCapture,
    ) -> tuple[TrialRecord, ...]:
        manifest = seed_capture.manifest
        self._validate_seed_capture_manifest(seed_capture)
        receipts = self._verified_harbor_invocation_receipts(manifest)
        by_path = self._validate_seed_receipt_bindings(
            seed_capture,
            receipts=receipts,
        )
        loaded = self._validate_seed_records(
            execution=seed_capture.execution,
            bundle=seed_capture.bundle,
            seeded_run_id=manifest.run_id,
            seed=manifest.seed,
            parent_bundle_id=self._parent_bundle_id(capture),
        )
        return self._verified_trial_record_bytes(loaded, by_path=by_path)

    @staticmethod
    def _validate_seed_capture_manifest(seed_capture: _SeedCapture) -> None:
        manifest = seed_capture.manifest
        if manifest.execution_bundle_id != seed_capture.bundle.bundle_id:
            raise ValueError("repair run artifact does not bind the exact seed execution bundle")
        if manifest.program_execution != seed_capture.execution.program:
            raise ValueError("repair run artifact does not bind the exact seed program execution")
        if manifest.budget != seed_capture.execution.budget:
            raise ValueError("repair run artifact does not bind the exact seed budget observation")

    @staticmethod
    def _validate_seed_receipt_bindings(
        seed_capture: _SeedCapture,
        *,
        receipts: tuple[HarborInvocationReceipt, ...],
    ) -> dict[str, ArtifactReference]:
        manifest = seed_capture.manifest
        runtime_receipts = tuple(
            invocation.receipt.reference for invocation in seed_capture.execution.harbor_invocations
        )
        if tuple(_artifact_identity(item) for item in manifest.harbor_invocation_receipts) != tuple(
            _artifact_identity(item) for item in runtime_receipts
        ):
            raise ValueError("repair run artifact does not bind the executed Harbor invocation receipts")
        by_path = {reference.path: reference for reference in manifest.trial_records}
        trial_paths = tuple(
            path for invocation in seed_capture.execution.harbor_invocations for path in invocation.imported_trial_paths
        )
        if set(map(str, trial_paths)) != set(by_path):
            raise ValueError("repair run artifact does not bind the executed TrialRecord paths")
        receipt_trials = tuple(reference for receipt in receipts for reference in receipt.imported_trial_records)
        if {_artifact_identity(reference) for reference in receipt_trials} != {
            _artifact_identity(reference) for reference in manifest.trial_records
        }:
            raise ValueError("Harbor invocation receipts do not bind the manifested TrialRecords")
        return by_path

    def _parent_bundle_id(self, capture: _RunCapture) -> str | None:
        parent_candidate_id = capture.compiled.parent_candidate_id
        if parent_candidate_id is None:
            return None
        parent = self._compiled.get(parent_candidate_id)
        if parent is None:
            raise ValueError("repair child lost its compiled parent lineage")
        return parent.bundle.bundle_id

    @staticmethod
    def _verified_trial_record_bytes(
        loaded: tuple[tuple[Path, TrialRecord], ...],
        *,
        by_path: dict[str, ArtifactReference],
    ) -> tuple[TrialRecord, ...]:
        records: list[TrialRecord] = []
        for path, record in loaded:
            reference = by_path[str(path)]
            if hashlib.sha256(path.read_bytes()).hexdigest() != reference.sha256:
                raise ValueError("repair TrialRecord artifact hash mismatch")
            records.append(record)
        return tuple(records)

    def _verified_harbor_invocation_receipts(
        self,
        execution: RepairSeedExecution,
    ) -> tuple[HarborInvocationReceipt, ...]:
        receipts: list[HarborInvocationReceipt] = []
        for reference in execution.harbor_invocation_receipts:
            _verify_artifact_reference(reference, label="Harbor invocation receipt")
            receipt = load_harbor_invocation_receipt(Path(reference.path))
            if receipt.bundle_id != execution.execution_bundle_id:
                raise ValueError("Harbor invocation receipt does not bind the seed execution bundle")
            if receipt.run_id != execution.run_id:
                raise ValueError("Harbor invocation receipt does not bind the seeded repair run")
            receipts.append(receipt)

        expected_coordinates = sorted(
            (
                attempt.node_id,
                attempt.attempt_index,
                attempt.fanout_index,
            )
            for node in execution.program_execution.node_evidence
            for attempt in node.attempts
            if attempt.operation_ref.operation_id in {"run_batch.v1", "finalize_task.v1"}
            and attempt.status is OperationExecutionStatus.SUCCEEDED
        )
        observed_coordinates = sorted(
            (
                receipt.program_node_id,
                receipt.attempt,
                receipt.fanout_index,
            )
            for receipt in receipts
        )
        if observed_coordinates != expected_coordinates:
            raise ValueError("Harbor invocation receipts do not match successful scored px attempts")
        return tuple(receipts)

    def _interpret_records(
        self,
        *,
        candidate: CompiledRepairCandidate,
        run: RepairRunResult,
        capture: _RunCapture,
        records: tuple[TrialRecord, ...],
    ) -> tuple[
        tuple[RepairTrialEvidence, ...],
        tuple[RepairRunObservation, ...],
        tuple[str, ...],
    ]:
        return _interpret_imported_records(
            candidate=candidate,
            run=run,
            capture=capture,
            records=records,
            repo_root=self.workflow.repo_root,
            tasks_root=self.tasks_root,
            verifier_policy=self.verifier_policy,
        )

    def _require_pairing(self, pairing: RepairPairingSpec) -> None:
        if pairing != self.request.pairing:
            raise ValueError("repair runtime pairing changed after initialization")

    def _record_repair_acceptance_authority(
        self,
        *,
        result: RepairLoopResult,
        terminal: StoredRepairArtifact,
    ) -> StoredAuthorityEvent:
        """Grant accepted repair authority from exact already-persisted runtime evidence."""
        if self._authority_ledger is None:
            raise ValueError("repair acceptance authority requires an authority ledger")
        if result.status is not RepairLoopStatus.ACCEPTED:
            raise ValueError("repair acceptance authority requires an accepted terminal result")

        host_runtime = AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        )
        plan_basis = self._observe_repair_artifact(
            artifact_id=f"repair-attempt-plan.{result.loop_id}.{result.attempt_id}",
            artifact=self.attempt_plan,
            producer=host_runtime,
            operation_id="repair-plan-persistence",
            parent_origin_sha256s=(),
        )
        run_bases: list[StoredBasis] = []
        for capture in self._runs.values():
            invocations = tuple(
                invocation for seed in capture.seeds for invocation in seed.execution.harbor_invocations
            )
            if not invocations:
                raise ValueError("accepted repair run has no scored Harbor invocation")
            receipt_origins: list[str] = []
            for invocation in invocations:
                if invocation.governance is None:
                    raise ValueError("accepted repair run lacks scored-import authority")
                receipt_origins.append(invocation.governance.receipt_basis.origin.content_sha256)
            run_bases.append(
                self._observe_repair_artifact(
                    artifact_id=f"repair-run.{capture.artifact.run_id}",
                    artifact=capture.artifact,
                    producer=host_runtime,
                    operation_id="repair-run-persistence",
                    parent_origin_sha256s=tuple(sorted(set(receipt_origins))),
                )
            )
        terminal_basis = self._observe_repair_artifact(
            artifact_id=f"repair-terminal.{result.loop_id}.{result.attempt_id}",
            artifact=terminal,
            producer=host_runtime,
            operation_id="repair-terminal-persistence",
            parent_origin_sha256s=(
                plan_basis.origin.content_sha256,
                *(item.origin.content_sha256 for item in run_bases),
            ),
        )
        event = AuthorityEvent(
            event_id=f"authority.repair-acceptance.{result.loop_id}.{result.attempt_id}",
            principal=AuthorityPrincipal(
                principal_id="host.repair-policy",
                kind=AuthorityPrincipalKind.HOST_POLICY,
            ),
            action=AuthorityAction.REPAIR_ACCEPTANCE,
            decision=AuthorityDecision.GRANTED,
            subject_id=f"repair-terminal.{result.loop_id}.{result.attempt_id}",
            subject_sha256=terminal.reference.sha256,
            basis=(
                plan_basis.reference,
                *(item.reference for item in run_bases),
                terminal_basis.reference,
            ),
            kernel_ref=self.registry.manifest.ref,
            reasons=("accepted paired repair and terminal evidence persisted",),
            revalidation_triggers=(
                "basis_replay_due",
                "critic_change",
                "kernel_version_change",
            ),
        )
        return self._authority_ledger.issue_authority_event(event)

    def _observe_repair_artifact(
        self,
        *,
        artifact_id: str,
        artifact: StoredRepairArtifact | StoredRepairRunArtifact,
        producer: AuthorityPrincipal,
        operation_id: str,
        parent_origin_sha256s: tuple[str, ...],
    ) -> StoredBasis:
        """Copy one exact repair artifact into the host-owned authority store."""
        assert self._authority_ledger is not None
        if artifact.path != Path(artifact.reference.path):
            raise ValueError("repair artifact wrapper and reference paths differ")
        _verify_artifact_reference(
            artifact.reference,
            label=artifact.reference.kind,
        )
        return self._authority_ledger.observe_basis(
            kind=BasisKind.EVIDENCE,
            artifact_id=artifact_id,
            content=artifact.path.read_bytes(),
            producer=producer,
            producer_process_id="aecbench.repair-runtime",
            observed_by=producer,
            channel="repair-runtime",
            operation_id=operation_id,
            invocation_id=self.request.attempt_id,
            parent_origin_sha256s=parent_origin_sha256s,
            operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
        )

    def _store_model(
        self,
        model: FrozenStrictModel,
        *,
        kind: str,
        filename: str,
        namespace: str,
    ) -> StoredRepairArtifact:
        encoded = (json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode()
        sha256 = hashlib.sha256(encoded).hexdigest()
        path = self.artifacts_root / namespace / sha256 / filename
        _write_content_addressed(path, encoded)
        return StoredRepairArtifact(
            path=path,
            reference=ArtifactReference(
                kind=kind,
                path=str(path),
                sha256=sha256,
                media_type="application/json",
            ),
        )

    def _store_run_manifest(
        self,
        manifest: RepairRunArtifactManifest,
    ) -> StoredRepairRunArtifact:
        stored = self._store_model(
            manifest,
            kind="repair-run",
            filename="repair-run.json",
            namespace="repair-runs",
        )
        return StoredRepairRunArtifact(
            run_id=manifest.run_id,
            candidate_id=manifest.candidate_id,
            path=stored.path,
            reference=stored.reference,
        )
