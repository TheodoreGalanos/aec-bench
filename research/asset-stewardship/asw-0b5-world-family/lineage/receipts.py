# ABOUTME: Implements the research-only B5-W0 common receipt envelope and structural DAG validator.
# ABOUTME: Cannot promote, package, generate, certify hydraulics, or define production contracts.

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, NoReturn, cast

PROFILE_ID = "AU-NSW-LH-SYN-SPS-v1"
RECEIPT_VERSION = "asw-0b5.research-receipt.v1"

RECEIPT_KINDS = (
    "generation-declaration",
    "engine-build",
    "generator-case",
    "certifier-case",
    "w4-case",
    "sensitivity-member",
    "family-decision",
    "gate-decision",
    "rights-review",
    "visibility-review",
    "package-conformance",
    "absence-proof",
    "promotion-decision",
)

SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9.-]*\Z")
VISIBILITY_CLASSES = {
    "public",
    "actor-visible",
    "host-private",
    "certification-private",
    "holdout-sensitive",
}


class ReceiptBoundaryError(ValueError):
    """Fail-closed receipt envelope or graph rejection."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"lineage:{code}: {detail}")


@dataclass(frozen=True)
class IdentifiedReceipt:
    """A canonical envelope paired with its recomputed content identity."""

    receipt_id: str
    envelope: dict[str, Any]
    canonical_bytes: bytes


def _fail(code: str, detail: str) -> NoReturn:
    raise ReceiptBoundaryError(code, detail)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            _fail("receipt.duplicate-key", f"duplicate key {name!r}")
        result[name] = value
    return result


def _check_json_types(value: Any) -> None:
    if value is None or isinstance(value, float):
        _fail("receipt.json-type", "null and JSON floating-point numbers are forbidden")
    if isinstance(value, dict):
        for name, child in value.items():
            if not isinstance(name, str):
                _fail("receipt.key", "object key is not a string")
            _check_json_types(child)
    elif isinstance(value, list):
        for child in value:
            _check_json_types(child)
    elif not isinstance(value, str | int | bool):
        _fail("receipt.json-type", f"unsupported type {type(value).__name__}")


def _canonical_bytes(value: object) -> bytes:
    _check_json_types(value)
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"{encoded}\n".encode()


def _parse_canonical(raw: bytes) -> dict[str, Any]:
    if raw.startswith(b"\xef\xbb\xbf"):
        _fail("receipt.bom", "BOM is forbidden")
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n") or b"\r" in raw:
        _fail("receipt.newline", "exactly one terminal LF is required")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        _fail("receipt.utf8", str(error))
    try:
        value = json.loads(text, object_pairs_hook=_unique_object)
    except json.JSONDecodeError as error:
        _fail("receipt.json", str(error))
    _check_json_types(value)
    if not isinstance(value, dict):
        _fail("receipt.root", "receipt must be an object")
    envelope = cast(dict[str, Any], value)
    if _canonical_bytes(envelope) != raw:
        _fail("receipt.noncanonical", "receipt bytes are not canonical")
    return envelope


def _require_object(
    value: Any,
    expected_keys: set[str],
    code: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected_keys:
        _fail(code, f"expected keys {sorted(expected_keys)!r}")
    return cast(dict[str, Any], value)


def _require_sha256(value: Any, code: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        _fail(code, "expected lower-case SHA-256")
    return value


def _require_token(value: Any, code: str) -> str:
    if not isinstance(value, str) or TOKEN_PATTERN.fullmatch(value) is None:
        _fail(code, f"unsafe token {value!r}")
    return value


def receipt_id(kind: str, canonical_receipt_bytes: bytes) -> str:
    if kind not in RECEIPT_KINDS:
        _fail("receipt.kind", f"unknown receipt kind {kind!r}")
    return hashlib.sha256(
        b"asw-0b5.research-receipt.v1\0" + kind.encode("ascii") + b"\0" + canonical_receipt_bytes
    ).hexdigest()


def _validate_authorities(authorities: Any) -> None:
    if not isinstance(authorities, list) or not authorities:
        _fail("receipt.authorities", "at least one authority identity is required")
    seen_roles: set[str] = set()
    for value in authorities:
        authority = _require_object(
            value,
            {"role", "sha256"},
            "receipt.authority-shape",
        )
        role = _require_token(authority["role"], "receipt.authority-role")
        _require_sha256(authority["sha256"], "receipt.authority-id")
        if role in seen_roles:
            _fail("receipt.authority-duplicate", f"duplicate authority role {role}")
        seen_roles.add(role)


def _validate_content_inventory(inventory: Any, field: str) -> None:
    if not isinstance(inventory, list):
        _fail(f"receipt.{field}", f"{field} must be an array")
    for value in inventory:
        item = _require_object(
            value,
            {"content_id", "role"},
            f"receipt.{field}-shape",
        )
        _require_sha256(item["content_id"], f"receipt.{field}-id")
        _require_token(item["role"], f"receipt.{field}-role")


def read_receipt(raw: bytes) -> IdentifiedReceipt:
    envelope = _parse_canonical(raw)
    _require_object(
        envelope,
        {
            "authorities",
            "first_failure",
            "generation_id",
            "inputs",
            "outputs",
            "parent_receipt_ids",
            "profile_id",
            "promotable",
            "receipt_kind",
            "receipt_version",
            "terminal_state",
            "visibility",
        },
        "receipt.shape",
    )
    kind = envelope["receipt_kind"]
    if not isinstance(kind, str) or kind not in RECEIPT_KINDS:
        _fail("receipt.kind", f"unknown receipt kind {kind!r}")
    if envelope["receipt_version"] != RECEIPT_VERSION:
        _fail("receipt.version", "receipt version mismatch")
    if not isinstance(envelope["profile_id"], str) or not envelope["profile_id"]:
        _fail("receipt.profile", "profile identity is required")
    _require_sha256(envelope["generation_id"], "receipt.generation")
    _validate_authorities(envelope["authorities"])

    parents = envelope["parent_receipt_ids"]
    if not isinstance(parents, list):
        _fail("receipt.parents", "parent identities must be an array")
    for parent_id in parents:
        _require_sha256(parent_id, "receipt.parent-id")
    _validate_content_inventory(envelope["inputs"], "inputs")
    _validate_content_inventory(envelope["outputs"], "outputs")

    first_failure = _require_object(
        envelope["first_failure"],
        {"code", "owner"},
        "receipt.first-failure-shape",
    )
    _require_token(first_failure["code"], "receipt.first-failure-code")
    _require_token(first_failure["owner"], "receipt.first-failure-owner")
    _require_token(envelope["terminal_state"], "receipt.terminal-state")
    if envelope["visibility"] not in VISIBILITY_CLASSES:
        _fail("receipt.visibility", "unknown visibility class")
    if type(envelope["promotable"]) is not bool:
        _fail("receipt.promotable", "promotable must be a boolean")
    if envelope["promotable"] and not (
        kind == "promotion-decision" and envelope["terminal_state"] == "promotion-issued"
    ):
        _fail("receipt.promotable", "only an issued promotion decision may be promotable")
    return IdentifiedReceipt(
        receipt_id=receipt_id(kind, raw),
        envelope=envelope,
        canonical_bytes=raw,
    )


def _detect_cycles(receipts_by_id: dict[str, IdentifiedReceipt]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(receipt_id_value: str) -> None:
        if receipt_id_value in visiting:
            _fail("graph.cycle", f"cycle includes {receipt_id_value}")
        if receipt_id_value in visited:
            return
        visiting.add(receipt_id_value)
        receipt = receipts_by_id[receipt_id_value]
        for parent_id in receipt.envelope["parent_receipt_ids"]:
            visit(parent_id)
        visiting.remove(receipt_id_value)
        visited.add(receipt_id_value)

    for node_id in receipts_by_id:
        visit(node_id)


def _terminates_at_root(
    node_id: str,
    receipts_by_id: dict[str, IdentifiedReceipt],
    root_id: str,
    memo: dict[str, bool],
) -> bool:
    if node_id == root_id:
        return True
    if node_id in memo:
        return memo[node_id]
    parents = receipts_by_id[node_id].envelope["parent_receipt_ids"]
    result = bool(parents) and all(
        _terminates_at_root(parent_id, receipts_by_id, root_id, memo) for parent_id in parents
    )
    memo[node_id] = result
    return result


def validate_receipt_graph(receipts: Sequence[IdentifiedReceipt]) -> None:
    if not receipts:
        _fail("graph.empty", "receipt graph is empty")
    receipts_by_id: dict[str, IdentifiedReceipt] = {}
    for receipt in receipts:
        if receipt.receipt_id in receipts_by_id:
            _fail("graph.duplicate-receipt", receipt.receipt_id)
        receipts_by_id[receipt.receipt_id] = receipt

    roots = [receipt for receipt in receipts if receipt.envelope["receipt_kind"] == "generation-declaration"]
    if len(roots) != 1 or roots[0].envelope["parent_receipt_ids"]:
        _fail("graph.root", "exactly one parentless generation declaration is required")
    root = roots[0]
    if root.envelope["profile_id"] != PROFILE_ID:
        _fail("graph.profile", "root profile does not match the B5 profile")

    for receipt in receipts:
        parents = receipt.envelope["parent_receipt_ids"]
        if len(parents) != len(set(parents)):
            _fail("graph.duplicate-parent", receipt.receipt_id)
        for parent_id in parents:
            if parent_id not in receipts_by_id:
                _fail("graph.missing-parent", parent_id)
        if receipt.envelope["profile_id"] != root.envelope["profile_id"]:
            _fail("graph.profile", receipt.receipt_id)
        if receipt.envelope["generation_id"] != root.envelope["generation_id"]:
            _fail("graph.generation", receipt.receipt_id)

    _detect_cycles(receipts_by_id)
    kind_index = {kind: index for index, kind in enumerate(RECEIPT_KINDS)}
    for receipt in receipts:
        child_index = kind_index[receipt.envelope["receipt_kind"]]
        for parent_id in receipt.envelope["parent_receipt_ids"]:
            parent = receipts_by_id[parent_id]
            if kind_index[parent.envelope["receipt_kind"]] >= child_index:
                _fail(
                    "graph.stage-order",
                    f"{parent.receipt_id} cannot parent {receipt.receipt_id}",
                )
    root_id = root.receipt_id
    memo: dict[str, bool] = {}
    for receipt in receipts:
        if not _terminates_at_root(receipt.receipt_id, receipts_by_id, root_id, memo):
            _fail("graph.root", f"{receipt.receipt_id} does not terminate at the root")
