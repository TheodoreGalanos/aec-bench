# ABOUTME: Provides deterministic uniqueness helpers shared by program-proposal contracts.
# ABOUTME: Preserves canonical ordering and exact validation errors across the proposal package.

from typing import Any


def canonical_unique_strings(
    value: tuple[str, ...],
    *,
    label: str,
) -> tuple[str, ...]:
    if len(value) != len(set(value)):
        raise ValueError(f"{label} must be unique")
    return tuple(sorted(value))


def canonical_unique_models(
    value: tuple[Any, ...],
    *,
    identity: str,
    label: str,
) -> tuple[Any, ...]:
    identities = [getattr(item, identity) for item in value]
    if len(identities) != len(set(identities)):
        raise ValueError(f"{label} must be unique by {identity}")
    return tuple(sorted(value, key=lambda item: getattr(item, identity)))
