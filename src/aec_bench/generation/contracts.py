# ABOUTME: Pydantic contract models for generated task instances.
# ABOUTME: Covers generation provenance metadata and the full sampled instance envelope.

from datetime import datetime

from aec_bench.contracts.validators import StrictModel
from aec_bench.templates.contracts import VisibilityLevel


class GenerationMetadata(StrictModel):
    """Provenance record for a generated task instance."""

    origin: str = "generated"
    template: str
    template_version: str = "1.0"
    seed: int
    timestamp: datetime
    difficulty: str
    visibility_level: VisibilityLevel
    archetype: str
    site_context: str


class SampledInstance(StrictModel):
    """A fully sampled task instance produced by the generation sampler."""

    instance_name: str
    all_params: dict[str, float | int | str]
    visible_params: dict[str, float | int | str]
    hidden_params: dict[str, float | int | str]
    ground_truth: dict[str, float]
    archetype_name: str
    site_context: str
    difficulty: str
    metadata: GenerationMetadata
