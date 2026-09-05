# ABOUTME: Checks experiment conditions before world or lifecycle execution starts.
# ABOUTME: Prevents project leakage and ambiguous repeated conditions in reproducible comparisons.

import pytest
from pydantic import ValidationError

from aec_bench.experimentation.engineering_decisions.definitions import (
    HydraulicExperiment,
    ProjectPartition,
    PumpExperiment,
    VerifierExperiment,
)


def test_a_project_cannot_cross_partitions_or_repeat_within_one() -> None:
    for partitions in (
        (ProjectPartition(split="train", seeds=(2, 2)),),
        (ProjectPartition(split="train", seeds=(2,)), ProjectPartition(split="acceptance", seeds=(2,))),
    ):
        with pytest.raises(ValidationError, match="exactly one partition"):
            HydraulicExperiment(partitions=partitions)


@pytest.mark.parametrize("seed", [True, 2.5, "2", -1])
def test_partition_seeds_are_strict_integers(seed: object) -> None:
    with pytest.raises(ValidationError):
        ProjectPartition.model_validate({"split": "train", "seeds": [seed]})


def test_unknown_and_duplicate_conditions_fail_before_execution() -> None:
    with pytest.raises(ValidationError, match="unknown hydraulic revision"):
        HydraulicExperiment(revisions=("unknown",))
    with pytest.raises(ValidationError, match="distinct"):
        VerifierExperiment(challenges=("none", "none"))
    with pytest.raises(ValidationError, match="distinct"):
        PumpExperiment(omit_verification_work=(True, True))
