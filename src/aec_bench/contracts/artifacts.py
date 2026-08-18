# ABOUTME: Defines the universal exact-byte reference returned by artifact stores.
# ABOUTME: Keeps byte identity separate from domain identity and source provenance.

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, PositiveInt

from aec_bench.contracts.harness_kernel import validate_sha256
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr

Sha256 = Annotated[str, AfterValidator(validate_sha256)]


class ArtifactRef(FrozenStrictModel):
    """Stable repository reference to independently retained exact bytes."""

    artifact_id: NonEmptyStr
    sha256: Sha256
    size_bytes: PositiveInt
    media_type: NonEmptyStr

    @property
    def path(self) -> str:
        """Return the repository locator for path-oriented consumers."""

        return self.artifact_id


__all__ = ("ArtifactRef", "Sha256")
