# ABOUTME: Tests the neutral generated-task identity contract.
# ABOUTME: Protects its persisted field names and hash validation.

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aec_bench.contracts.task_generation import TaskGenerationIdentity


def test_task_generation_identity_preserves_its_persisted_shape() -> None:
    identity = TaskGenerationIdentity(
        task_id="drainage/example-01",
        template="drainage-review",
        template_source_sha256="a" * 64,
        seed=42,
        instance_index=1,
    )

    assert identity.model_dump(mode="json") == {
        "task_id": "drainage/example-01",
        "origin": "generated",
        "template": "drainage-review",
        "template_source_sha256": "a" * 64,
        "seed": 42,
        "instance_index": 1,
    }


def test_task_generation_identity_rejects_an_invalid_template_hash() -> None:
    with pytest.raises(ValidationError, match="SHA-256 digest must contain 64 lowercase hexadecimal characters"):
        TaskGenerationIdentity(
            task_id="drainage/example-01",
            template="drainage-review",
            template_source_sha256="not-a-hash",
            seed=42,
            instance_index=1,
        )
