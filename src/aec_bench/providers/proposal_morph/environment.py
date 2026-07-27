# ABOUTME: Owns the Morph proposal environment state machine and Harbor I/O boundary.
# ABOUTME: Serializes candidate, verifier, broken, and closed transitions under one lock.

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable
from functools import partial
from pathlib import Path, PurePosixPath
from typing import Any

from harbor.environments.base import BaseEnvironment, ExecResult  # type: ignore[import-untyped]
from harbor.models.environment_type import EnvironmentType  # type: ignore[import-untyped]
from harbor.models.task.config import EnvironmentConfig  # type: ignore[import-untyped]
from harbor.models.trial.paths import TrialPaths  # type: ignore[import-untyped]

from aec_bench.contracts.harness_kernel import validate_sha256
from aec_bench.harness.proposal_environment_pool import (
    IsolatedProposalEnvironmentIdentity,
    IsolatedProposalEnvironmentPool,
)
from aec_bench.harness.runtime_dependencies import RUNTIME_PYTHON_PACKAGES
from aec_bench.providers.morph_cloud import extract_archive, morph_object_id

from .async_ops import (
    run_boundary_transition as _run_boundary_transition,
)
from .async_ops import (
    run_transition_call as _run_transition_call,
)
from .boundary import (
    BoundaryPhase as _BoundaryPhase,
)
from .boundary import (
    HandoffVariant as _HandoffVariant,
)
from .boundary import (
    ProposalCandidateInvocationTransition,
    ProposalMorphBoundaryError,
)
from .boundary import (
    ProposalMorphState as _ProposalMorphState,
)
from .boundary import (
    SealedArtifact as _SealedArtifact,
)
from .boundary import (
    TestsSnapshot as _TestsSnapshot,
)
from .cleanup import (
    teardown_with_cleanup_receipt_errors,
)
from .confinement import (
    is_candidate_upload_path as _is_candidate_upload_path,
)
from .confinement import (
    is_handoff_path as _is_handoff_path,
)
from .confinement import (
    read_regular_file as _read_regular_file,
)
from .confinement import (
    validated_remote_path as _validated_remote_path,
)
from .confinement import (
    write_receipt as _write_receipt,
)
from .constants import (
    INVOCATION_ID_PATTERN as _INVOCATION_ID,
)
from .constants import (
    OUTPUT_PATH as _OUTPUT_PATH,
)
from .constants import (
    PROPOSAL_HANDOFF_MAX_TOTAL_BYTES as _HANDOFF_MAX_TOTAL_BYTES,
)
from .constants import (
    PROPOSAL_SESSION_ROOT as _PROPOSAL_SESSION_ROOT,
)
from .constants import (
    REMOTE_LOGS_DIR,
    REMOTE_TESTS_DIR,
    REMOTE_WORKSPACE_DIR,
)
from .evidence import (
    read_sealed_artifact as _read_sealed_artifact,
)
from .evidence import (
    seal_artifacts as _seal_artifacts,
)
from .evidence import (
    snapshot_tests as _snapshot_tests,
)
from .evidence import (
    tests_content_sha256 as _tests_content_sha256,
)
from .evidence import (
    verify_tests_snapshot as _verify_tests_snapshot,
)
from .operations import ProposalMorphHarborOperations, default_proposal_morph_operations
from .provisioning import provision_environment


class ProposalMorphHarborEnvironment(BaseEnvironment):  # type: ignore[misc]
    """Harbor environment with a hard candidate-to-verifier transition."""

    def __init__(
        self,
        environment_dir: Path,
        environment_name: str,
        session_id: str,
        trial_paths: TrialPaths,
        task_env_config: EnvironmentConfig,
        *,
        compute_backend: str = "morph",
        operations: ProposalMorphHarborOperations | None = None,
        isolated_operations_factory: (Callable[[int], ProposalMorphHarborOperations] | None) = None,
        runtime_archive_path: Path | str,
        runtime_archive_sha256: str,
        runtime_archive_content_sha256: str,
        runtime_packages: tuple[str, ...] = RUNTIME_PYTHON_PACKAGES,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            environment_dir=environment_dir,
            environment_name=environment_name,
            session_id=session_id,
            trial_paths=trial_paths,
            task_env_config=task_env_config,
            **kwargs,
        )
        validate_sha256(runtime_archive_sha256)
        validate_sha256(runtime_archive_content_sha256)
        if tuple(runtime_packages) != RUNTIME_PYTHON_PACKAGES:
            raise ProposalMorphBoundaryError("proposal runtime packages must match the governed runtime lock")
        archive_path = Path(runtime_archive_path)
        archive_bytes = _read_regular_file(
            archive_path,
            label="proposal runtime archive",
            max_bytes=64 * 1024 * 1024,
        )
        if hashlib.sha256(archive_bytes).hexdigest() != runtime_archive_sha256:
            raise ProposalMorphBoundaryError("proposal runtime archive SHA-256 changed before environment construction")

        self.compute_backend = compute_backend
        self._uses_default_operations = operations is None
        self._operations = operations or default_proposal_morph_operations(
            cpus=task_env_config.cpus,
            memory_mb=task_env_config.memory_mb,
            storage_mb=task_env_config.storage_mb,
        )
        if isolated_operations_factory is not None and not callable(isolated_operations_factory):
            raise ProposalMorphBoundaryError(
                "proposal isolated operations factory must be callable",
            )
        self._isolated_operations_factory = isolated_operations_factory
        self._runtime_archive_path = archive_path
        self.runtime_archive_sha256 = runtime_archive_sha256
        self.runtime_archive_content_sha256 = runtime_archive_content_sha256
        self._runtime_packages = runtime_packages
        self._state: _ProposalMorphState | None = None
        self._phase = _BoundaryPhase.NEW
        self._tests_snapshot: _TestsSnapshot | None = None
        self._sealed_artifacts: dict[str, _SealedArtifact] = {}
        self._io_lock = asyncio.Lock()

        self.boundary_dir = self.trial_paths.trial_dir / "proposal-morph-boundary"
        self.seal_dir = self.boundary_dir / "sealed-artifacts"
        self.seal_manifest_path = self.boundary_dir / "seal-manifest.json"
        self.rotation_receipt_path = self.boundary_dir / "verifier-rotation.json"
        self.cleanup_receipt_path = self.boundary_dir / "proposal-cleanup.json"
        self.invocation_receipts_dir = self.boundary_dir / "candidate-transitions"

    @staticmethod
    def type() -> EnvironmentType:
        return EnvironmentType.DOCKER

    @property
    def is_mounted(self) -> bool:
        return False

    @property
    def supports_gpus(self) -> bool:
        return False

    @property
    def can_disable_internet(self) -> bool:
        return False

    @property
    def _environment_definition_path(self) -> Path:
        return Path(self.environment_dir) / "Dockerfile"

    def _validate_definition(self) -> None:
        _read_regular_file(
            self._environment_definition_path,
            label="proposal Morph Dockerfile",
            max_bytes=1024 * 1024,
        )

    async def start(self, force_build: bool) -> None:
        async with self._io_lock:
            await self._start(force_build=force_build)

    async def _start(self, force_build: bool) -> None:
        del force_build
        if self._phase is not _BoundaryPhase.NEW:
            raise ProposalMorphBoundaryError("proposal Morph environment can only be started once")
        try:
            self.boundary_dir.mkdir(parents=False, exist_ok=False)
        except FileExistsError as error:
            raise ProposalMorphBoundaryError("proposal Morph boundary directory already exists") from error
        self.invocation_receipts_dir.mkdir()
        try:
            state = await provision_environment(
                operations=self._operations,
                dockerfile_path=self._environment_definition_path,
                context_dir=Path(self.environment_dir),
                runtime_archive_path=self._runtime_archive_path,
                runtime_archive_sha256=self.runtime_archive_sha256,
                runtime_archive_content_sha256=self.runtime_archive_content_sha256,
                runtime_packages=self._runtime_packages,
            )
        except BaseException:
            self._state = None
            self._phase = _BoundaryPhase.BROKEN
            raise
        self._state = state
        self._phase = _BoundaryPhase.CANDIDATE

    async def stop(self, delete: bool) -> None:
        async with self._io_lock:
            state = self._state
            boundary_phase = self._phase
            self._state = None
            self._phase = _BoundaryPhase.CLOSED
            if state is None:
                return
            teardown = asyncio.create_task(
                teardown_with_cleanup_receipt_errors(
                    operations=self._operations,
                    cleanup_receipt_path=self.cleanup_receipt_path,
                    rotation_receipt_path=self.rotation_receipt_path,
                    runtime_archive_sha256=self.runtime_archive_sha256,
                    runtime_archive_content_sha256=self.runtime_archive_content_sha256,
                    snapshot=state.snapshot,
                    instance=state.instance,
                    expected_container_identity=state.container_identity,
                    boundary_phase=boundary_phase,
                    delete=delete,
                )
            )
            try:
                errors = await asyncio.shield(teardown)
            except asyncio.CancelledError as cancellation:
                failures: list[Exception] = []
                try:
                    failures.extend(await teardown)
                except Exception as error:
                    failures.append(error)
                if failures:
                    raise BaseExceptionGroup(
                        "proposal Morph Harbor teardown was cancelled and cleanup failed",
                        [cancellation, *failures],
                    ) from cancellation
                raise
            if errors:
                raise ExceptionGroup("proposal Morph Harbor teardown failed", errors)

    async def reset_candidate_container_for_invocation(
        self,
        *,
        invocation_id: str,
        expected_runtime_digest: str,
    ) -> ProposalCandidateInvocationTransition:
        """Replace the candidate container before a subsequent model invocation."""

        async with self._io_lock:
            return await _run_boundary_transition(
                lambda: self._reset_candidate_container_for_invocation(
                    invocation_id=invocation_id,
                    expected_runtime_digest=expected_runtime_digest,
                )
            )

    def isolated_environment_identity(
        self,
    ) -> IsolatedProposalEnvironmentIdentity:
        """Return provider identities used to prove one pool slot is independent."""

        state = self._require_phase(_BoundaryPhase.CANDIDATE)
        return IsolatedProposalEnvironmentIdentity(
            environment_session_id=self.session_id,
            runtime_snapshot_identity=morph_object_id(state.snapshot),
            trial_instance_identity=morph_object_id(state.instance),
            candidate_container_identity=state.container_identity,
            runtime_archive_sha256=self.runtime_archive_sha256,
            runtime_archive_content_sha256=self.runtime_archive_content_sha256,
        )

    def create_isolated_environment_pool(
        self,
        *,
        capacity: int,
        receipt_root: Path | str,
        expected_runtime_archive_sha256: str,
        expected_runtime_archive_content_sha256: str,
    ) -> IsolatedProposalEnvironmentPool:
        """Create a bounded pool backed by independent Morph snapshots and instances."""

        self._require_phase(_BoundaryPhase.CANDIDATE)
        validate_sha256(expected_runtime_archive_sha256)
        validate_sha256(expected_runtime_archive_content_sha256)
        if (
            expected_runtime_archive_sha256 != self.runtime_archive_sha256
            or expected_runtime_archive_content_sha256 != self.runtime_archive_content_sha256
        ):
            raise ProposalMorphBoundaryError(
                "proposal environment pool runtime archive binding differs from the outer Harbor environment",
            )
        if not self._uses_default_operations and self._isolated_operations_factory is None:
            raise ProposalMorphBoundaryError(
                "custom proposal Morph operations require an isolated operations factory before ready-set execution",
            )

        child_trial_root = self.trial_paths.trial_dir / "proposal-ready-set-environments"

        def environment_factory(slot: int) -> ProposalMorphHarborEnvironment:
            trial_dir = child_trial_root / f"slot-{slot:03d}"
            if trial_dir.exists() or trial_dir.is_symlink():
                raise ProposalMorphBoundaryError(
                    f"proposal pool trial directory already exists: {trial_dir}",
                )
            trial_paths = TrialPaths(trial_dir)
            trial_paths.mkdir()
            return ProposalMorphHarborEnvironment(
                environment_dir=Path(self.environment_dir),
                environment_name=(f"{self.environment_name}.ready-set.slot-{slot:03d}"),
                session_id=f"{self.session_id}.ready-set.slot-{slot:03d}",
                trial_paths=trial_paths,
                task_env_config=self.task_env_config.model_copy(deep=True),
                logger=self.logger,
                compute_backend=self.compute_backend,
                operations=self._isolated_operations(slot),
                runtime_archive_path=self._runtime_archive_path,
                runtime_archive_sha256=self.runtime_archive_sha256,
                runtime_archive_content_sha256=(self.runtime_archive_content_sha256),
                runtime_packages=self._runtime_packages,
            )

        return IsolatedProposalEnvironmentPool(
            capacity=capacity,
            receipt_root=receipt_root,
            expected_runtime_archive_sha256=(expected_runtime_archive_sha256),
            expected_runtime_archive_content_sha256=(expected_runtime_archive_content_sha256),
            environment_factory=environment_factory,
        )

    def _isolated_operations(
        self,
        slot: int,
    ) -> ProposalMorphHarborOperations:
        if self._isolated_operations_factory is not None:
            operations = self._isolated_operations_factory(slot)
            if operations is self._operations:
                raise ProposalMorphBoundaryError(
                    "proposal environment pool cannot share outer provider operations",
                )
            return operations
        return default_proposal_morph_operations(
            cpus=self.task_env_config.cpus,
            memory_mb=self.task_env_config.memory_mb,
            storage_mb=self.task_env_config.storage_mb,
        )

    async def _reset_candidate_container_for_invocation(
        self,
        *,
        invocation_id: str,
        expected_runtime_digest: str,
    ) -> ProposalCandidateInvocationTransition:
        state = self._require_phase(_BoundaryPhase.CANDIDATE)
        if not _INVOCATION_ID.fullmatch(invocation_id):
            raise ProposalMorphBoundaryError("candidate invocation ID is invalid")
        validate_sha256(expected_runtime_digest)
        if expected_runtime_digest != self.runtime_archive_sha256:
            raise ProposalMorphBoundaryError("candidate reset runtime digest does not match the pinned runtime archive")
        receipt_path = self.invocation_receipts_dir / f"{invocation_id}.json"
        if receipt_path.exists() or receipt_path.is_symlink():
            raise ProposalMorphBoundaryError(f"candidate invocation {invocation_id!r} already has a reset receipt")

        previous_identity = state.container_identity
        receipt: dict[str, object] = {
            "schema_version": "aecbench.proposal-candidate-transition.v1",
            "status": "started",
            "invocation_id": invocation_id,
            "runtime_archive_sha256": self.runtime_archive_sha256,
            "previous_container_identity": previous_identity,
            "current_container_identity": None,
            "previous_container_stopped": False,
            "workspace_wiped": False,
            "candidate_logs_wiped": False,
        }
        self._phase = _BoundaryPhase.ROTATING
        try:
            await _run_transition_call(
                partial(
                    self._operations.stop_trial_container,
                    instance=state.instance,
                    expected_container_identity=previous_identity,
                )
            )
            receipt["previous_container_stopped"] = True
            await _run_transition_call(
                partial(
                    self._operations.reset_trial_mounts,
                    instance=state.instance,
                )
            )
            receipt["workspace_wiped"] = True
            receipt["candidate_logs_wiped"] = True
            identity = await _run_transition_call(
                partial(
                    self._operations.start_proposal_container,
                    instance=state.instance,
                    role=f"candidate.{invocation_id}",
                    workspace_dir=REMOTE_WORKSPACE_DIR,
                    logs_dir=REMOTE_LOGS_DIR,
                    tests_dir=REMOTE_TESTS_DIR,
                )
            )
            if not identity or identity == previous_identity:
                raise ProposalMorphBoundaryError("candidate reset did not produce a distinct container identity")
            state.container_identity = identity
            receipt["current_container_identity"] = identity
            receipt["status"] = "completed"
            _write_receipt(receipt_path, receipt)
            self._phase = _BoundaryPhase.CANDIDATE
            return ProposalCandidateInvocationTransition(
                invocation_id=invocation_id,
                previous_container_identity=previous_identity,
                current_container_identity=identity,
                runtime_archive_sha256=self.runtime_archive_sha256,
                receipt_path=receipt_path,
            )
        except BaseException:
            receipt["status"] = "failed"
            _write_receipt(receipt_path, receipt)
            self._phase = _BoundaryPhase.BROKEN
            raise

    async def upload_file(self, source_path: Path | str, target_path: str) -> None:
        async with self._io_lock:
            state = self._require_phase(_BoundaryPhase.CANDIDATE)
            target = _validated_remote_path(target_path)
            if not _is_candidate_upload_path(target):
                raise ProposalMorphBoundaryError(f"proposal candidate upload path is not allowlisted: {target}")
            content = _read_regular_file(
                Path(source_path),
                label="proposal upload source",
                max_bytes=_HANDOFF_MAX_TOTAL_BYTES,
            )
            await _run_transition_call(
                partial(
                    self._operations.write_instance_file,
                    instance=state.instance,
                    remote_path=target,
                    content=content,
                )
            )

    async def upload_dir(self, source_dir: Path | str, target_dir: str) -> None:
        async with self._io_lock:
            target = _validated_remote_path(target_dir)
            if target == REMOTE_TESTS_DIR:
                await _run_boundary_transition(lambda: self._upload_verifier_tests(Path(source_dir)))
                return
            if not _is_candidate_upload_path(target):
                raise ProposalMorphBoundaryError(f"proposal candidate upload path is not allowlisted: {target}")
            state = self._require_phase(_BoundaryPhase.CANDIDATE)
            await _run_transition_call(
                partial(
                    self._operations.upload_directory,
                    instance=state.instance,
                    local_path=Path(source_dir),
                    remote_path=target,
                )
            )

    async def download_file(
        self,
        source_path: str,
        target_path: Path | str,
    ) -> None:
        async with self._io_lock:
            source = _validated_remote_path(source_path)
            sealed = self._sealed_artifacts.get(source)
            if sealed is not None:
                content = _read_sealed_artifact(
                    sealed,
                    remote_path=source,
                )
            else:
                state = self._require_active()
                if self._phase is _BoundaryPhase.VERIFIER and _is_handoff_path(source):
                    raise FileNotFoundError(f"sealed proposal artifact not found: {source}")
                remote_content = await _run_transition_call(
                    partial(
                        self._operations.read_container_file,
                        instance=state.instance,
                        remote_path=source,
                    )
                )
                if remote_content is None:
                    raise FileNotFoundError(f"file not found in proposal Morph environment: {source}")
                content = remote_content
            target = Path(target_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

    async def download_dir(
        self,
        source_dir: str,
        target_dir: Path | str,
    ) -> None:
        async with self._io_lock:
            source = _validated_remote_path(source_dir)
            if source == _PROPOSAL_SESSION_ROOT and self._phase is _BoundaryPhase.VERIFIER:
                prefix = f"{_PROPOSAL_SESSION_ROOT}/"
                selected = {
                    remote_path: artifact
                    for remote_path, artifact in self._sealed_artifacts.items()
                    if remote_path.startswith(prefix)
                }
                if not selected:
                    raise FileNotFoundError(f"sealed proposal directory not found: {source}")
                destination = Path(target_dir)
                destination.mkdir(parents=True, exist_ok=True)
                for remote_path, artifact in sorted(selected.items()):
                    relative = PurePosixPath(remote_path).relative_to(PurePosixPath(_PROPOSAL_SESSION_ROOT))
                    target = destination.joinpath(*relative.parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(
                        _read_sealed_artifact(
                            artifact,
                            remote_path=remote_path,
                        )
                    )
                return

            state = self._require_active()
            archive = await _run_transition_call(
                partial(
                    self._operations.read_container_directory_archive,
                    instance=state.instance,
                    remote_path=source,
                )
            )
            if archive is None:
                raise FileNotFoundError(f"directory not found in proposal Morph environment: {source}")
            extract_archive(archive_bytes=archive, target_dir=Path(target_dir))

    async def is_dir(self, path: str) -> bool:
        source = _validated_remote_path(path)
        if source == _PROPOSAL_SESSION_ROOT and self._phase is _BoundaryPhase.VERIFIER:
            return any(remote_path.startswith(f"{_PROPOSAL_SESSION_ROOT}/") for remote_path in self._sealed_artifacts)
        return bool(await super().is_dir(source))

    async def exec(
        self,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_sec: int | None = None,
    ) -> ExecResult:
        async with self._io_lock:
            state = self._require_active()
            result = await _run_transition_call(
                partial(
                    self._operations.run_container_command_result,
                    instance=state.instance,
                    command=("bash", "-lc", command),
                    workdir=cwd,
                    env=env,
                    timeout_seconds=timeout_sec,
                )
            )
            return ExecResult(
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.exit_code,
            )

    async def _upload_verifier_tests(self, source_dir: Path) -> None:
        if self._phase is _BoundaryPhase.VERIFIER:
            await self._retry_verifier_tests(source_dir)
            return
        state = self._require_phase(_BoundaryPhase.CANDIDATE)
        tests_snapshot = _snapshot_tests(
            source_dir=source_dir,
            boundary_dir=self.boundary_dir,
        )
        previous_identity = state.container_identity
        receipt: dict[str, object] = {
            "schema_version": "aecbench.proposal-verifier-rotation.v1",
            "status": "started",
            "runtime_archive_sha256": self.runtime_archive_sha256,
            "runtime_archive_content_sha256": self.runtime_archive_content_sha256,
            "tests_content_sha256": tests_snapshot.content_sha256,
            "candidate_container_identity": previous_identity,
            "verifier_container_identity": None,
            "candidate_container_stopped": False,
            "artifacts_sealed": False,
            "mounts_wiped": False,
            "output_restored": False,
            "tests_uploaded": False,
            "sealed_output_sha256": None,
        }
        self._phase = _BoundaryPhase.ROTATING
        try:
            await _run_transition_call(
                partial(
                    self._operations.stop_trial_container,
                    instance=state.instance,
                    expected_container_identity=previous_identity,
                )
            )
            receipt["candidate_container_stopped"] = True
            artifacts = await _run_transition_call(
                partial(
                    self._operations.read_stopped_trial_artifacts,
                    instance=state.instance,
                )
            )
            sealed_handoff = _seal_artifacts(
                artifacts=artifacts,
                seal_dir=self.seal_dir,
                manifest_path=self.seal_manifest_path,
                runtime_archive_sha256=self.runtime_archive_sha256,
                runtime_archive_content_sha256=self.runtime_archive_content_sha256,
                environment_session_id=self.session_id,
                compute_backend=self.compute_backend,
            )
            sealed = sealed_handoff.artifacts
            self._sealed_artifacts = sealed
            if sealed_handoff.variant is _HandoffVariant.CANDIDATE_FAILURE:
                receipt["handoff_variant"] = sealed_handoff.variant.value
                receipt["candidate_failure_session_receipt_sha256"] = (
                    sealed_handoff.candidate_failure_session_receipt_sha256
                )
            receipt["artifacts_sealed"] = True
            if sealed_handoff.variant is _HandoffVariant.COMPLETED_OUTPUT:
                receipt["sealed_output_sha256"] = hashlib.sha256(
                    _read_sealed_artifact(
                        sealed[_OUTPUT_PATH],
                        remote_path=_OUTPUT_PATH,
                    )
                ).hexdigest()
            await _run_transition_call(
                partial(
                    self._operations.reset_trial_mounts,
                    instance=state.instance,
                )
            )
            receipt["mounts_wiped"] = True
            verifier_identity = await _run_transition_call(
                partial(
                    self._operations.start_proposal_container,
                    instance=state.instance,
                    role="verifier",
                    workspace_dir=REMOTE_WORKSPACE_DIR,
                    logs_dir=REMOTE_LOGS_DIR,
                    tests_dir=REMOTE_TESTS_DIR,
                )
            )
            if not verifier_identity or verifier_identity == previous_identity:
                raise ProposalMorphBoundaryError("verifier rotation did not produce a distinct container identity")
            state.container_identity = verifier_identity
            receipt["verifier_container_identity"] = verifier_identity
            if sealed_handoff.variant is _HandoffVariant.COMPLETED_OUTPUT:
                output_content = _read_sealed_artifact(
                    sealed[_OUTPUT_PATH],
                    remote_path=_OUTPUT_PATH,
                )
                await _run_transition_call(
                    partial(
                        self._operations.write_instance_file,
                        instance=state.instance,
                        remote_path=_OUTPUT_PATH,
                        content=output_content,
                    )
                )
                receipt["output_restored"] = True
            _verify_tests_snapshot(tests_snapshot)
            await _run_transition_call(
                partial(
                    self._operations.upload_directory,
                    instance=state.instance,
                    local_path=tests_snapshot.path,
                    remote_path=REMOTE_TESTS_DIR,
                )
            )
            receipt["tests_uploaded"] = True
            receipt["status"] = "completed"
            _write_receipt(self.rotation_receipt_path, receipt)
            self._tests_snapshot = tests_snapshot
            self._phase = _BoundaryPhase.VERIFIER
        except BaseException:
            receipt["status"] = "failed"
            _write_receipt(self.rotation_receipt_path, receipt)
            self._phase = _BoundaryPhase.BROKEN
            raise

    async def _retry_verifier_tests(self, source_dir: Path) -> None:
        state = self._require_phase(_BoundaryPhase.VERIFIER)
        if self._tests_snapshot is None:
            raise ProposalMorphBoundaryError("proposal verifier phase has no pinned tests snapshot")
        observed_sha256 = _tests_content_sha256(source_dir)
        if observed_sha256 != self._tests_snapshot.content_sha256:
            raise ProposalMorphBoundaryError("proposal verifier tests payload changed after rotation")
        _verify_tests_snapshot(self._tests_snapshot)
        await _run_transition_call(
            partial(
                self._operations.upload_directory,
                instance=state.instance,
                local_path=self._tests_snapshot.path,
                remote_path=REMOTE_TESTS_DIR,
            )
        )

    def _require_active(self) -> _ProposalMorphState:
        if self._phase is _BoundaryPhase.BROKEN:
            raise ProposalMorphBoundaryError("proposal Morph boundary is broken")
        if self._phase in {
            _BoundaryPhase.NEW,
            _BoundaryPhase.ROTATING,
            _BoundaryPhase.CLOSED,
        }:
            raise ProposalMorphBoundaryError(f"proposal Morph environment is not available during {self._phase.value}")
        if self._state is None:
            raise ProposalMorphBoundaryError("proposal Morph environment has no active provider state")
        return self._state

    def _require_phase(self, phase: _BoundaryPhase) -> _ProposalMorphState:
        state = self._require_active()
        if self._phase is not phase:
            raise ProposalMorphBoundaryError(f"proposal Morph operation requires {phase.value} phase")
        return state
