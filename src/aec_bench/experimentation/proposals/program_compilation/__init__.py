# ABOUTME: Exposes the stable public API for governed proposal compilation.
# ABOUTME: Reexports each symbol from its single cohesive implementation module.

from .compilation import compile_governed_proposal
from .contracts import ProposalRunSessionBundle
from .errors import ProposalCompilationHostError
from .profile import proposal_execution_profile

__all__ = (
    "ProposalCompilationHostError",
    "ProposalRunSessionBundle",
    "compile_governed_proposal",
    "proposal_execution_profile",
)
