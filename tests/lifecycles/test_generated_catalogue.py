# ABOUTME: Tests explicit lifecycle-owner descriptors and generated composition.
# ABOUTME: Protects freshness, stable order, invalid descriptors, duplicate identities, and lookup behavior.

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from aec_bench.lifecycles.catalogue import lifecycle_definition, lifecycle_template_ids
from aec_bench.lifecycles.generated_catalogue import LIFECYCLE_DESCRIPTORS, load_lifecycle_definitions
from aec_bench.lifecycles.runtime.definition import LifecycleOwnerDescriptor
from aec_bench.lifecycles.stormwater_design.design_response import LIFECYCLE_DESCRIPTOR as DESIGN_RESPONSE_DESCRIPTOR
from aec_bench.lifecycles.stormwater_design.drainage_model import LIFECYCLE_DESCRIPTOR as DRAINAGE_MODEL_DESCRIPTOR
from aec_bench.lifecycles.stormwater_design.hydraulic_review import (
    LIFECYCLE_DESCRIPTOR as HYDRAULIC_REVIEW_DESCRIPTOR,
)
from aec_bench.lifecycles.structural_review.facade_submittal import (
    LIFECYCLE_DESCRIPTOR as FACADE_SUBMITTAL_DESCRIPTOR,
)
from scripts.generate_lifecycle_catalogue import OWNER_IMPORTS, render_catalogue


def test_each_concrete_lifecycle_owner_exposes_one_descriptor() -> None:
    assert LIFECYCLE_DESCRIPTORS == (
        DRAINAGE_MODEL_DESCRIPTOR,
        FACADE_SUBMITTAL_DESCRIPTOR,
        DESIGN_RESPONSE_DESCRIPTOR,
        HYDRAULIC_REVIEW_DESCRIPTOR,
    )


def test_generated_lifecycle_catalogue_matches_generator_output() -> None:
    generated_path = Path(__file__).parents[2] / "src" / "aec_bench" / "lifecycles" / "generated_catalogue.py"

    assert generated_path.read_text(encoding="utf-8") == render_catalogue()


def test_generated_lifecycle_catalogue_has_stable_order_and_current_lookup() -> None:
    definitions = load_lifecycle_definitions()
    template_ids = tuple(definition.metadata.template_id for definition in definitions)

    assert template_ids == tuple(sorted(template_ids))
    assert set(template_ids) == lifecycle_template_ids()
    assert all(lifecycle_definition(template_id) in definitions for template_id in template_ids)


def test_generator_supports_another_lifecycle_owner_and_sorts_it() -> None:
    additional_owner = (
        "asset-assurance-lifecycle",
        "aec_bench.lifecycles.asset_assurance",
        "LIFECYCLE_DESCRIPTOR",
        "ASSET_ASSURANCE_DESCRIPTOR",
    )

    rendered = render_catalogue((*OWNER_IMPORTS, additional_owner))

    assert "from aec_bench.lifecycles.asset_assurance import LIFECYCLE_DESCRIPTOR" in rendered
    assert rendered.index("ASSET_ASSURANCE_DESCRIPTOR,") < rendered.index("DRAINAGE_MODEL_DESCRIPTOR,")


def test_lifecycle_owner_descriptor_rejects_invalid_definition() -> None:
    with pytest.raises(TypeError, match="requires a LifecycleDefinition"):
        LifecycleOwnerDescriptor(definition=object())  # type: ignore[arg-type]


def test_generated_lifecycle_catalogue_rejects_duplicate_template_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    duplicate = LIFECYCLE_DESCRIPTORS[0]
    monkeypatch.setattr(
        "aec_bench.lifecycles.generated_catalogue.LIFECYCLE_DESCRIPTORS",
        (duplicate, duplicate),
    )

    with pytest.raises(ValueError, match="template IDs must be unique"):
        load_lifecycle_definitions()


def test_lifecycle_catalogue_import_does_not_load_optional_providers() -> None:
    source_root = Path(__file__).parents[2] / "src"
    probe = (
        "import sys; import aec_bench.lifecycles.catalogue; "
        "print(sorted(name for name in sys.modules if name.split('.')[0] in "
        "{'boto3', 'botocore', 'harbor', 'prime', 'verifiers', 'pydantic_ai', 'httpx'}))"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=source_root.parents[1],
        env={"PYTHONPATH": str(source_root)},
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "[]"
