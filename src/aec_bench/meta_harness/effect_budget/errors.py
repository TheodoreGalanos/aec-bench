# ABOUTME: Defines phase-neutral failures for durable reserve-before-effect accounting.
# ABOUTME: Lets shared durable machinery distinguish confinement, integrity, and capacity failures.


class EffectBudgetError(RuntimeError):
    """Base error for durable reserve-before-effect accounting."""


class EffectBudgetConfinementError(EffectBudgetError):
    """Raised when effect-budget evidence escapes its host-owned root."""


class EffectBudgetCollisionError(EffectBudgetError):
    """Raised when immutable budget identity is reused with different bytes."""


class EffectBudgetIntegrityError(EffectBudgetError):
    """Raised when persisted or supplied budget evidence is inconsistent."""


class EffectBudgetIncompleteError(EffectBudgetError):
    """Raised when a started effect has no terminal evidence."""


class EffectBudgetExceededError(EffectBudgetError):
    """Raised when reserved or observed effects cross a frozen ceiling."""
