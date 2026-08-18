# ABOUTME: Reports reference-aware dataset materialisation integrity without per-task manifest hashes.
# ABOUTME: Separates verified, missing, modified, and unexpected task material.

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntegrityResult:
    """Result of comparing an immutable dataset reference with materialised task bytes."""

    verified: int = 0
    missing: tuple[str, ...] = ()
    modified: tuple[str, ...] = ()
    unexpected: tuple[str, ...] = ()

    @property
    def is_clean(self) -> bool:
        return not self.missing and not self.modified and not self.unexpected


__all__ = ("IntegrityResult",)
