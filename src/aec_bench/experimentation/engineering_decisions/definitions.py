# ABOUTME: Defines explicit reproducible conditions for four engineering decision experiments.
# ABOUTME: Assigns whole hydraulic lineages to dataset partitions before selecting revision siblings.

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from aec_bench.contracts.validators import StrictModel


class ProjectPartition(StrictModel):
    split: Literal["train", "development", "acceptance"]
    seeds: tuple[Annotated[int, Field(strict=True, ge=0)], ...]

    @model_validator(mode="after")
    def validate_seeds(self) -> Self:
        if not self.seeds or any(type(seed) is not int or seed < 0 for seed in self.seeds):
            raise ValueError("project seeds must be non-empty non-negative integers")
        return self


class HydraulicExperiment(StrictModel):
    experiment_id: Literal["hydraulic-counterfactual"] = "hydraulic-counterfactual"
    partitions: tuple[ProjectPartition, ...] = (
        ProjectPartition(split="train", seeds=(2,)),
        ProjectPartition(split="development", seeds=(8,)),
        ProjectPartition(split="acceptance", seeds=(12,)),
    )
    revisions: tuple[str, ...] = (
        "administrative_no_op",
        "major_idf_revision",
        "outlet_geometry_revision",
        "tailwater_revision",
    )

    @model_validator(mode="after")
    def validate_partitions(self) -> Self:
        seeds = [seed for partition in self.partitions for seed in partition.seeds]
        if not seeds or len(seeds) != len(set(seeds)):
            raise ValueError("each project seed must belong to exactly one partition")
        if not self.revisions or len(self.revisions) != len(set(self.revisions)):
            raise ValueError("revision conditions must be non-empty and distinct")
        from aec_bench.lifecycles.stormwater_design.hydraulic_review_variants import list_hydraulic_review_variant_ids

        if set(self.revisions) - set(list_hydraulic_review_variant_ids()):
            raise ValueError("experiment includes an unknown hydraulic revision")
        return self


HydraulicChallenge = Literal[
    "none", "reordered_decisions", "stale_source", "missing_memo", "false_readiness", "false_authority"
]
CHALLENGES: tuple[HydraulicChallenge, ...] = (
    "none",
    "reordered_decisions",
    "stale_source",
    "missing_memo",
    "false_readiness",
    "false_authority",
)


class VerifierExperiment(StrictModel):
    experiment_id: Literal["verifier-challenges"] = "verifier-challenges"
    seed: int = Field(default=2, ge=0, strict=True)
    revision: str = "major_idf_revision"
    challenges: tuple[HydraulicChallenge, ...] = CHALLENGES

    @model_validator(mode="after")
    def validate_conditions(self) -> Self:
        HydraulicExperiment(
            partitions=(ProjectPartition(split="development", seeds=(self.seed,)),), revisions=(self.revision,)
        )
        if not self.challenges or len(self.challenges) != len(set(self.challenges)):
            raise ValueError("challenge conditions must be non-empty and distinct")
        return self


DamPolicy = Literal["evidence_first", "unsupported", "late"]


class DamExperiment(StrictModel):
    experiment_id: Literal["dam-investigation"] = "dam-investigation"
    profiles: tuple[str, ...] = ("investigation-routine", "investigation-fault", "investigation-urgent-fault")
    policies: tuple[DamPolicy, ...] = ("evidence_first", "unsupported", "late")
    max_actions: int = Field(default=16, ge=1, strict=True)

    @model_validator(mode="after")
    def validate_conditions(self) -> Self:
        if not self.profiles or len(self.profiles) != len(set(self.profiles)):
            raise ValueError("dam profiles must be non-empty and distinct")
        if not self.policies or len(self.policies) != len(set(self.policies)):
            raise ValueError("dam policies must be non-empty and distinct")
        return self


class PumpExperiment(StrictModel):
    experiment_id: Literal["pump-handover"] = "pump-handover"
    profile: str = "pump-station-reference-system.asw-8-rs1.v1"
    horizon_seconds: int = Field(default=93600, gt=21600, strict=True)
    max_actions: int = Field(default=512, ge=1, strict=True)
    omit_verification_work: tuple[bool, ...] = (False, True)

    @model_validator(mode="after")
    def validate_conditions(self) -> Self:
        if not self.omit_verification_work or len(self.omit_verification_work) != len(set(self.omit_verification_work)):
            raise ValueError("pump handover conditions must be non-empty and distinct")
        return self
