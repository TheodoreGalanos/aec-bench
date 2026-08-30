# ABOUTME: Runs clean baseline and fixed-candidate Prime journeys on pump reference profiles.
# ABOUTME: Keeps refinement qualification with experiments, separate from execution runtimes.

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import field_validator, model_validator

from aec_bench import worlds
from aec_bench.contracts.content_address import ContentAddressedModel
from aec_bench.contracts.evaluation_result import StewardshipEvaluation
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.harness_kernel import validate_sha256
from aec_bench.contracts.trial_record import ExecutionStatus, TrialRecord
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr
from aec_bench.experimentation.meta_harness import HarnessCandidate, HarnessCandidateTrials, run_harness_study
from aec_bench.harness.prime_world_actor import run_prime_world_actor_session
from aec_bench.harness.pump_station_prime.evidence import PumpStationPrimeJourneyLimits
from aec_bench.harness.pump_station_trial import run_pump_station_trial
from aec_bench.harness.world_trials import WorldTrialRunner, run_world_experiment
from aec_bench.ledger.writer import write_trial_record_at
from aec_bench.prime_agent.acp import PrimeAcpIsolation
from aec_bench.prime_agent.refinement import (
    PrimeRefinementCandidate,
    PrimeRefinementMode,
    empty_refinement_candidate,
    validate_refinement_request,
)
from aec_bench.prime_agent.session_evidence import PrimeAcpUsage
from aec_bench.trials import plan_trials
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import PUMP_STATION_TASK_WORLD_ID
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_system import (
    PUMP_STATION_REFERENCE_SYSTEM_ID,
    PUMP_STATION_REFERENCE_SYSTEM_RS2_ID,
    list_reference_system_ids,
)

QUALIFICATION_REPORT_NAME = "prime-refinement-qualification.json"
QUALIFICATION_CANDIDATE_NAME = "prime-refinement-candidate.json"
DEFAULT_QUALIFICATION_PROFILES = (
    PUMP_STATION_REFERENCE_SYSTEM_ID,
    PUMP_STATION_REFERENCE_SYSTEM_RS2_ID,
)


class PrimeRefinementTreatment(StrEnum):
    """The two fixed harness treatments in a qualification comparison."""

    BASELINE = "baseline"
    CANDIDATE = "candidate"


class PrimeRefinementQualificationLimits(FrozenStrictModel):
    """Serializable journey limits shared by every qualification cell."""

    max_sessions: int
    max_host_controls: int
    max_world_actions: int
    max_model_calls: int
    max_tokens: int
    max_cost_usd: Decimal
    max_wall_seconds: float

    @classmethod
    def from_journey_limits(cls, limits: PumpStationPrimeJourneyLimits) -> PrimeRefinementQualificationLimits:
        return cls(
            max_sessions=limits.max_sessions,
            max_host_controls=limits.max_host_controls,
            max_world_actions=limits.max_world_actions,
            max_model_calls=limits.max_model_calls,
            max_tokens=limits.max_tokens,
            max_cost_usd=limits.max_cost_usd,
            max_wall_seconds=limits.max_wall_seconds,
        )


class PrimeRefinementQualificationObservation(ContentAddressedModel):
    """One independently evaluated baseline or candidate journey."""

    schema_version: Literal["aecbench.prime-refinement-observation.v1"] = "aecbench.prime-refinement-observation.v1"
    order: int
    profile_id: NonEmptyStr
    repetition: int
    treatment: PrimeRefinementTreatment
    candidate_sha256: str
    journey_file: NonEmptyStr
    host_policy_sha256: str
    completion: NonEmptyStr
    world_state: NonEmptyStr
    stop_reason: NonEmptyStr
    benchmark_valid: bool
    verification_valid: bool
    evaluation: StewardshipEvaluation
    usage: PrimeAcpUsage
    elapsed_seconds: float
    world_action_count: int

    @field_validator("candidate_sha256", "host_policy_sha256")
    @classmethod
    def validate_digest(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.order < 0 or self.repetition < 1:
            raise ValueError("Prime refinement observation order and repetition are out of range")
        if self.elapsed_seconds < 0 or self.world_action_count < 0:
            raise ValueError("Prime refinement observation counts must not be negative")
        return self


class PrimeRefinementQualificationContrast(FrozenStrictModel):
    """The paired evidence identities for one profile and repetition."""

    profile_id: NonEmptyStr
    repetition: int
    baseline_observation_sha256: str
    candidate_observation_sha256: str

    @field_validator("baseline_observation_sha256", "candidate_observation_sha256")
    @classmethod
    def validate_digest(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("repetition")
    @classmethod
    def validate_repetition(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Prime refinement contrast repetition must be positive")
        return value


class PrimeRefinementQualificationReport(ContentAddressedModel):
    """Complete comparison evidence with an explicit pending human decision."""

    schema_version: Literal["aecbench.prime-refinement-qualification.v1"] = "aecbench.prime-refinement-qualification.v1"
    qualification_id: NonEmptyStr
    candidate: PrimeRefinementCandidate
    baseline_sha256: str
    profile_ids: tuple[NonEmptyStr, ...]
    repetitions: int
    instruction_sha256: str
    model_requested: NonEmptyStr
    isolation: PrimeAcpIsolation
    pump_station_guidance: bool
    limits: PrimeRefinementQualificationLimits
    observations: tuple[PrimeRefinementQualificationObservation, ...]
    contrasts: tuple[PrimeRefinementQualificationContrast, ...]
    evidence_valid: bool
    decision: Literal["pending"] = "pending"

    @field_validator("baseline_sha256", "instruction_sha256")
    @classmethod
    def validate_digest(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_design(self) -> Self:
        if not self.profile_ids or len(set(self.profile_ids)) != len(self.profile_ids):
            raise ValueError("Prime refinement qualification profiles must be distinct")
        if self.repetitions < 1:
            raise ValueError("Prime refinement qualification repetitions must be positive")
        expected = len(self.profile_ids) * self.repetitions * len(PrimeRefinementTreatment)
        if len(self.observations) != expected:
            raise ValueError("Prime refinement qualification observation count differs from its design")
        if tuple(observation.order for observation in self.observations) != tuple(range(expected)):
            raise ValueError("Prime refinement qualification observation order must be complete")
        if len(self.contrasts) != len(self.profile_ids) * self.repetitions:
            raise ValueError("Prime refinement qualification contrast count differs from its design")
        observations = {
            (observation.profile_id, observation.repetition, observation.treatment): observation
            for observation in self.observations
        }
        if len(observations) != expected:
            raise ValueError("Prime refinement qualification observations must have distinct cells")
        expected_cells = {
            (profile_id, repetition, treatment)
            for profile_id in self.profile_ids
            for repetition in range(1, self.repetitions + 1)
            for treatment in PrimeRefinementTreatment
        }
        if set(observations) != expected_cells:
            raise ValueError("Prime refinement qualification observations differ from its design")
        if any(
            observation.candidate_sha256
            != (
                self.baseline_sha256
                if treatment is PrimeRefinementTreatment.BASELINE
                else self.candidate.content_sha256
            )
            for (_profile_id, _repetition, treatment), observation in observations.items()
        ):
            raise ValueError("Prime refinement qualification observation has another treatment")
        if len({observation.host_policy_sha256 for observation in self.observations}) != 1:
            raise ValueError("Prime refinement qualification host policy differs between cells")
        expected_contrasts = {
            (
                profile_id,
                repetition,
                observations[(profile_id, repetition, PrimeRefinementTreatment.BASELINE)].content_sha256,
                observations[(profile_id, repetition, PrimeRefinementTreatment.CANDIDATE)].content_sha256,
            )
            for profile_id in self.profile_ids
            for repetition in range(1, self.repetitions + 1)
        }
        actual_contrasts = {
            (
                contrast.profile_id,
                contrast.repetition,
                contrast.baseline_observation_sha256,
                contrast.candidate_observation_sha256,
            )
            for contrast in self.contrasts
        }
        if actual_contrasts != expected_contrasts:
            raise ValueError("Prime refinement qualification contrasts differ from its observations")
        if self.evidence_valid != all(
            observation.benchmark_valid and observation.verification_valid and observation.evaluation.valid
            for observation in self.observations
        ):
            raise ValueError("Prime refinement qualification validity differs from its observations")
        return self


@dataclass(frozen=True, slots=True)
class PrimeRefinementQualificationRun:
    """One completed qualification run and its durable report path."""

    report: PrimeRefinementQualificationReport
    report_file: Path


async def run_prime_refinement_qualification(
    *,
    output_directory: Path,
    qualification_id: str,
    candidate: PrimeRefinementCandidate,
    instruction: str,
    model: str,
    isolation: PrimeAcpIsolation,
    limits: PumpStationPrimeJourneyLimits,
    profile_ids: tuple[str, ...] = DEFAULT_QUALIFICATION_PROFILES,
    repetitions: int = 1,
    pump_station_guidance: bool = False,
    executable: str = "prime-agent",
    environment: Mapping[str, str] | None = None,
    run_trial: WorldTrialRunner | None = None,
) -> PrimeRefinementQualificationRun:
    """Compare an empty harness with one candidate through normal world trial records."""
    validate_refinement_request(PrimeRefinementMode.CANDIDATE, candidate)
    _validate_design(profile_ids, repetitions)
    output_directory = output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=False)
    candidate_file = output_directory / QUALIFICATION_CANDIDATE_NAME
    candidate_file.write_text(candidate.model_dump_json(indent=2) + "\n", encoding="utf-8")

    baseline = empty_refinement_candidate()
    tasks = [
        worlds.task(PUMP_STATION_TASK_WORLD_ID, profile=profile_id, instruction=instruction)
        for profile_id in profile_ids
    ]
    selected_runner = run_trial
    if selected_runner is None:
        from functools import partial

        selected_runner = partial(run_pump_station_trial, actor=run_prime_world_actor_session)

    async def evaluate_candidate(
        harness: HarnessCandidate[PrimeRefinementCandidate],
    ) -> list[TrialRecord]:
        parameters: dict[str, object] = {
            "isolation": isolation.value,
            "max_sessions": limits.max_sessions,
            "max_host_controls": limits.max_host_controls,
            "max_world_actions": limits.max_world_actions,
            "max_model_calls": limits.max_model_calls,
            "max_tokens": limits.max_tokens,
            "max_cost_usd": str(limits.max_cost_usd),
            "max_wall_seconds": limits.max_wall_seconds,
            "pump_station_guidance": pump_station_guidance,
            "refinement_mode": PrimeRefinementMode.CANDIDATE.value,
            "refinement_candidate": harness.value.model_dump(mode="json"),
            "executable": executable,
        }
        if environment is not None:
            parameters["environment"] = dict(environment)
        agent = AgentConfig(name=harness.candidate_id, adapter="prime-agent", model=model, parameters=parameters)
        trials = plan_trials(
            f"{qualification_id}-{harness.candidate_id}",
            tasks=tasks,
            agents=[agent],
            compute=ComputeConfig(backend="local"),
            repetitions=repetitions,
        )
        records = await run_world_experiment(tasks=tasks, trials=trials, run_trial=selected_runner)
        for record in records:
            write_trial_record_at(
                path=output_directory / "cells" / harness.candidate_id / f"{record.trial_id}.json",
                record=record,
            )
        return records

    study = await run_harness_study(
        baseline=HarnessCandidate(PrimeRefinementTreatment.BASELINE.value, baseline),
        candidates=[HarnessCandidate(PrimeRefinementTreatment.CANDIDATE.value, candidate)],
        evaluate=evaluate_candidate,
        assess=lambda _baseline, _candidates: None,
    )
    candidate_trials = study.candidates[0]
    record_cells = {
        (profile_id, repetition, treatment): record
        for treatment, trial_set in (
            (PrimeRefinementTreatment.BASELINE, study.baseline),
            (PrimeRefinementTreatment.CANDIDATE, candidate_trials),
        )
        for profile_id in profile_ids
        for repetition, record in _records_for_profile(trial_set, profile_id)
    }
    observations: list[PrimeRefinementQualificationObservation] = []
    contrasts: list[PrimeRefinementQualificationContrast] = []
    for profile_id in profile_ids:
        for repetition in range(1, repetitions + 1):
            paired: dict[PrimeRefinementTreatment, PrimeRefinementQualificationObservation] = {}
            for treatment, selected_candidate in (
                (PrimeRefinementTreatment.BASELINE, baseline),
                (PrimeRefinementTreatment.CANDIDATE, candidate),
            ):
                observation = _observation_from_record(
                    record_cells[(profile_id, repetition, treatment)],
                    output_directory=output_directory,
                    order=len(observations),
                    profile_id=profile_id,
                    repetition=repetition,
                    treatment=treatment,
                    candidate=selected_candidate,
                )
                observations.append(observation)
                paired[treatment] = observation
            contrasts.append(
                PrimeRefinementQualificationContrast(
                    profile_id=profile_id,
                    repetition=repetition,
                    baseline_observation_sha256=paired[PrimeRefinementTreatment.BASELINE].content_sha256,
                    candidate_observation_sha256=paired[PrimeRefinementTreatment.CANDIDATE].content_sha256,
                )
            )

    report = PrimeRefinementQualificationReport(
        qualification_id=qualification_id,
        candidate=candidate,
        baseline_sha256=baseline.content_sha256,
        profile_ids=profile_ids,
        repetitions=repetitions,
        instruction_sha256=hashlib.sha256(instruction.encode("utf-8")).hexdigest(),
        model_requested=model,
        isolation=isolation,
        pump_station_guidance=pump_station_guidance,
        limits=PrimeRefinementQualificationLimits.from_journey_limits(limits),
        observations=tuple(observations),
        contrasts=tuple(contrasts),
        evidence_valid=all(
            observation.benchmark_valid and observation.verification_valid and observation.evaluation.valid
            for observation in observations
        ),
    )
    report_file = output_directory / QUALIFICATION_REPORT_NAME
    report_file.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return PrimeRefinementQualificationRun(report=report, report_file=report_file)


def _validate_design(profile_ids: tuple[str, ...], repetitions: int) -> None:
    if not profile_ids or len(set(profile_ids)) != len(profile_ids):
        raise ValueError("Prime refinement qualification profiles must be distinct")
    unknown = set(profile_ids) - set(list_reference_system_ids())
    if unknown:
        raise ValueError(f"unknown pump reference profiles: {', '.join(sorted(unknown))}")
    if repetitions < 1:
        raise ValueError("Prime refinement qualification repetitions must be positive")


def _records_for_profile(
    trial_set: HarnessCandidateTrials[PrimeRefinementCandidate], profile_id: str
) -> list[tuple[int, TrialRecord]]:
    selected = [record for record in trial_set.records if record.task_id.endswith(f"/{profile_id}")]
    return [(index, record) for index, record in enumerate(selected, start=1)]


def _observation_from_record(
    record: TrialRecord,
    *,
    output_directory: Path,
    order: int,
    profile_id: str,
    repetition: int,
    treatment: PrimeRefinementTreatment,
    candidate: PrimeRefinementCandidate,
) -> PrimeRefinementQualificationObservation:
    if record.output is None or record.output.agent_output is None or record.output.agent_result is None:
        raise ValueError("Prime world TrialRecord lacks its normalized result")
    if record.evaluation is None or record.cost is None:
        raise ValueError("Prime world TrialRecord lacks evaluation or usage")
    journey_file = Path(record.output.agent_output.output_path)
    journey = json.loads(journey_file.read_text(encoding="utf-8"))
    host_policy_sha256 = journey.get("host_policy_sha256")
    if not isinstance(host_policy_sha256, str):
        raise ValueError("Prime journey evidence lacks its host policy digest")
    evaluation = record.evaluation
    cost = record.cost
    stewardship = evaluation.stewardship
    if stewardship is None:
        raise ValueError("Prime world TrialRecord lacks pump stewardship evaluation")
    result = record.output.agent_result
    return PrimeRefinementQualificationObservation(
        order=order,
        profile_id=profile_id,
        repetition=repetition,
        treatment=treatment,
        candidate_sha256=candidate.content_sha256,
        journey_file=(output_directory / "cells" / treatment.value / f"{record.trial_id}.json")
        .relative_to(output_directory)
        .as_posix(),
        host_policy_sha256=host_policy_sha256,
        completion=str(result["completion"]),
        world_state=str(result["world_state"]),
        stop_reason=str(result["stop_reason"]),
        benchmark_valid=record.execution_status is ExecutionStatus.COMPLETED,
        verification_valid=evaluation.validity.verifier_completed,
        evaluation=stewardship,
        usage=PrimeAcpUsage(
            complete=record.execution_status is ExecutionStatus.COMPLETED,
            model_calls=cost.model_calls or 0,
            input_tokens=cost.tokens_in or 0,
            output_tokens=cost.tokens_out or 0,
            cache_read_tokens=cost.cache_read_tokens or 0,
            cache_write_tokens=cost.cache_write_tokens or 0,
            total_tokens=(cost.tokens_in or 0) + (cost.tokens_out or 0),
            cost_usd=Decimal(str(cost.estimated_cost_usd or 0)),
        ),
        elapsed_seconds=record.timing.agent_seconds or record.timing.total_seconds,
        world_action_count=int(result["world_action_count"]),
    )
