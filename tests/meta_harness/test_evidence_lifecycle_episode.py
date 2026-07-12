# ABOUTME: Tests the typed host-to-environment boundary for evidence-lifecycle episodes.
# ABOUTME: Proves identity, attempt ownership, failure closure, and reward separation.

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Never, cast

import pytest
from pydantic import ValidationError

import aec_bench.meta_harness.evidence_lifecycle as lifecycle_runtime
from aec_bench.meta_harness.evidence_lifecycle import (
    EvidenceLifecycleError,
    LifecycleEpisodeExecutionError,
    run_evidence_lifecycle,
)
from aec_bench.meta_harness.evidence_lifecycle_episode import (
    LifecycleEpisodeContext,
    LifecycleEpisodeEnvironment,
    LifecycleEpisodeEnvironmentFailure,
    LifecycleEpisodeRequest,
    LifecycleEpisodeResult,
    LifecycleEpisodeUsage,
    LifecycleExecutionMode,
    LifecycleVisibilityPolicy,
)
from aec_bench.task_world_templates.contracts import (
    EvidenceCheckpointSpec,
    EvidenceLifecycleSpec,
)


def test_episode_result_rejects_verifier_owned_fields() -> None:
    result = _completed_result(_request())
    payload = result.model_dump(mode="json")
    payload["reward"] = 1.0
    payload["passed"] = True

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        LifecycleEpisodeResult.model_validate(payload)


def test_episode_contract_enforces_mode_visibility_and_failure_consistency() -> None:
    request = _request()

    with pytest.raises(ValidationError, match="persistent_context execution requires persistent_context visibility"):
        LifecycleEpisodeRequest.model_validate(
            {
                **request.model_dump(mode="json"),
                "execution_mode": LifecycleExecutionMode.PERSISTENT_CONTEXT,
                "memory_visibility_policy": LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
            }
        )

    with pytest.raises(ValidationError, match="fresh_context episode must own exactly one checkpoint"):
        LifecycleEpisodeRequest.model_validate(
            {
                **request.model_dump(mode="json"),
                "checkpoint_ids": ["initial_review", "response_review"],
            }
        )

    persistent = LifecycleEpisodeRequest.model_validate(
        {
            **request.model_dump(mode="json"),
            "checkpoint_ids": ["initial_review", "response_review"],
            "execution_mode": LifecycleExecutionMode.PERSISTENT_CONTEXT,
            "memory_visibility_policy": LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
        }
    )
    assert persistent.checkpoint_ids == ("initial_review", "response_review")

    completed = _completed_result(request)
    with pytest.raises(ValidationError, match="fresh_context result must own exactly one checkpoint"):
        LifecycleEpisodeResult.model_validate(
            {
                **completed.model_dump(mode="json"),
                "checkpoint_ids": ["initial_review", "response_review"],
            }
        )
    with pytest.raises(ValidationError, match="completed episode cannot declare a failure"):
        LifecycleEpisodeResult.model_validate({**completed.model_dump(mode="json"), "failure_kind": "provider_error"})
    with pytest.raises(ValidationError, match="failed episode requires failure_kind"):
        LifecycleEpisodeResult.model_validate({**completed.model_dump(mode="json"), "status": "failed"})


def test_runner_opens_host_identity_before_environment_execution(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    environment = _RecordingEnvironment()

    lifecycle = run_evidence_lifecycle(
        package,
        run_dir,
        episode_environment=environment,
    )

    assert isinstance(environment, LifecycleEpisodeEnvironment)
    assert lifecycle["status"] == "complete"
    assert [request.checkpoint_id for request in environment.requests] == [
        "initial_review",
        "response_review",
    ]
    assert [request.session_id for request in environment.requests] == [
        "initial_review.session-001",
        "response_review.session-001",
    ]
    assert [request.attempt_id for request in environment.requests] == [
        "initial_review.attempt-001",
        "response_review.attempt-001",
    ]
    assert all(observation["attempt_was_active"] for observation in environment.observations)
    assert all(request.execution_mode is LifecycleExecutionMode.FRESH_CONTEXT for request in environment.requests)
    state = _read_json(run_dir / "state.json")
    assert [[attempt["status"] for attempt in item["attempts"]] for item in state["checkpoint_runs"]] == [
        ["submitted"],
        ["submitted"],
    ]


def test_host_request_preserves_session_identity_across_publication_interrupt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    environment = _RecordingEnvironment()
    original_open_attempt = lifecycle_runtime.open_checkpoint_attempt

    def interrupt_after_publication(*args: Any, **kwargs: Any) -> Never:
        original_open_attempt(*args, **kwargs)
        raise KeyboardInterrupt("simulated publication interruption")

    monkeypatch.setattr(lifecycle_runtime, "open_checkpoint_attempt", interrupt_after_publication)
    with pytest.raises(KeyboardInterrupt, match="simulated publication interruption"):
        run_evidence_lifecycle(package, run_dir, episode_environment=environment)

    first_session = run_dir / "episodes" / "initial_review" / "initial_review.session-001"
    request = _read_json(first_session / "episode_request.json")
    assert request["attempt_id"] == "initial_review.attempt-001"
    assert not (first_session / "episode_result.json").exists()

    monkeypatch.setattr(lifecycle_runtime, "open_checkpoint_attempt", original_open_attempt)
    result = run_evidence_lifecycle(package, run_dir, episode_environment=environment)

    assert result["status"] == "complete"
    interrupted_result = _read_json(first_session / "episode_result.json")
    assert interrupted_result["status"] == "failed"
    assert interrupted_result["failure_kind"] == "interrupted"
    state = _read_json(run_dir / "state.json")
    assert [attempt["status"] for attempt in state["checkpoint_runs"][0]["attempts"]] == [
        "interrupted",
        "submitted",
    ]


def test_retry_adopts_identical_request_left_before_attempt_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    environment = _RecordingEnvironment()
    original_open_attempt = lifecycle_runtime.open_checkpoint_attempt

    def interrupt_before_publication(*_args: Any, **_kwargs: Any) -> Never:
        raise KeyboardInterrupt("simulated pre-publication interruption")

    monkeypatch.setattr(lifecycle_runtime, "open_checkpoint_attempt", interrupt_before_publication)
    with pytest.raises(KeyboardInterrupt, match="simulated pre-publication interruption"):
        run_evidence_lifecycle(package, run_dir, episode_environment=environment)

    first_session = run_dir / "episodes" / "initial_review" / "initial_review.session-001"
    request_bytes = (first_session / "episode_request.json").read_bytes()
    state = _read_json(run_dir / "state.json")
    assert state["checkpoint_runs"][0]["attempts"] == []

    monkeypatch.setattr(lifecycle_runtime, "open_checkpoint_attempt", original_open_attempt)
    result = run_evidence_lifecycle(package, run_dir, episode_environment=environment)

    assert result["status"] == "complete"
    assert (first_session / "episode_request.json").read_bytes() == request_bytes
    assert not (first_session / "environment_prepared_episode_request.json").exists()
    state = _read_json(run_dir / "state.json")
    assert state["checkpoint_runs"][0]["attempts"][0]["status"] == "submitted"


def test_retry_adopts_v1_request_left_before_attempt_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    environment = _RecordingEnvironment()
    original_open_attempt = lifecycle_runtime.open_checkpoint_attempt

    def interrupt_before_publication(*_args: Any, **_kwargs: Any) -> Never:
        raise KeyboardInterrupt("simulated pre-publication interruption")

    monkeypatch.setattr(lifecycle_runtime, "open_checkpoint_attempt", interrupt_before_publication)
    with pytest.raises(KeyboardInterrupt, match="simulated pre-publication interruption"):
        run_evidence_lifecycle(package, run_dir, episode_environment=environment)

    request_path = run_dir / "episodes" / "initial_review" / "initial_review.session-001" / "episode_request.json"
    _downgrade_episode_request_and_state(request_path, run_dir / "state.json")
    request_bytes = request_path.read_bytes()

    monkeypatch.setattr(lifecycle_runtime, "open_checkpoint_attempt", original_open_attempt)
    result = run_evidence_lifecycle(package, run_dir, episode_environment=environment)

    assert result["status"] == "complete"
    assert request_path.read_bytes() == request_bytes
    assert environment.requests[0].schema_version == "1"


def test_recovery_accepts_v1_request_for_interrupted_v3_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    environment = _RecordingEnvironment()
    original_open_attempt = lifecycle_runtime.open_checkpoint_attempt

    def interrupt_after_publication(*args: Any, **kwargs: Any) -> Never:
        original_open_attempt(*args, **kwargs)
        raise KeyboardInterrupt("simulated publication interruption")

    monkeypatch.setattr(lifecycle_runtime, "open_checkpoint_attempt", interrupt_after_publication)
    with pytest.raises(KeyboardInterrupt, match="simulated publication interruption"):
        run_evidence_lifecycle(package, run_dir, episode_environment=environment)

    request_path = run_dir / "episodes" / "initial_review" / "initial_review.session-001" / "episode_request.json"
    _downgrade_episode_request_and_state(request_path, run_dir / "state.json")

    monkeypatch.setattr(lifecycle_runtime, "open_checkpoint_attempt", original_open_attempt)
    result = run_evidence_lifecycle(package, run_dir, episode_environment=environment)

    assert result["status"] == "complete"
    interrupted_result = _read_json(request_path.with_name("episode_result.json"))
    assert interrupted_result["status"] == "failed"
    assert interrupted_result["failure_kind"] == "interrupted"
    state = _read_json(run_dir / "state.json")
    assert state["schema_version"] == "4"
    assert [attempt["status"] for attempt in state["checkpoint_runs"][0]["attempts"]] == [
        "interrupted",
        "submitted",
    ]


def test_recovery_rejects_tampered_active_attempt_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    environment = _RecordingEnvironment()
    original_open_attempt = lifecycle_runtime.open_checkpoint_attempt

    def interrupt_after_publication(*args: Any, **kwargs: Any) -> Never:
        original_open_attempt(*args, **kwargs)
        raise KeyboardInterrupt("simulated publication interruption")

    monkeypatch.setattr(lifecycle_runtime, "open_checkpoint_attempt", interrupt_after_publication)
    with pytest.raises(KeyboardInterrupt, match="simulated publication interruption"):
        run_evidence_lifecycle(package, run_dir, episode_environment=environment)

    request_path = run_dir / "episodes" / "initial_review" / "initial_review.session-001" / "episode_request.json"
    request = _read_json(request_path)
    request["requested_model"] = "forged-model"
    request["package_sha256"] = "f" * 64
    _write_json(request_path, request)
    monkeypatch.setattr(lifecycle_runtime, "open_checkpoint_attempt", original_open_attempt)

    with pytest.raises(EvidenceLifecycleError, match="episode request hash mismatch"):
        run_evidence_lifecycle(package, run_dir, episode_environment=environment)

    state = _read_json(run_dir / "state.json")
    attempt = state["checkpoint_runs"][0]["attempts"][0]
    assert attempt["status"] == "active"
    assert attempt["episode_request_sha256"] != lifecycle_runtime._sha256(request_path)


def test_environment_exception_fails_attempt_without_archiving_submission(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"

    with pytest.raises(RuntimeError, match="environment exploded"):
        run_evidence_lifecycle(
            package,
            run_dir,
            episode_environment=_CrashingEnvironment(),
        )

    state = _read_json(run_dir / "state.json")
    attempt = state["checkpoint_runs"][0]["attempts"][0]
    assert attempt["status"] == "failed"
    assert attempt["failure_kind"] == "episode_environment_exception"
    assert not (run_dir / "episodes" / "initial_review" / "submission.json").exists()
    episode_result = _read_json(
        run_dir / "episodes" / "initial_review" / "initial_review.session-001" / "episode_result.json"
    )
    assert episode_result["status"] == "failed"
    assert episode_result["failure_kind"] == "episode_environment_exception"
    assert episode_result["requested_adapter"] == "deterministic"
    assert episode_result["adapter"] == "unresolved"


def test_blank_environment_failure_kind_is_closed_as_environment_exception(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"

    with pytest.raises(ValueError, match="failure_kind must not be blank"):
        run_evidence_lifecycle(
            package,
            run_dir,
            episode_environment=_BlankFailureKindEnvironment(),
        )

    state = _read_json(run_dir / "state.json")
    attempt = state["checkpoint_runs"][0]["attempts"][0]
    assert attempt["status"] == "failed"
    assert attempt["failure_kind"] == "episode_environment_exception"


def test_environment_cannot_prepopulate_host_owned_result_path(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"

    with pytest.raises(EvidenceLifecycleError, match="reserved artifacts"):
        run_evidence_lifecycle(
            package,
            run_dir,
            episode_environment=_PreparedHostResultEnvironment(),
        )

    result_dir = run_dir / "episodes" / "initial_review" / "initial_review.session-001"
    canonical = _read_json(result_dir / "episode_result.json")
    quarantined = _read_json(result_dir / "environment_prepared_episode_result.json")
    assert canonical["status"] == "failed"
    assert canonical["failure_kind"] == "episode_preparation_invalid"
    assert quarantined == {"environment_owned": True}
    state = _read_json(run_dir / "state.json")
    assert state["checkpoint_runs"][0]["attempts"][0]["status"] == "failed"


def test_mismatched_result_identity_fails_closed_before_submission(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"

    with pytest.raises(EvidenceLifecycleError, match="episode result identity does not match request"):
        run_evidence_lifecycle(
            package,
            run_dir,
            episode_environment=_MismatchedEnvironment(),
        )

    state = _read_json(run_dir / "state.json")
    attempt = state["checkpoint_runs"][0]["attempts"][0]
    assert attempt["status"] == "failed"
    assert attempt["failure_kind"] == "episode_result_identity_mismatch"
    assert not (run_dir / "episodes" / "initial_review" / "submission.json").exists()
    result_dir = run_dir / "episodes" / "initial_review" / "initial_review.session-001"
    canonical = _read_json(result_dir / "episode_result.json")
    rejected = _read_json(result_dir / "rejected_episode_result.json")
    assert canonical["attempt_id"] == "initial_review.attempt-001"
    assert canonical["failure_kind"] == "episode_result_identity_mismatch"
    assert rejected["attempt_id"] == "wrong.attempt-999"


def test_returned_failed_result_closes_attempt_without_submission(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"

    with pytest.raises(LifecycleEpisodeExecutionError, match="provider_error"):
        run_evidence_lifecycle(
            package,
            run_dir,
            episode_environment=_FailedEnvironment(),
        )

    state = _read_json(run_dir / "state.json")
    attempt = state["checkpoint_runs"][0]["attempts"][0]
    assert attempt["status"] == "failed"
    assert attempt["failure_kind"] == "provider_error"
    assert not (run_dir / "episodes" / "initial_review" / "submission.json").exists()
    episode_result = _read_json(
        run_dir / "episodes" / "initial_review" / "initial_review.session-001" / "episode_result.json"
    )
    assert episode_result["status"] == "failed"
    assert episode_result["failure_kind"] == "provider_error"


def test_failure_reconciliation_error_does_not_leave_host_attempt_active(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"

    with pytest.raises(LifecycleEpisodeExecutionError, match="provider_error") as raised:
        run_evidence_lifecycle(
            package,
            run_dir,
            episode_environment=_ReconciliationCrashingEnvironment(),
        )

    state = _read_json(run_dir / "state.json")
    attempt = state["checkpoint_runs"][0]["attempts"][0]
    assert attempt["status"] == "failed"
    assert attempt["failure_kind"] == "provider_error"
    assert any("failure reconciliation failed" in note for note in raised.value.__notes__)


def test_completed_result_without_submission_fails_attempt(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"

    with pytest.raises(EvidenceLifecycleError, match="checkpoint submission not found"):
        run_evidence_lifecycle(
            package,
            run_dir,
            episode_environment=_NoSubmissionEnvironment(),
        )

    state = _read_json(run_dir / "state.json")
    attempt = state["checkpoint_runs"][0]["attempts"][0]
    assert attempt["status"] == "failed"
    assert attempt["failure_kind"] == "episode_submission_invalid"


def test_unvalidated_result_payload_is_rejected_and_attempt_is_failed(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"

    with pytest.raises(EvidenceLifecycleError, match="invalid episode result"):
        run_evidence_lifecycle(
            package,
            run_dir,
            episode_environment=cast(LifecycleEpisodeEnvironment, _InvalidResultEnvironment()),
        )

    state = _read_json(run_dir / "state.json")
    attempt = state["checkpoint_runs"][0]["attempts"][0]
    assert attempt["status"] == "failed"
    assert attempt["failure_kind"] == "episode_result_invalid"
    assert not (run_dir / "episodes" / "initial_review" / "submission.json").exists()
    episode_result = _read_json(
        run_dir / "episodes" / "initial_review" / "initial_review.session-001" / "episode_result.json"
    )
    assert episode_result["status"] == "failed"
    assert episode_result["failure_kind"] == "episode_result_invalid"
    assert "reward" not in episode_result


def test_retry_cannot_submit_candidate_left_by_failed_attempt(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"

    with pytest.raises(LifecycleEpisodeExecutionError, match="provider_error"):
        run_evidence_lifecycle(
            package,
            run_dir,
            episode_environment=_FailedAfterWritingEnvironment(),
        )
    stale_payload = {"checkpoint_id": "initial_review", "source": "failed"}
    preserved = (
        run_dir / "episodes" / "initial_review" / "initial_review.session-001" / "failed_submission" / "submission.json"
    )
    assert _read_json(preserved) == stale_payload
    assert not (run_dir / "workspace" / "submissions" / "initial_review.json").exists()

    with pytest.raises(EvidenceLifecycleError, match="checkpoint submission not found"):
        run_evidence_lifecycle(
            package,
            run_dir,
            episode_environment=_NoSubmissionEnvironment(),
        )

    assert _read_json(preserved) == stale_payload
    assert not (run_dir / "episodes" / "initial_review" / "submission.json").exists()
    state = _read_json(run_dir / "state.json")
    assert [attempt["status"] for attempt in state["checkpoint_runs"][0]["attempts"]] == [
        "failed",
        "failed",
    ]


@dataclass
class _RecordingEnvironment:
    execution_mode: LifecycleExecutionMode = LifecycleExecutionMode.FRESH_CONTEXT
    memory_visibility_policy: LifecycleVisibilityPolicy = LifecycleVisibilityPolicy.ARTIFACT_MEMORY
    requested_adapter: str = "deterministic"
    requested_model: str = "gold"
    max_turns_per_session: int = 1
    requests: list[LifecycleEpisodeRequest] = field(default_factory=list)
    observations: list[dict[str, bool]] = field(default_factory=list)

    def recover(self, context: LifecycleEpisodeContext) -> None:
        assert context.active_checkpoint_id == context.checkpoint_id

    def prepare(self, _request: LifecycleEpisodeRequest) -> None:
        return None

    def record_failure(
        self,
        _request: LifecycleEpisodeRequest,
        *,
        failure_kind: str,
        provider_error: str | None,
    ) -> None:
        return None

    def execute(self, request: LifecycleEpisodeRequest) -> LifecycleEpisodeResult:
        self.requests.append(request)
        state = _read_json(Path(request.run_dir) / "state.json")
        checkpoint = next(item for item in state["checkpoint_runs"] if item["checkpoint_id"] == request.checkpoint_id)
        attempt_was_active = any(
            attempt["attempt_id"] == request.attempt_id
            and attempt["session_id"] == request.session_id
            and attempt["status"] == "active"
            for attempt in checkpoint["attempts"]
        )
        self.observations.append({"attempt_was_active": attempt_was_active})
        _write_json(Path(request.submission_path), {"checkpoint_id": request.checkpoint_id})
        return _completed_result(request)


@dataclass(frozen=True)
class _CrashingEnvironment:
    execution_mode: LifecycleExecutionMode = LifecycleExecutionMode.FRESH_CONTEXT
    memory_visibility_policy: LifecycleVisibilityPolicy = LifecycleVisibilityPolicy.ARTIFACT_MEMORY
    requested_adapter: str = "deterministic"
    requested_model: str = "gold"
    max_turns_per_session: int = 1

    def recover(self, _context: LifecycleEpisodeContext) -> None:
        return None

    def prepare(self, _request: LifecycleEpisodeRequest) -> None:
        return None

    def record_failure(
        self,
        _request: LifecycleEpisodeRequest,
        *,
        failure_kind: str,
        provider_error: str | None,
    ) -> None:
        return None

    def execute(self, _request: LifecycleEpisodeRequest) -> LifecycleEpisodeResult:
        raise RuntimeError("environment exploded")


@dataclass(frozen=True)
class _BlankFailureKindEnvironment(_CrashingEnvironment):
    def execute(self, _request: LifecycleEpisodeRequest) -> LifecycleEpisodeResult:
        raise LifecycleEpisodeEnvironmentFailure(" ", "blank kind")


@dataclass(frozen=True)
class _MismatchedEnvironment:
    execution_mode: LifecycleExecutionMode = LifecycleExecutionMode.FRESH_CONTEXT
    memory_visibility_policy: LifecycleVisibilityPolicy = LifecycleVisibilityPolicy.ARTIFACT_MEMORY
    requested_adapter: str = "deterministic"
    requested_model: str = "gold"
    max_turns_per_session: int = 1

    def recover(self, _context: LifecycleEpisodeContext) -> None:
        return None

    def prepare(self, _request: LifecycleEpisodeRequest) -> None:
        return None

    def record_failure(
        self,
        _request: LifecycleEpisodeRequest,
        *,
        failure_kind: str,
        provider_error: str | None,
    ) -> None:
        return None

    def execute(self, request: LifecycleEpisodeRequest) -> LifecycleEpisodeResult:
        _write_json(Path(request.submission_path), {"checkpoint_id": request.checkpoint_id})
        return _completed_result(request).model_copy(update={"attempt_id": "wrong.attempt-999"})


@dataclass(frozen=True)
class _PreparedHostResultEnvironment(_CrashingEnvironment):
    def prepare(self, request: LifecycleEpisodeRequest) -> None:
        result_dir = Path(request.run_dir) / "episodes" / request.checkpoint_id / request.session_id
        _write_json(result_dir / "episode_result.json", {"environment_owned": True})

    def execute(self, _request: LifecycleEpisodeRequest) -> LifecycleEpisodeResult:
        raise AssertionError("prepare violation must stop before execution")


@dataclass(frozen=True)
class _FailedEnvironment:
    execution_mode: LifecycleExecutionMode = LifecycleExecutionMode.FRESH_CONTEXT
    memory_visibility_policy: LifecycleVisibilityPolicy = LifecycleVisibilityPolicy.ARTIFACT_MEMORY
    requested_adapter: str = "deterministic"
    requested_model: str = "gold"
    max_turns_per_session: int = 1

    def recover(self, _context: LifecycleEpisodeContext) -> None:
        return None

    def prepare(self, _request: LifecycleEpisodeRequest) -> None:
        return None

    def record_failure(
        self,
        _request: LifecycleEpisodeRequest,
        *,
        failure_kind: str,
        provider_error: str | None,
    ) -> None:
        return None

    def execute(self, request: LifecycleEpisodeRequest) -> LifecycleEpisodeResult:
        return LifecycleEpisodeResult.model_validate(
            {
                **_completed_result(request).model_dump(mode="json"),
                "status": "failed",
                "failure_kind": "provider_error",
            }
        )


@dataclass(frozen=True)
class _ReconciliationCrashingEnvironment(_FailedEnvironment):
    def record_failure(
        self,
        _request: LifecycleEpisodeRequest,
        *,
        failure_kind: str,
        provider_error: str | None,
    ) -> None:
        raise RuntimeError("cannot reconcile environment artifact")


@dataclass(frozen=True)
class _FailedAfterWritingEnvironment:
    execution_mode: LifecycleExecutionMode = LifecycleExecutionMode.FRESH_CONTEXT
    memory_visibility_policy: LifecycleVisibilityPolicy = LifecycleVisibilityPolicy.ARTIFACT_MEMORY
    requested_adapter: str = "deterministic"
    requested_model: str = "gold"
    max_turns_per_session: int = 1

    def recover(self, _context: LifecycleEpisodeContext) -> None:
        return None

    def prepare(self, _request: LifecycleEpisodeRequest) -> None:
        return None

    def record_failure(
        self,
        _request: LifecycleEpisodeRequest,
        *,
        failure_kind: str,
        provider_error: str | None,
    ) -> None:
        return None

    def execute(self, request: LifecycleEpisodeRequest) -> LifecycleEpisodeResult:
        _write_json(Path(request.submission_path), {"checkpoint_id": request.checkpoint_id, "source": "failed"})
        return LifecycleEpisodeResult.model_validate(
            {
                **_completed_result(request).model_dump(mode="json"),
                "status": "failed",
                "failure_kind": "provider_error",
            }
        )


@dataclass(frozen=True)
class _NoSubmissionEnvironment:
    execution_mode: LifecycleExecutionMode = LifecycleExecutionMode.FRESH_CONTEXT
    memory_visibility_policy: LifecycleVisibilityPolicy = LifecycleVisibilityPolicy.ARTIFACT_MEMORY
    requested_adapter: str = "deterministic"
    requested_model: str = "gold"
    max_turns_per_session: int = 1

    def recover(self, _context: LifecycleEpisodeContext) -> None:
        return None

    def prepare(self, _request: LifecycleEpisodeRequest) -> None:
        return None

    def record_failure(
        self,
        _request: LifecycleEpisodeRequest,
        *,
        failure_kind: str,
        provider_error: str | None,
    ) -> None:
        return None

    def execute(self, request: LifecycleEpisodeRequest) -> LifecycleEpisodeResult:
        return _completed_result(request)


@dataclass(frozen=True)
class _InvalidResultEnvironment:
    execution_mode: LifecycleExecutionMode = LifecycleExecutionMode.FRESH_CONTEXT
    memory_visibility_policy: LifecycleVisibilityPolicy = LifecycleVisibilityPolicy.ARTIFACT_MEMORY
    requested_adapter: str = "deterministic"
    requested_model: str = "gold"
    max_turns_per_session: int = 1

    def recover(self, _context: LifecycleEpisodeContext) -> None:
        return None

    def prepare(self, _request: LifecycleEpisodeRequest) -> None:
        return None

    def record_failure(
        self,
        _request: LifecycleEpisodeRequest,
        *,
        failure_kind: str,
        provider_error: str | None,
    ) -> None:
        return None

    def execute(self, request: LifecycleEpisodeRequest) -> object:
        return {**_completed_result(request).model_dump(mode="json"), "reward": 1.0}


def _request() -> LifecycleEpisodeRequest:
    return LifecycleEpisodeRequest(
        episode_id="lifecycle.demo.initial_review.attempt-001",
        lifecycle_id="lifecycle.demo",
        world_id="world.demo",
        lifecycle_spec_sha256="0" * 64,
        package_sha256="1" * 64,
        checkpoint_id="initial_review",
        checkpoint_ids=("initial_review",),
        attempt_id="initial_review.attempt-001",
        session_id="initial_review.session-001",
        execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
        memory_visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
        requested_adapter="deterministic",
        requested_model="gold",
        max_turns_per_session=1,
        title="Initial Review",
        instruction="Complete the initial review.",
        workspace="/tmp/run/workspace",
        run_dir="/tmp/run",
        instruction_path="/tmp/run/workspace/instruction.md",
        submission_path="/tmp/run/workspace/submissions/initial_review.json",
        released_files=("initial.txt",),
        completed_checkpoint_ids=(),
    )


def _completed_result(request: LifecycleEpisodeRequest) -> LifecycleEpisodeResult:
    return LifecycleEpisodeResult(
        episode_id=request.episode_id,
        attempt_id=request.attempt_id,
        session_id=request.session_id,
        checkpoint_ids=request.checkpoint_ids,
        execution_mode=request.execution_mode,
        memory_visibility_policy=request.memory_visibility_policy,
        status="completed",
        requested_adapter="deterministic",
        requested_model="gold",
        max_turns_per_session=request.max_turns_per_session,
        adapter="in_process",
        resolved_model="gold",
        configuration={"source": "test"},
        usage=LifecycleEpisodeUsage(),
    )


def _write_package(package: Path) -> Path:
    spec = EvidenceLifecycleSpec(
        lifecycle_id="lifecycle.demo",
        world_id="world.demo",
        checkpoints=[_checkpoint("initial_review"), _checkpoint("response_review")],
    )
    _write_json(package / "lifecycle.json", spec.model_dump(mode="json"))
    for checkpoint in spec.checkpoints:
        instruction_path = package / checkpoint.instruction_path
        instruction_path.parent.mkdir(parents=True, exist_ok=True)
        instruction_path.write_text(f"Complete {checkpoint.checkpoint_id}.\n", encoding="utf-8")
        release_dir = package / checkpoint.release_path
        release_dir.mkdir(parents=True, exist_ok=True)
        (release_dir / f"{checkpoint.checkpoint_id}.txt").write_text("evidence\n", encoding="utf-8")
    return package


def _checkpoint(checkpoint_id: str) -> EvidenceCheckpointSpec:
    return EvidenceCheckpointSpec(
        checkpoint_id=checkpoint_id,
        title=checkpoint_id.replace("_", " ").title(),
        release_path=f"releases/{checkpoint_id}",
        instruction_path=f"instructions/{checkpoint_id}.md",
        submission_path=f"submissions/{checkpoint_id}.json",
    )


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _downgrade_episode_request_and_state(request_path: Path, state_path: Path) -> None:
    request = _read_json(request_path)
    request["schema_version"] = "1"
    request.pop("evidence_request_catalog")
    request.pop("released_evidence_artifacts")
    request_path.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    state = _read_json(state_path)
    state["schema_version"] = "3"
    for checkpoint in state["checkpoint_runs"]:
        checkpoint.pop("evidence_request_budget")
        checkpoint.pop("evidence_request_budget_remaining")
        checkpoint.pop("evidence_request_actions")
        for attempt in checkpoint["attempts"]:
            attempt.pop("inherited_from_parent")
    attempts = state["checkpoint_runs"][0]["attempts"]
    if attempts:
        attempts[0]["episode_request_sha256"] = lifecycle_runtime._sha256(request_path)
    _write_json(state_path, state)


def _read_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
