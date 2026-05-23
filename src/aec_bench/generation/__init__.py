# ABOUTME: Generation package for the aec-bench instance sampler.
# ABOUTME: Re-exports key types for convenient import by downstream modules.

from aec_bench.generation.contracts import GenerationMetadata, SampledInstance
from aec_bench.generation.dataset import (
    CompositionPlan,
    CoverageWarning,
    DatasetManifest,
    DatasetSummary,
    InstanceEntry,
    PlannedInstance,
    SuiteConfig,
    compose_dataset,
    execute_plan,
    load_suite_config,
)
from aec_bench.generation.sampler import sample_instance

__all__ = [
    "CompositionPlan",
    "CoverageWarning",
    "DatasetManifest",
    "DatasetSummary",
    "GenerationMetadata",
    "InstanceEntry",
    "PlannedInstance",
    "SampledInstance",
    "SuiteConfig",
    "compose_dataset",
    "execute_plan",
    "load_suite_config",
    "sample_instance",
]
