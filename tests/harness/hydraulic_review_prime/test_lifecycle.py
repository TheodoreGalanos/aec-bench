# ABOUTME: Proves hydraulic-review Prime sessions compose through the existing lifecycle checkpoint runner.
# ABOUTME: Covers fresh sessions, aggregate limits, fail-closed completion, recovery, and separate evidence.

from __future__ import annotations

import importlib
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from aec_bench.harness.hydraulic_review_prime.lifecycle import (
    HydraulicReviewPrimeLifecycleLimits,
    HydraulicReviewPrimeLifecycleRecoveryError,
    run_hydraulic_review_prime_lifecycle,
)
from aec_bench.ledger.immutable_byte_store import ImmutableArtifactCollisionError
from aec_bench.lifecycles.runtime.episode import LifecycleEpisodeEnvironmentFailure
from aec_bench.lifecycles.runtime.lifecycle import (
    LifecycleEpisodeExecutionError,
    load_evidence_lifecycle_spec,
    read_evidence_lifecycle_state,
)
from aec_bench.lifecycles.stormwater_design.hydraulic_review import (
    build_hydraulic_operation_resolver,
    materialize_hydraulic_review_lifecycle,
)
from aec_bench.lifecycles.stormwater_design.hydraulic_review_smoke import write_hydraulic_review_smoke_submission
from aec_bench.prime_agent.acp import PrimeAcpIsolation, PrimeAcpPaths, PrimeAcpRun
from aec_bench.prime_agent.refinement import (
    PrimeRefinementEvidence,
    PrimeRefinementMode,
    empty_refinement_candidate,
)
from aec_bench.prime_agent.session_evidence import (
    PrimeAcpRefinement,
    PrimeAcpTopology,
    PrimeAcpUsage,
)


def _limits(*, max_sessions: int = 5) -> HydraulicReviewPrimeLifecycleLimits:
    return HydraulicReviewPrimeLifecycleLimits(
        max_sessions=max_sessions,
        max_model_calls=8,
        max_tokens=1_000,
        max_cost_usd=Decimal("5"),
        max_wall_seconds=30,
    )


def _fake_executable(root: Path, name: str = "prime-agent") -> str:
    executable = root / name
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    return str(executable)


def _fake_prime_run(
    kwargs: dict[str, Any],
    *,
    index: int,
    session_state: str = "ended",
    stop_reason: str = "end_turn",
    limit_reason: str | None = None,
    error: str | None = None,
    usage_complete: bool = True,
    reported_isolation: PrimeAcpIsolation | None = None,
    reported_benchmark_valid: bool | None = None,
) -> PrimeAcpRun:
    actor_workspace = Path(kwargs["actor_workspace"])
    evidence_directory = Path(kwargs["evidence_directory"])
    evidence_directory.mkdir(parents=True)
    runtime = actor_workspace / ".fake-prime"
    state_dir = runtime / "state"
    session_dir = runtime / "sessions"
    state_dir.mkdir(parents=True)
    session_dir.mkdir(parents=True)
    paths = PrimeAcpPaths(
        state_dir=state_dir,
        session_dir=session_dir,
        inbound_file=evidence_directory / "prime-acp-in.jsonl",
        outbound_file=evidence_directory / "prime-acp-out.jsonl",
        stderr_file=evidence_directory / "prime-stderr.log",
        run_file=evidence_directory / "prime-run.json",
    )
    for path in (paths.inbound_file, paths.outbound_file, paths.stderr_file):
        path.write_text("", encoding="utf-8")
    paths.run_file.write_text('{"schema":"fake-prime-acp-run"}\n', encoding="utf-8")
    now = datetime.now(UTC)
    candidate = empty_refinement_candidate()
    usage = PrimeAcpUsage(
        complete=usage_complete,
        model_calls=1,
        input_tokens=10,
        output_tokens=5,
        cache_read_tokens=2,
        cache_write_tokens=3,
        total_tokens=20,
        cost_usd=Decimal("0.25"),
    )
    return PrimeAcpRun(
        command=("fake-prime",),
        prime_version="0.7.0",
        paths=paths,
        started_at=now,
        finished_at=now,
        elapsed_seconds=1.0,
        exit_code=0,
        session_id=f"fake-hydraulic-review-{index:03d}",
        protocol_version=1,
        agent_name="prime-agent",
        agent_version="0.7.0",
        agent_capabilities={},
        limits=kwargs["limits"],
        usage=usage,
        topology=PrimeAcpTopology(root_sessions=1, child_sessions=0),
        refinement=PrimeAcpRefinement(events=0, completed=0, failed=0, unknown=0),
        refinement_harness=PrimeRefinementEvidence(
            mode=PrimeRefinementMode.CAPTURE,
            candidate=candidate,
            global_candidate=candidate,
            sources=(),
            portable=True,
            issues=(),
            changed=False,
            drifted=False,
        ),
        limit_reason=limit_reason,
        session_state=session_state,
        stop_reason=stop_reason,
        timed_out=False,
        benchmark_valid=(
            kwargs["isolation"] is PrimeAcpIsolation.MACOS_SANDBOX and error is None
            if reported_benchmark_valid is None
            else reported_benchmark_valid
        ),
        isolation=kwargs["isolation"] if reported_isolation is None else reported_isolation,
        updates=(),
        error=error,
    )


def _runner(
    *,
    package: Path,
    run: Path,
    offer_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    calls: list[dict[str, Any]],
    offer_submission: bool = True,
    session_state: str = "ended",
    stop_reason: str = "end_turn",
    limit_reason: str | None = None,
    error: str | None = None,
    usage_complete: bool = True,
    reported_isolation: PrimeAcpIsolation | None = None,
    reported_benchmark_valid: bool | None = None,
) -> Callable[..., Any]:
    async def run_prime(**kwargs: Any) -> PrimeAcpRun:
        index = len(calls)
        calls.append(kwargs)
        actor_workspace = Path(kwargs["actor_workspace"])
        with monkeypatch.context() as patch:
            patch.syspath_prepend(str(actor_workspace))
            for name, value in kwargs["actor_environment"].items():
                patch.setenv(name, value)
            sys.modules.pop("hydraulic_review", None)
            client = importlib.import_module("hydraulic_review")
            capabilities = await client.capabilities()
            observation = await client.observe()
            await client.list_files(".")
            await client.read_file("instruction.md")
            assert len(capabilities["operations"]) == 6
            if offer_submission:
                resolver = build_hydraulic_operation_resolver(package, run)
                state = read_evidence_lifecycle_state(package, run, operation_resolver=resolver)
                checkpoint_id = str(state["active_checkpoint_id"])
                session_id = actor_workspace.name
                spec = load_evidence_lifecycle_spec(package)
                checkpoint = next(item for item in spec.checkpoints if item.checkpoint_id == checkpoint_id)
                assert not (run / "workspace" / checkpoint.submission_path).exists()
                offer_dir.mkdir(parents=True, exist_ok=True)
                candidate = offer_dir / f"{index:03d}.json"
                write_hydraulic_review_smoke_submission(
                    package,
                    run,
                    checkpoint_id,
                    session_id,
                    candidate,
                )
                submission = json.loads(candidate.read_text(encoding="utf-8"))
                assert observation["checkpoint_id"] == checkpoint_id
                await client.offer_submission(submission)
        return _fake_prime_run(
            kwargs,
            index=index,
            session_state=session_state,
            stop_reason=stop_reason,
            limit_reason=limit_reason,
            error=error,
            usage_complete=usage_complete,
            reported_isolation=reported_isolation,
            reported_benchmark_valid=reported_benchmark_valid,
        )

    return run_prime


def test_three_fresh_prime_sessions_complete_the_real_lifecycle_with_aggregate_usage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = materialize_hydraulic_review_lifecycle(tmp_path / "package")
    run = tmp_path / "run"
    calls: list[dict[str, Any]] = []
    result = run_hydraulic_review_prime_lifecycle(
        package_dir=package,
        run_dir=run,
        actor_workspace_root=tmp_path / "actors",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
        limits=_limits(),
        executable=_fake_executable(tmp_path),
        prime_session_runner=_runner(
            package=package,
            run=run,
            offer_dir=tmp_path / "offers",
            monkeypatch=monkeypatch,
            calls=calls,
        ),
    )

    assert result.lifecycle["status"] == "complete"
    assert result.verification["passed"] is True
    assert result.prime["status"] == "complete"
    assert result.prime["usage"]["model_calls"] == 3
    assert result.prime["usage"]["total_tokens"] == 60
    assert result.prime["usage"]["cost_usd"] == "0.75"
    assert len(result.prime["attempts"]) == 3
    assert not result.prime["benchmark_valid"]
    assert not result.benchmark_valid
    assert len(calls) == 3
    assert len({Path(call["actor_workspace"]) for call in calls}) == 3
    assert len({Path(call["evidence_directory"]) for call in calls}) == 3
    assert [call["limits"].max_model_calls for call in calls] == [8, 7, 6]
    assert [call["limits"].max_tokens for call in calls] == [1_000, 980, 960]
    assert [call["limits"].max_cost_usd for call in calls] == [Decimal("5"), Decimal("4.75"), Decimal("4.50")]
    assert [call["limits"].max_wall_seconds for call in calls] == [30, 29, 28]
    assert all("read them with `hydraulic_review.read_file()`" in call["instruction"] for call in calls)
    assert all("retry `import hydraulic_review` once" in call["instruction"] for call in calls)
    assert "verification" not in result.prime
    assert "reward" not in result.prime
    assert all(Path(item["prime_run"]).is_absolute() is False for item in result.prime["attempts"])


@pytest.mark.parametrize(
    ("offer_submission", "session_state", "stop_reason", "limit_reason", "error", "usage_complete"),
    [
        (False, "ended", "end_turn", None, None, True),
        (True, "cancelled", "cancelled", None, None, True),
        (True, "ended", "end_turn", "max_tokens", None, True),
        (True, "failed", "end_turn", None, "provider failed", True),
        (True, "ended", "end_turn", None, None, False),
    ],
)
def test_non_clean_prime_attempt_never_submits_or_advances(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    offer_submission: bool,
    session_state: str,
    stop_reason: str,
    limit_reason: str | None,
    error: str | None,
    usage_complete: bool,
) -> None:
    package = materialize_hydraulic_review_lifecycle(tmp_path / "package")
    run = tmp_path / "run"
    calls: list[dict[str, Any]] = []
    with pytest.raises(LifecycleEpisodeExecutionError):
        run_hydraulic_review_prime_lifecycle(
            package_dir=package,
            run_dir=run,
            actor_workspace_root=tmp_path / "actors",
            model="anthropic/test",
            isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
            limits=_limits(),
            executable=_fake_executable(tmp_path),
            prime_session_runner=_runner(
                package=package,
                run=run,
                offer_dir=tmp_path / "offers",
                monkeypatch=monkeypatch,
                calls=calls,
                offer_submission=offer_submission,
                session_state=session_state,
                stop_reason=stop_reason,
                limit_reason=limit_reason,
                error=error,
                usage_complete=usage_complete,
            ),
        )

    resolver = build_hydraulic_operation_resolver(package, run)
    state = read_evidence_lifecycle_state(package, run, operation_resolver=resolver)
    assert state["status"] == "awaiting_checkpoint_submission"
    assert state["active_checkpoint_id"] == "baseline_analysis"
    assert not (run / "episodes" / "baseline_analysis" / "submission.json").exists()
    assert not (run / "workspace" / "submissions" / "baseline_analysis.json").exists()
    manifest = json.loads((run / "prime" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert len(manifest["attempts"]) == 1
    assert len(calls) == 1


def test_returned_prime_isolation_must_match_the_requested_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = materialize_hydraulic_review_lifecycle(tmp_path / "package")
    run = tmp_path / "run"
    calls: list[dict[str, Any]] = []
    with pytest.raises(LifecycleEpisodeExecutionError):
        run_hydraulic_review_prime_lifecycle(
            package_dir=package,
            run_dir=run,
            actor_workspace_root=tmp_path / "actors",
            model="anthropic/test",
            isolation=PrimeAcpIsolation.MACOS_SANDBOX,
            limits=_limits(),
            executable=_fake_executable(tmp_path),
            prime_session_runner=_runner(
                package=package,
                run=run,
                offer_dir=tmp_path / "offers",
                monkeypatch=monkeypatch,
                calls=calls,
                reported_isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
                reported_benchmark_valid=True,
            ),
        )

    manifest = json.loads((run / "prime" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["attempts"][0]["isolation"] == "development_same_user"
    assert manifest["benchmark_valid"] is False
    assert not (run / "workspace" / "submissions" / "baseline_analysis.json").exists()


@pytest.mark.parametrize("changed_boundary", ["actor_workspace", "executable", "private_paths"])
def test_resume_rejects_a_changed_prime_execution_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed_boundary: str,
) -> None:
    package = materialize_hydraulic_review_lifecycle(tmp_path / "package")
    run = tmp_path / "run"
    actor_root = tmp_path / "actors"
    executable = _fake_executable(tmp_path)
    private_path = tmp_path / "private-one"
    private_path.mkdir()
    calls: list[dict[str, Any]] = []
    runner = _runner(
        package=package,
        run=run,
        offer_dir=tmp_path / "offers",
        monkeypatch=monkeypatch,
        calls=calls,
        offer_submission=False,
    )
    with pytest.raises(LifecycleEpisodeExecutionError):
        run_hydraulic_review_prime_lifecycle(
            package_dir=package,
            run_dir=run,
            actor_workspace_root=actor_root,
            model="anthropic/test",
            isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
            limits=_limits(),
            executable=executable,
            additional_private_paths=(private_path,),
            prime_session_runner=runner,
        )

    configuration = json.loads((run / "prime" / "configuration.json").read_text(encoding="utf-8"))
    assert configuration["executable"]["path"] == str(Path(executable).resolve())
    assert configuration["filesystem_boundary"]["actor_workspace_root"] == str(actor_root.resolve())
    assert configuration["filesystem_boundary"]["additional_private_paths"] == [str(private_path.resolve())]

    changed_actor_root = tmp_path / "other-actors" if changed_boundary == "actor_workspace" else actor_root
    changed_executable = (
        _fake_executable(tmp_path, "other-prime-agent") if changed_boundary == "executable" else executable
    )
    changed_private_path = tmp_path / "private-two" if changed_boundary == "private_paths" else private_path
    changed_private_path.mkdir(exist_ok=True)
    with pytest.raises(ImmutableArtifactCollisionError, match="configuration.json"):
        run_hydraulic_review_prime_lifecycle(
            package_dir=package,
            run_dir=run,
            actor_workspace_root=changed_actor_root,
            model="anthropic/test",
            isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
            limits=_limits(),
            executable=changed_executable,
            additional_private_paths=(changed_private_path,),
            prime_session_runner=runner,
        )

    assert len(calls) == 1


def test_aggregate_session_limit_stops_before_a_third_prime_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = materialize_hydraulic_review_lifecycle(tmp_path / "package")
    run = tmp_path / "run"
    calls: list[dict[str, Any]] = []
    with pytest.raises(LifecycleEpisodeEnvironmentFailure, match="session limit"):
        run_hydraulic_review_prime_lifecycle(
            package_dir=package,
            run_dir=run,
            actor_workspace_root=tmp_path / "actors",
            model="anthropic/test",
            isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
            limits=_limits(max_sessions=2),
            executable=_fake_executable(tmp_path),
            prime_session_runner=_runner(
                package=package,
                run=run,
                offer_dir=tmp_path / "offers",
                monkeypatch=monkeypatch,
                calls=calls,
            ),
        )

    assert len(calls) == 2
    resolver = build_hydraulic_operation_resolver(package, run)
    state = read_evidence_lifecycle_state(package, run, operation_resolver=resolver)
    assert state["active_checkpoint_id"] == "closeout_review"
    manifest = json.loads((run / "prime" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["usage"]["model_calls"] == 2
    assert len(manifest["attempts"]) == 2


def test_malformed_prior_prime_accounting_fails_closed_before_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = materialize_hydraulic_review_lifecycle(tmp_path / "package")
    run = tmp_path / "run"
    calls: list[dict[str, Any]] = []
    runner = _runner(
        package=package,
        run=run,
        offer_dir=tmp_path / "offers",
        monkeypatch=monkeypatch,
        calls=calls,
        offer_submission=False,
    )
    with pytest.raises(LifecycleEpisodeExecutionError):
        run_hydraulic_review_prime_lifecycle(
            package_dir=package,
            run_dir=run,
            actor_workspace_root=tmp_path / "actors",
            model="anthropic/test",
            isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
            limits=_limits(),
            executable=_fake_executable(tmp_path),
            prime_session_runner=runner,
        )
    attempt = next(run.glob("episodes/*/*/prime-attempt.json"))
    attempt.write_text("not json\n", encoding="utf-8")

    with pytest.raises(HydraulicReviewPrimeLifecycleRecoveryError, match="malformed"):
        run_hydraulic_review_prime_lifecycle(
            package_dir=package,
            run_dir=run,
            actor_workspace_root=tmp_path / "actors",
            model="anthropic/test",
            isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
            limits=_limits(),
            executable=_fake_executable(tmp_path),
            prime_session_runner=runner,
        )
    assert len(calls) == 1


def test_prior_prime_accounting_cannot_reference_another_episode_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = materialize_hydraulic_review_lifecycle(tmp_path / "package")
    run = tmp_path / "run"
    calls: list[dict[str, Any]] = []
    runner = _runner(
        package=package,
        run=run,
        offer_dir=tmp_path / "offers",
        monkeypatch=monkeypatch,
        calls=calls,
        offer_submission=False,
    )
    with pytest.raises(LifecycleEpisodeExecutionError):
        run_hydraulic_review_prime_lifecycle(
            package_dir=package,
            run_dir=run,
            actor_workspace_root=tmp_path / "actors",
            model="anthropic/test",
            isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
            limits=_limits(),
            executable=_fake_executable(tmp_path),
            prime_session_runner=runner,
        )
    attempt = next(run.glob("episodes/*/*/prime-attempt.json"))
    payload = json.loads(attempt.read_text(encoding="utf-8"))
    payload["prime_run"] = payload["transport_log"]
    payload["prime_run_sha256"] = payload["transport_log_sha256"]
    attempt.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(HydraulicReviewPrimeLifecycleRecoveryError, match="reference differs from its episode"):
        run_hydraulic_review_prime_lifecycle(
            package_dir=package,
            run_dir=run,
            actor_workspace_root=tmp_path / "actors",
            model="anthropic/test",
            isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
            limits=_limits(),
            executable=_fake_executable(tmp_path),
            prime_session_runner=runner,
        )
    assert len(calls) == 1


def test_runner_exception_is_not_masked_by_incomplete_prime_evidence(tmp_path: Path) -> None:
    package = materialize_hydraulic_review_lifecycle(tmp_path / "package")
    run = tmp_path / "run"

    async def broken_runner(**kwargs: Any) -> PrimeAcpRun:
        evidence_directory = Path(kwargs["evidence_directory"])
        evidence_directory.mkdir(parents=True)
        (evidence_directory / "partial.jsonl").write_text("{}\n", encoding="utf-8")
        raise RuntimeError("runner exploded")

    with pytest.raises(RuntimeError, match="runner exploded") as captured:
        run_hydraulic_review_prime_lifecycle(
            package_dir=package,
            run_dir=run,
            actor_workspace_root=tmp_path / "actors",
            model="anthropic/test",
            isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
            limits=_limits(),
            executable=_fake_executable(tmp_path),
            prime_session_runner=broken_runner,
        )

    assert any("Prime manifest reconciliation failed" in note for note in captured.value.__notes__)
