# ABOUTME: Tests for validating LLM-reviewed task part decomposition sidecars.
# ABOUTME: Ensures crossover-facing decomposition artifacts stay structured.

import pytest
from pydantic import ValidationError

from aec_bench.contracts.task_decomposition import TaskDecompositionBatch


def test_task_decomposition_batch_accepts_structured_parts() -> None:
    batch = TaskDecompositionBatch.model_validate(
        {
            "version": 1,
            "reviewer": "codex-spark",
            "scope": "mechanical",
            "decompositions": [
                {
                    "task_id": "mechanical/velocity-check",
                    "source_genome_path": "task_genomes/templates/mechanical/velocity-check.yaml",
                    "parts": [
                        {
                            "id": "pipe_flow_inputs",
                            "kind": "input",
                            "summary": "Flow and diameter define pipe section velocity",
                            "depends_on": [],
                            "recombinable": True,
                            "crossover_role": "hydraulic input bundle",
                        },
                        {
                            "id": "velocity_range_check",
                            "kind": "threshold",
                            "summary": "Compare calculated velocity to allowed range",
                            "depends_on": ["pipe_flow_inputs"],
                            "recombinable": True,
                            "crossover_role": "compliance decision",
                        },
                    ],
                    "trajectory_checks": ["shows pipe area before velocity"],
                    "crossover_notes": ["range thresholds can recombine with other flow tasks"],
                }
            ],
        }
    )

    assert batch.decompositions[0].parts[1].kind == "threshold"


def test_task_decomposition_rejects_absolute_source_paths() -> None:
    with pytest.raises(ValidationError):
        TaskDecompositionBatch.model_validate(
            {
                "reviewer": "codex-spark",
                "scope": "bad",
                "decompositions": [
                    {
                        "task_id": "mechanical/bad",
                        "source_genome_path": "/tmp/bad.yaml",
                        "parts": [],
                    }
                ],
            }
        )


def test_task_decomposition_rejects_trailing_ellipsis_text() -> None:
    with pytest.raises(ValidationError):
        TaskDecompositionBatch.model_validate(
            {
                "reviewer": "codex-spark",
                "scope": "mechanical",
                "decompositions": [
                    {
                        "task_id": "mechanical/velocity-check",
                        "source_genome_path": ("task_genomes/templates/mechanical/velocity-check.yaml"),
                        "parts": [
                            {
                                "id": "calculation_chain",
                                "kind": "formula",
                                "summary": "Calculate pipe velocity from flow...",
                                "depends_on": [],
                                "recombinable": True,
                                "crossover_role": "calculation kernel",
                            }
                        ],
                    }
                ],
            }
        )
