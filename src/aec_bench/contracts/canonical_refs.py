# ABOUTME: Canonical reference contracts for output normalisation.
# ABOUTME: Declares project IDs, base names, document codes that should be matched verbatim.

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CanonicalRef:
    """A canonical reference value declared in task config.

    `value` is the authoritative form. Any near-match in the agent's
    output (within bounded edit distance) is normalised to this value.
    """

    name: str
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError(f"CanonicalRef {self.name!r} has empty value")


@dataclass(frozen=True)
class CanonicalRefSet:
    """An ordered collection of canonical references for a task."""

    refs: tuple[CanonicalRef, ...] = ()


def parse_canonical_refs(data: Mapping[str, Any]) -> CanonicalRefSet:
    """Parse a canonical_refs dict (typically from task.toml [canonical_refs]).

    Each key/value pair becomes a CanonicalRef. Values must be strings;
    non-string values are coerced via str() for safety.
    """
    refs = tuple(CanonicalRef(name=name, value=str(value)) for name, value in data.items())
    return CanonicalRefSet(refs=refs)
