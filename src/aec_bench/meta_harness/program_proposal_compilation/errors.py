# ABOUTME: Defines host-owned and candidate-owned proposal-compilation failures.
# ABOUTME: Preserves the error boundary that prevents host faults becoming candidate utility.

from aec_bench.contracts.proposal_execution_types import ProposalCompileRejectionCode


class ProposalCompilationHostError(RuntimeError):
    """Host-owned failure that must not be converted into candidate utility."""


class _CandidateCompileError(ValueError):
    def __init__(
        self,
        code: ProposalCompileRejectionCode,
        message: str,
        *,
        subject_ids: tuple[str, ...] = (),
    ) -> None:
        self.code = code
        self.subject_ids = tuple(sorted(set(subject_ids)))
        super().__init__(message)
