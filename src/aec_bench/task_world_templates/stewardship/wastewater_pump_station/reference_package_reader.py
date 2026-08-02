# ABOUTME: Strictly loads the certified wastewater pump-station production reference package.
# ABOUTME: Rejects inventory, schema, identity, rights, visibility, and content drift.

from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path
from typing import Any, NoReturn, cast

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_models import (
    MutableJsonObject,
    ReferencePackage,
)

EXPECTED_PACKAGE_CONTENT_ID = "642da8bdfad63d7324e0c5886f1f8f3866c9a6bd25f165fa2a5937d68e8a5e16"
EXPECTED_MANIFEST_CONTENT_ID = "ab9a6b91afb0aff6229fafd10b6d748e873904cf8f43c3d195f56f57775209b8"
REFERENCE_PROFILE_V1 = "AU-NSW-LH-SYN-SPS-v1"
REFERENCE_PROFILE_V2 = "AU-NSW-LH-SYN-SPS-v2"
REFERENCE_PACKAGE_FILE_NAMES = (
    "physical-member.json",
    "physical-reference-checks.json",
    "promotion-manifest.json",
    "public-profile.json",
)

_PROFILE_ID = REFERENCE_PROFILE_V1
_GENERATION_ID = "738bc2b31f40ae7ea7831a54826c10c7e1f8084e64a6c0e0883bc6290aa84c8e"
_MEMBER_CONTENT_ID = "55c1c11746ec59bac6632a96de1c2c97eb26b9b6642908ba23c187f0a8509133"
_MANIFEST_SPECIFICATION_ID = "asw-0b5.promotion-manifest-specification.v1"
_RIGHTS_DECISION_ID = "repository-original-redistributable"
_MANIFEST_DOMAIN = b"asw-0b5.promotion-manifest.v1\0"
_PAYLOAD_DOMAIN = b"asw-0b5.promoted-payload.v1\0"
_PACKAGE_DOMAIN = b"asw-0b5.promoted-package.v1\0"
_EXPECTED_FILE_IDENTITIES = {
    "physical-member.json": (
        4487,
        "e9d311fae3fd634a7cead1a27cd3282cce5758feb6a39e34c4e68e1e5651b9c5",
    ),
    "physical-reference-checks.json": (
        5250,
        "f84bafeb2298d6742241bdc0037f2a6f841e8e12a384e7e935c6d9e9730f834f",
    ),
    "promotion-manifest.json": (
        293117,
        "26113e9f4fdcaa1b08fa53d01fd6bf63892ef2146582e00c8dd1a8328940e832",
    ),
    "public-profile.json": (
        1131,
        "71087fcaa884fa394256f4bdd7b9b289c2f778cb60a635571132ae21720b3ee1",
    ),
}
_EXPECTED_VERSIONS = {
    "manifest": "asw-0b5.promotion-manifest.v1",
    "package": "asw-au-nsw-lh-syn-sps.package.v1",
    "physical_member": "asw-0b5.physical-member.v1",
    "physical_reference_checks": "asw-0b5.physical-reference-checks.v1",
    "public_profile": "asw-0b5.public-profile.v1",
}
_EXPECTED_COMPATIBILITY = {
    "historical_runtime_bytes": "none",
    "migration": "none",
    "predecessor": "none",
    "replacement": "new-manifest-and-package-id-only",
    "supersession": "immutable",
    "unknown_fields": "reject",
    "unknown_files": "reject",
}
_EXPECTED_VISIBILITY = {
    "actor_visible_payloads": [],
    "certification_private_payloads": [],
    "holdout_sensitive_payloads": [],
    "host_private_payloads": ["physical-member", "physical-reference-checks"],
    "public_payloads": ["public-profile"],
}
_ROLE_EXPECTATIONS = {
    "physical-member": {
        "relative_path": "physical-member.json",
        "schema_identity": "asw-0b5.physical-member.v1",
        "visibility_class": "host-private",
    },
    "physical-reference-checks": {
        "relative_path": "physical-reference-checks.json",
        "schema_identity": "asw-0b5.physical-reference-checks.v1",
        "visibility_class": "host-private",
    },
    "public-profile": {
        "relative_path": "public-profile.json",
        "schema_identity": "asw-0b5.public-profile.v1",
        "visibility_class": "public",
    },
}
_MANIFEST_KEYS = {
    "authority",
    "claims",
    "compatibility",
    "evidence",
    "fields",
    "generation",
    "package",
    "retirement",
    "versions",
    "visibility",
}
_PAYLOAD_KEYS = {
    "physical-member": {
        "asset",
        "composites",
        "member_content_id",
        "orderings",
        "parameters",
        "profile_id",
        "rules",
        "schema_id",
    },
    "physical-reference-checks": {
        "checks",
        "generation_id",
        "member_content_id",
        "profile_id",
        "schema_id",
    },
    "public-profile": {
        "asset",
        "claim_ceiling",
        "context",
        "generation_id",
        "license",
        "manifest_specification_id",
        "permitted_claim_ids",
        "profile_id",
        "prohibited_claim_ids",
        "schema_id",
    },
}


class ReferencePackageError(ValueError):
    """Raised when the production reference package differs from its contract."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> NoReturn:
    raise ReferencePackageError(code, detail)


def bundled_reference_package_root(*, profile_id: str = REFERENCE_PROFILE_V1) -> Path:
    """Return the production-owned package directory for one registered profile."""
    if profile_id == REFERENCE_PROFILE_V1:
        return Path(__file__).with_name("reference_package")
    if profile_id == REFERENCE_PROFILE_V2:
        return Path(__file__).with_name("reference_packages") / "au-nsw-lh-syn-sps-v2"
    _fail("unknown-reference-profile", profile_id)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            _fail("duplicate-json-key", key)
        value[key] = child
    return value


def _reject_non_integer_number(value: str) -> NoReturn:
    _fail("canonical-json", f"non-integer JSON number {value!r}")


def _check_json_value(value: object) -> None:
    if value is None or isinstance(value, float):
        _fail("canonical-json", "null and floating-point values are forbidden")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                _fail("canonical-json", "object key is not text")
            _check_json_value(child)
    elif isinstance(value, list):
        for child in value:
            _check_json_value(child)
    elif not isinstance(value, str | int | bool):
        _fail("canonical-json", "unsupported JSON value")


def _canonical_json(value: object) -> bytes:
    _check_json_value(value)
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _read_object(path: Path) -> tuple[MutableJsonObject, bytes]:
    try:
        raw = path.read_bytes()
    except OSError as error:
        _fail("package-read", f"{path.name}: {error}")
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n") or b"\r" in raw or raw.startswith(b"\xef\xbb\xbf"):
        _fail("canonical-json", f"{path.name} has non-canonical line bytes")
    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_float=_reject_non_integer_number,
            parse_constant=_reject_non_integer_number,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        _fail("canonical-json", f"{path.name}: {error}")
    if not isinstance(parsed, dict):
        _fail("payload-shape", f"{path.name} is not an object")
    _check_json_value(parsed)
    if _canonical_json(parsed) != raw:
        _fail("canonical-json", f"{path.name} is not canonical")
    return cast(MutableJsonObject, parsed), raw


def _object(value: object, code: str, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(code, f"{label} is not an object")
    return cast(dict[str, Any], value)


def _list(value: object, code: str, label: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(code, f"{label} is not a list")
    return value


def _safe_package_files(root: Path) -> dict[str, Path]:
    try:
        root_mode = root.lstat().st_mode
    except OSError as error:
        _fail("package-root", str(error))
    if root.is_symlink() or not stat.S_ISDIR(root_mode):
        _fail("package-root", "package root is not a plain directory")
    files: dict[str, Path] = {}
    try:
        entries = tuple(root.iterdir())
    except OSError as error:
        _fail("package-read", str(error))
    for path in entries:
        try:
            mode = path.lstat().st_mode
        except OSError as error:
            _fail("package-read", str(error))
        if path.is_symlink() or not stat.S_ISREG(mode):
            _fail("unsafe-package-entry", path.name)
        files[path.name] = path
    if set(files) != set(REFERENCE_PACKAGE_FILE_NAMES):
        _fail("package-inventory", "root file inventory differs")
    return files


def _validate_manifest(manifest: MutableJsonObject) -> None:
    if set(manifest) != _MANIFEST_KEYS:
        _fail("manifest-shape", "top-level fields differ")
    versions = _object(manifest["versions"], "version-drift", "versions")
    if versions != _EXPECTED_VERSIONS:
        _fail("version-drift", "manifest or payload version differs")
    compatibility = _object(manifest["compatibility"], "compatibility-policy", "compatibility")
    if compatibility != _EXPECTED_COMPATIBILITY:
        _fail("compatibility-policy", "compatibility policy differs")
    visibility = _object(manifest["visibility"], "visibility-policy", "visibility")
    if visibility != _EXPECTED_VISIBILITY:
        _fail("visibility-policy", "visibility inventory differs")

    authority = _object(manifest["authority"], "manifest-authority", "authority")
    if (
        authority.get("profile_id") != _PROFILE_ID
        or authority.get("manifest_specification_id") != _MANIFEST_SPECIFICATION_ID
    ):
        _fail("manifest-authority", "profile or manifest authority differs")
    generation = _object(manifest["generation"], "generation-drift", "generation")
    if (
        generation.get("reference_world_generation_id") != _GENERATION_ID
        or generation.get("runtime_member_id") != _MEMBER_CONTENT_ID
        or {key: generation.get(key) for key in ("v0", "v1", "v2", "v3", "v4")}
        != {"v0": "pass", "v1": "pass", "v2": "pass", "v3": "pass", "v4": "unclaimed"}
    ):
        _fail("generation-drift", "generation authority differs")

    fields = _list(manifest["fields"], "rights-policy", "fields")
    if len(fields) != 340:
        _fail("rights-policy", "field inventory differs")
    for index, field_value in enumerate(fields):
        field = _object(field_value, "rights-policy", f"fields[{index}]")
        role = field.get("semantic_role")
        expectation = _ROLE_EXPECTATIONS.get(role) if isinstance(role, str) else None
        if (
            expectation is None
            or field.get("rights_decision_id") != _RIGHTS_DECISION_ID
            or field.get("visibility_class") != expectation["visibility_class"]
        ):
            _fail("rights-policy", f"field {index} differs")

    package = _object(manifest["package"], "manifest-package", "package")
    if (
        package.get("root_file_count") != 4
        or package.get("external_dependencies") != []
        or package.get("package_content_id") != EXPECTED_PACKAGE_CONTENT_ID
    ):
        _fail("manifest-package", "package authority differs")


def _validate_payload_inventory(
    manifest: MutableJsonObject,
    raw_payloads: dict[str, bytes],
) -> None:
    authority = _object(manifest["authority"], "manifest-authority", "authority")
    rights_review_content_id = authority.get("rights_review_content_id")
    package = _object(manifest["package"], "manifest-package", "package")
    payloads = _list(package.get("payloads"), "manifest-package", "package payloads")
    if len(payloads) != 3:
        _fail("manifest-package", "payload inventory differs")
    expected_roles = tuple(_ROLE_EXPECTATIONS)
    actual_roles: list[str] = []
    for index, row_value in enumerate(payloads):
        row = _object(row_value, "manifest-package", f"payloads[{index}]")
        role = row.get("semantic_role")
        if not isinstance(role, str) or role not in _ROLE_EXPECTATIONS:
            _fail("manifest-package", f"payload role {index} differs")
        actual_roles.append(role)
        expected = _ROLE_EXPECTATIONS[role]
        path = expected["relative_path"]
        raw = raw_payloads[path]
        size, raw_sha256 = _EXPECTED_FILE_IDENTITIES[path]
        if row.get("visibility_class") != expected["visibility_class"]:
            _fail("visibility-policy", f"{role} visibility differs")
        if row.get("rights_review_content_id") != rights_review_content_id:
            _fail("rights-policy", f"{role} rights review differs")
        payload_content_id = hashlib.sha256(_PAYLOAD_DOMAIN + role.encode("ascii") + b"\0" + raw).hexdigest()
        if (
            row.get("relative_path") != path
            or row.get("schema_identity") != expected["schema_identity"]
            or row.get("media_type") != "application/json"
            or row.get("size_bytes") != size
            or row.get("sha256") != raw_sha256
            or row.get("payload_content_id") != payload_content_id
        ):
            _fail("payload-drift", f"{role} identity differs")
    if tuple(actual_roles) != expected_roles:
        _fail("manifest-package", "payload order differs")
    package_content_id = hashlib.sha256(_PACKAGE_DOMAIN + _canonical_json(payloads)).hexdigest()
    if package_content_id != EXPECTED_PACKAGE_CONTENT_ID:
        _fail("package-identity", "computed package identity differs")


def _validate_payloads(
    manifest: MutableJsonObject,
    member: MutableJsonObject,
    checks: MutableJsonObject,
    profile: MutableJsonObject,
) -> None:
    payloads = {
        "physical-member": member,
        "physical-reference-checks": checks,
        "public-profile": profile,
    }
    for role, payload in payloads.items():
        if set(payload) != _PAYLOAD_KEYS[role]:
            _fail("payload-shape", f"{role} top-level fields differ")
        if (
            payload.get("profile_id") != _PROFILE_ID
            or payload.get("schema_id") != _ROLE_EXPECTATIONS[role]["schema_identity"]
        ):
            _fail("payload-schema", f"{role} schema or profile differs")
    generation = _object(manifest["generation"], "generation-drift", "generation")
    authority = _object(manifest["authority"], "manifest-authority", "authority")
    if (
        member.get("member_content_id") != _MEMBER_CONTENT_ID
        or checks.get("member_content_id") != _MEMBER_CONTENT_ID
        or checks.get("generation_id") != _GENERATION_ID
        or profile.get("generation_id") != _GENERATION_ID
        or generation.get("runtime_member_id") != member.get("member_content_id")
        or profile.get("asset") != member.get("asset")
        or profile.get("manifest_specification_id") != authority.get("manifest_specification_id")
    ):
        _fail("identity-link", "cross-file identity differs")
    check_rows = _list(checks.get("checks"), "payload-shape", "physical reference checks")
    if len(check_rows) != 9:
        _fail("payload-shape", "physical reference-check count differs")
    claims = _object(manifest["claims"], "claim-policy", "claims")
    if (
        profile.get("permitted_claim_ids") != claims.get("permitted")
        or profile.get("prohibited_claim_ids") != claims.get("prohibited")
        or profile.get("claim_ceiling") != "construct-valid-synthetic-benchmark"
    ):
        _fail("claim-policy", "public claim boundary differs")
    license_value = _object(profile.get("license"), "rights-policy", "license")
    if license_value.get("identifier") != "MIT":
        _fail("rights-policy", "public license differs")


def _validate_exact_file_identities(raw_files: dict[str, bytes]) -> None:
    for name, raw in raw_files.items():
        size, expected_sha256 = _EXPECTED_FILE_IDENTITIES[name]
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != expected_sha256:
            _fail("file-content-drift", name)
    manifest_raw = raw_files["promotion-manifest.json"]
    manifest_content_id = hashlib.sha256(_MANIFEST_DOMAIN + manifest_raw).hexdigest()
    if manifest_content_id != EXPECTED_MANIFEST_CONTENT_ID:
        _fail("manifest-identity", "manifest content identity differs")


def load_reference_package(
    package_root: Path | None = None,
    *,
    profile_id: str = REFERENCE_PROFILE_V1,
) -> ReferencePackage:
    """Load one exact certified registered package or fail closed on any drift."""
    if profile_id == REFERENCE_PROFILE_V2:
        from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader_v2 import (
            load_v2_reference_package,
        )

        return load_v2_reference_package(
            package_root
            if package_root is not None
            else bundled_reference_package_root(profile_id=REFERENCE_PROFILE_V2)
        )
    if profile_id != REFERENCE_PROFILE_V1:
        _fail("unknown-reference-profile", profile_id)
    root = package_root if package_root is not None else bundled_reference_package_root()
    files = _safe_package_files(Path(root))
    documents: dict[str, MutableJsonObject] = {}
    raw_files: dict[str, bytes] = {}
    for name in REFERENCE_PACKAGE_FILE_NAMES:
        document, raw = _read_object(files[name])
        documents[name] = document
        raw_files[name] = raw

    manifest = documents["promotion-manifest.json"]
    member = documents["physical-member.json"]
    checks = documents["physical-reference-checks.json"]
    profile = documents["public-profile.json"]
    _validate_manifest(manifest)
    _validate_payloads(manifest, member, checks, profile)
    _validate_payload_inventory(
        manifest,
        {name: raw for name, raw in raw_files.items() if name != "promotion-manifest.json"},
    )
    _validate_exact_file_identities(raw_files)
    return ReferencePackage.from_documents(
        profile_id=_PROFILE_ID,
        generation_id=_GENERATION_ID,
        package_content_id=EXPECTED_PACKAGE_CONTENT_ID,
        manifest_content_id=EXPECTED_MANIFEST_CONTENT_ID,
        manifest=manifest,
        physical_member=member,
        physical_reference_checks=checks,
        public_profile=profile,
    )
