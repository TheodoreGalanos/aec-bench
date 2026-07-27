# ABOUTME: Defines host-owned validation profiles for executable program compilation.
# ABOUTME: Keeps profile policy independent from operation validation and orchestration modules.

from enum import StrEnum


class ProgramCompilationProfile(StrEnum):
    """Closed host-owned validation profile for one execution-program shape."""

    STANDARD = "standard"
    MONOLITHIC_INCUMBENT = "monolithic_incumbent"
