# ABOUTME: Defines bounded failures for Learning Study planning and execution.
# ABOUTME: Preserves study, arm, and step context without exposing task secrets.

from __future__ import annotations


class LearningStudyError(Exception):
    """Base error for one Learning Study boundary failure."""


class LearningStudySpecInvalid(LearningStudyError):
    pass


class LearningStudyReferenceInvalid(LearningStudyError):
    pass


class LearningStudyOrderInvalid(LearningStudyError):
    pass


class LearningStudyTaskResolutionFailed(LearningStudyError):
    pass


class LearningStudyPlanCollision(LearningStudyError):
    pass


class LearningStudyFeatureUnsupported(LearningStudyError):
    pass


class LearningStudyRuntimeError(LearningStudyError):
    pass


class LearningStudyPersistenceError(LearningStudyRuntimeError):
    pass


__all__ = (
    "LearningStudyError",
    "LearningStudyFeatureUnsupported",
    "LearningStudyOrderInvalid",
    "LearningStudyPlanCollision",
    "LearningStudyPersistenceError",
    "LearningStudyReferenceInvalid",
    "LearningStudyRuntimeError",
    "LearningStudySpecInvalid",
    "LearningStudyTaskResolutionFailed",
)
