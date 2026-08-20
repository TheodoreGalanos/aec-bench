# ABOUTME: Ordinary in-process values produced while sampling task templates.
# ABOUTME: Keeps generation inputs explicit without creating a serialized contract layer.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from aec_bench.templates.contracts import VisibilityLevel

if TYPE_CHECKING:
    from aec_bench.generation.replay import GenerationManifest


@dataclass(frozen=True, slots=True)
class SampledInstance:
    """A fully sampled task instance produced by the generation sampler."""

    instance_name: str
    all_params: dict[str, float | int | str]
    visible_params: dict[str, float | int | str]
    hidden_params: dict[str, float | int | str]
    ground_truth: dict[str, float]
    archetype_name: str
    site_context: str
    difficulty: str
    template_name: str
    seed: int
    instance_index: int
    visibility_level: VisibilityLevel


@dataclass(frozen=True, slots=True)
class GeneratedTaskSet:
    """Generated runnable task packages and their optional replay manifest."""

    output_root: Path
    task_paths: tuple[Path, ...]
    manifest: GenerationManifest
