# ABOUTME: Provides deterministic uniqueness helpers for proposal-execution contracts.
# ABOUTME: Preserves canonical ordering and exact validation errors across the package.

from typing import TypeVar

_ModelT = TypeVar("_ModelT")


def canonical_unique_strings(
    value: tuple[str, ...],
    *,
    label: str,
) -> tuple[str, ...]:
    if len(value) != len(set(value)):
        raise ValueError(f"{label} must be unique")
    return tuple(sorted(value))


def canonical_unique_models(
    value: tuple[_ModelT, ...],
    *,
    identity: str,
    label: str,
) -> tuple[_ModelT, ...]:
    identities = [getattr(item, identity) for item in value]
    if len(identities) != len(set(identities)):
        raise ValueError(f"{label} must be unique by {identity}")
    return tuple(sorted(value, key=lambda item: getattr(item, identity)))
