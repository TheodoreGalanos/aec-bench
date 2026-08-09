# ABOUTME: Tests clean Prime baseline and fixed-candidate qualification across pump profiles.
# ABOUTME: Confirms that qualification records evidence but makes no promotion decision.

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.contracts.world_session import StewardshipStateSnapshotRef
from aec_bench.experimentation.qualification.prime_refinement import (
    DEFAULT_QUALIFICATION_PROFILES,
    PrimeRefinementTreatment,
    run_prime_refinement_qualification,
)
from aec_bench.harness.pump_station_prime.evidence import PumpStationPrimeJourneyLimits
from aec_bench.harness.pump_station_prime.journey import PumpStationPrimeJourneyRun
from aec_bench.prime_agent.acp import PrimeAcpIsolation
from aec_bench.prime_agent.refinement import (
    PrimeRefinementCandidate,
    PrimeRefinementEntry,
    PrimeRefinementKind,
    PrimeRefinementMode,
    PrimeRefinementScope,
    empty_refinement_candidate,
)
from aec_bench.prime_agent.session_evidence import PrimeAcpUsage
from aec_bench.worlds.stewardship.wastewater_pump_station.evaluation import (
    evaluate_pump_station_reference_run,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)


def _candidate() -> PrimeRefinementCandidate:
    return PrimeRefinementCandidate(
        prime_harness_schema=1,
        entries=(
            PrimeRefinementEntry(
                id="compact-action-state",
                kind=PrimeRefinementKind.MEMORY,
                title="Keep compact action state",
                content="Keep one compact state and reconcile it with observe().",
                path="pump/stewardship",
                scope=PrimeRefinementScope.LOCAL,
                reference={},
                arguments={},
                metadata={},
                source="refine",
                created_at="2026-08-09T00:00:00Z",
                updated_at="2026-08-09T00:00:00Z",
                version=1,
            ),
        ),
    )


def _limits() -> PumpStationPrimeJourneyLimits:
    return PumpStationPrimeJourneyLimits(
        max_sessions=4,
        max_host_controls=4,
        max_world_actions=100,
        max_model_calls=20,
        max_tokens=10_000,
        max_cost_usd=Decimal("20"),
        max_wall_seconds=600,
    )


@pytest.mark.asyncio
async def test_qualifies_one_candidate_in_clean_fixed_treatment_cells(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aec_bench.experimentation.qualification.prime_refinement as qualification_module

    candidate = _candidate()
    calls: list[dict[str, Any]] = []
    selected_profiles: list[str] = []

    async def fake_journey(**kwargs: Any) -> PumpStationPrimeJourneyRun:
        calls.append(kwargs)
        assert kwargs["refinement_mode"] is PrimeRefinementMode.CANDIDATE
        world_directory = cast(Path, kwargs["world_run_directory"])
        repository = PumpStationWorldRunRepository(world_directory)
        run = PumpStationWorldRun.resume_reference_system(
            repository=repository,
            snapshot=repository.current_snapshot(),
        )
        selected_profiles.append(run.manifest.reference_system_id)
        evidence_directory = cast(Path, kwargs["evidence_directory"])
        evidence_directory.mkdir(parents=True)
        run_file = evidence_directory / "prime-world-journey.json"
        run_file.write_text(json.dumps({"host_policy_sha256": "a" * 64}) + "\n", encoding="utf-8")
        selected_snapshot = run.snapshot()
        snapshot = StewardshipStateSnapshotRef(
            run_id=selected_snapshot.run_id,
            episode_id=selected_snapshot.episode_id,
            world_branch_id=selected_snapshot.world_branch_id,
            sequence=selected_snapshot.sequence,
            state_id=selected_snapshot.state_id,
            commit_id=selected_snapshot.commit_id,
        )
        return PumpStationPrimeJourneyRun(
            segments=(),
            host_controls=(),
            final_snapshot=snapshot,
            world_state="active",
            completion="incomplete",
            stop_reason="no-eligible-host-control",
            verification=run.verify(),
            evaluation=evaluate_pump_station_reference_run(run, evaluation_scope="bounded_continuation"),
            usage=PrimeAcpUsage(
                complete=True,
                model_calls=1,
                input_tokens=10,
                output_tokens=5,
                cache_read_tokens=0,
                cache_write_tokens=0,
                total_tokens=15,
                cost_usd=Decimal("0.10"),
            ),
            elapsed_seconds=1.0,
            world_action_attempts=0,
            run_file=run_file,
            benchmark_valid=True,
            refinement_candidate=cast(PrimeRefinementCandidate, kwargs["refinement_candidate"]),
        )

    monkeypatch.setattr(qualification_module, "run_pump_station_prime_journey", fake_journey)
    result = await run_prime_refinement_qualification(
        output_directory=tmp_path / "qualification",
        qualification_id="prime-refinement-study",
        candidate=candidate,
        instruction="Complete the pump-station stewardship task.",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.MACOS_SANDBOX,
        limits=_limits(),
    )

    assert selected_profiles == [
        DEFAULT_QUALIFICATION_PROFILES[0],
        DEFAULT_QUALIFICATION_PROFILES[0],
        DEFAULT_QUALIFICATION_PROFILES[1],
        DEFAULT_QUALIFICATION_PROFILES[1],
    ]
    assert [call["refinement_candidate"] for call in calls] == [
        empty_refinement_candidate(),
        candidate,
        empty_refinement_candidate(),
        candidate,
    ]
    assert len({call["actor_workspace"] for call in calls}) == 4
    assert len({call["world_run_directory"] for call in calls}) == 4
    assert result.report.decision == "pending"
    assert result.report.evidence_valid
    assert [observation.treatment for observation in result.report.observations] == [
        PrimeRefinementTreatment.BASELINE,
        PrimeRefinementTreatment.CANDIDATE,
        PrimeRefinementTreatment.BASELINE,
        PrimeRefinementTreatment.CANDIDATE,
    ]
    assert len(result.report.contrasts) == 2
    report_text = result.report_file.read_text(encoding="utf-8")
    assert str(tmp_path) not in report_text
    assert result.report.content_sha256 in report_text


@pytest.mark.asyncio
async def test_rejects_an_unknown_profile_before_creating_evidence(tmp_path: Path) -> None:
    output_directory = tmp_path / "qualification"

    with pytest.raises(ValueError, match="unknown pump reference profiles"):
        await run_prime_refinement_qualification(
            output_directory=output_directory,
            qualification_id="prime-refinement-study",
            candidate=_candidate(),
            instruction="Complete the pump-station stewardship task.",
            model="anthropic/test",
            isolation=PrimeAcpIsolation.MACOS_SANDBOX,
            limits=_limits(),
            profile_ids=("unknown-profile",),
        )

    assert not output_directory.exists()
