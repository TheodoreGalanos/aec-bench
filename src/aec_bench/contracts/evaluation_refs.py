# ABOUTME: Defines public references to published evaluation regimes and their critics.
# ABOUTME: Makes one exact regime artifact the only evaluation compatibility identity.

from __future__ import annotations

from enum import StrEnum

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr


class CriticRole(StrEnum):
    """Independent roles in one evaluation regime."""

    DEVELOPMENT = "development"
    ACCEPTANCE = "acceptance"
    RED_TEAM = "red_team"


class EvaluationRegimeRef(FrozenStrictModel):
    """Domain identity plus the exact published bytes of one evaluation regime."""

    regime_id: NonEmptyStr
    artifact: ArtifactRef

    @property
    def authority_identity(self) -> EvaluationRegimeRef:
        """Use this exact artifact reference at authority boundaries."""

        return self


class CriticRef(FrozenStrictModel):
    """One stable critic ID resolved within one exact evaluation regime."""

    regime: EvaluationRegimeRef
    critic_id: NonEmptyStr
    role: CriticRole

    @property
    def authority_identity(self) -> CriticRef:
        """Use this exact regime-scoped reference at authority boundaries."""

        return self


__all__ = ("CriticRef", "CriticRole", "EvaluationRegimeRef")
