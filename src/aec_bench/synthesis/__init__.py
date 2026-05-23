# ABOUTME: Adapter-agnostic synthesis domain — aggregates K candidate outputs into one.
# ABOUTME: Public surface is synthesise(); everything else is internal.

from aec_bench.synthesis.engine import (
    SynthesisBudgetError,
    synthesise,
)

__all__ = [
    "SynthesisBudgetError",
    "synthesise",
]
