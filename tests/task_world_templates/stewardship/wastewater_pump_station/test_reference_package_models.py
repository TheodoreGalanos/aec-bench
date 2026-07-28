# ABOUTME: Unit-tests the immutable wastewater pump-station reference-package model.
# ABOUTME: Proves that caller-owned JSON data cannot change a loaded production package.

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_models import (
    FrozenJsonValue,
    MutableJsonObject,
    ReferencePackage,
)


def test_reference_package_is_deeply_immutable() -> None:
    source = {"nested": [{"value": "kept"}]}
    document = cast(MutableJsonObject, source)

    package = ReferencePackage.from_documents(
        profile_id="profile",
        generation_id="generation",
        package_content_id="package",
        manifest_content_id="manifest",
        manifest=document,
        physical_member=document,
        physical_reference_checks=document,
        public_profile=document,
    )
    source["nested"][0]["value"] = "changed"

    nested = package.manifest["nested"]
    assert isinstance(nested, tuple)
    row = nested[0]
    assert isinstance(row, Mapping)
    assert row["value"] == "kept"
    with pytest.raises(TypeError):
        cast(MutableMapping[str, FrozenJsonValue], package.manifest)["extra"] = "blocked"
    with pytest.raises(FrozenInstanceError):
        package.__setattr__("profile_id", "changed")
