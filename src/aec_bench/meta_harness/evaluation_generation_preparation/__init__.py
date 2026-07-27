# ABOUTME: Exposes phase-neutral services for preparing evaluation-generation task material.
# ABOUTME: Keeps historical experiment schemas behind explicit versioned compatibility adapters.

from aec_bench.meta_harness.evaluation_generation_preparation.task_material import (
    EvaluationTaskMaterial,
    EvaluationTaskMaterialError,
    EvaluationTaskMaterialSpec,
    load_evaluation_task_material,
    validate_disjoint_material_roots,
)

__all__ = (
    "EvaluationTaskMaterial",
    "EvaluationTaskMaterialError",
    "EvaluationTaskMaterialSpec",
    "load_evaluation_task_material",
    "validate_disjoint_material_roots",
)
