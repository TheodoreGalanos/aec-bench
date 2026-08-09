# ABOUTME: Tests strict ASW-8 station-data selection, identity, and promotion checks.
# ABOUTME: Proves the accepted v1 package stays unchanged while v2 adds three pumps.

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import cast

import pytest

from aec_bench.worlds.stewardship.wastewater_pump_station.reference_package_models import (
    FrozenJsonObject,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_package_reader import (
    REFERENCE_PROFILE_V1,
    REFERENCE_PROFILE_V2,
    ReferencePackageError,
    bundled_reference_package_root,
    load_reference_package,
)

_V1_HASHES = {
    "physical-member.json": "e9d311fae3fd634a7cead1a27cd3282cce5758feb6a39e34c4e68e1e5651b9c5",
    "physical-reference-checks.json": "f84bafeb2298d6742241bdc0037f2a6f841e8e12a384e7e935c6d9e9730f834f",
    "promotion-manifest.json": "26113e9f4fdcaa1b08fa53d01fd6bf63892ef2146582e00c8dd1a8328940e832",
    "public-profile.json": "71087fcaa884fa394256f4bdd7b9b289c2f778cb60a635571132ae21720b3ee1",
}


def _asset(package_value: FrozenJsonObject) -> FrozenJsonObject:
    return cast(FrozenJsonObject, package_value["asset"])


def test_v1_bytes_and_default_route_remain_unchanged() -> None:
    root = bundled_reference_package_root()

    assert root.name == "reference_package"
    assert load_reference_package().profile_id == REFERENCE_PROFILE_V1
    assert {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in root.iterdir()} == _V1_HASHES


def test_v2_route_loads_exact_three_pump_promoted_package() -> None:
    root = bundled_reference_package_root(profile_id=REFERENCE_PROFILE_V2)
    package = load_reference_package(profile_id=REFERENCE_PROFILE_V2)
    asset = _asset(package.physical_member)

    assert root.as_posix().endswith("reference_packages/au-nsw-lh-syn-sps-v2")
    assert package.profile_id == REFERENCE_PROFILE_V2
    assert package.physical_member["schema_id"] == "pump-station-physical-member.v2"
    assert package.physical_reference_checks["schema_id"] == "pump-station-physical-reference-checks.v2"
    assert package.public_profile["schema_id"] == "pump-station-public-profile.v2"
    assert package.manifest["schema_id"] == "pump-station-promotion-manifest.v2"
    assert tuple(cast(tuple[str, ...], asset["component_ids"])) == (
        "pump-a",
        "pump-b",
        "pump-c",
    )
    assert asset["maximum_running_pumps"] == 2
    assert asset["service_capacity_units_per_running_pump"] == 1
    assert asset["test_running_service_capacity_units"] == 0


@pytest.mark.parametrize(
    ("profile_id", "root_profile"),
    [
        (REFERENCE_PROFILE_V1, REFERENCE_PROFILE_V2),
        (REFERENCE_PROFILE_V2, REFERENCE_PROFILE_V1),
    ],
)
def test_cross_profile_package_use_fails_closed(
    profile_id: str,
    root_profile: str,
) -> None:
    with pytest.raises(ReferencePackageError) as raised:
        load_reference_package(
            bundled_reference_package_root(profile_id=root_profile),
            profile_id=profile_id,
        )

    assert raised.value.code in {"file-content-drift", "manifest-shape", "payload-schema"}


def test_unregistered_profile_fails_closed() -> None:
    with pytest.raises(ReferencePackageError) as raised:
        bundled_reference_package_root(profile_id="AU-NSW-LH-SYN-SPS-v3")

    assert raised.value.code == "unknown-reference-profile"


def test_v2_mutation_fails_exact_identity_check(tmp_path: Path) -> None:
    package_root = Path(
        shutil.copytree(
            bundled_reference_package_root(profile_id=REFERENCE_PROFILE_V2),
            tmp_path / "v2-package",
        )
    )
    member_path = package_root / "physical-member.json"
    member_path.write_bytes(member_path.read_bytes().replace(b'"pump-c"', b'"pump-d"'))

    with pytest.raises(ReferencePackageError) as raised:
        load_reference_package(package_root, profile_id=REFERENCE_PROFILE_V2)

    assert raised.value.code == "file-content-drift"
