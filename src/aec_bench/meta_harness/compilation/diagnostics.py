# ABOUTME: Defines stable compiler diagnostics and their deterministic failure boundary.
# ABOUTME: Keeps ownership, messages, and sorted subject identities consistent across compiler stages.

from enum import StrEnum
from typing import Never

from pydantic import field_validator

from aec_bench.contracts.harness_kernel import FrozenStrictModel
from aec_bench.contracts.validators import NonEmptyStr


class CompilationOwner(StrEnum):
    """Boundary responsible for a deterministic compile failure."""

    KERNEL = "kernel"
    HARNESS = "harness"
    PROGRAM = "program"
    WORLD = "world"
    RUNTIME = "runtime"


class CompilationDiagnostic(FrozenStrictModel):
    """Stable failure attribution used by verifier-guided repair."""

    owner: CompilationOwner
    code: NonEmptyStr
    message: NonEmptyStr
    subject_ids: tuple[NonEmptyStr, ...] = ()

    @field_validator("subject_ids")
    @classmethod
    def validate_subject_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if tuple(sorted(set(value))) != value:
            raise ValueError("compile diagnostic subject ids must be sorted and unique")
        return value


class CompilationError(ValueError):
    """Raised with a typed diagnostic when deterministic compilation fails."""

    def __init__(self, diagnostic: CompilationDiagnostic) -> None:
        self.diagnostic = diagnostic
        super().__init__(diagnostic.message)


def _fail(
    *,
    owner: CompilationOwner,
    code: str,
    message: str,
    subject_ids: tuple[str, ...] = (),
) -> Never:
    raise CompilationError(
        CompilationDiagnostic(
            owner=owner,
            code=code,
            message=message,
            subject_ids=tuple(sorted(set(subject_ids))),
        )
    )
