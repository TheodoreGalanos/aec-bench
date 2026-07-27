# ABOUTME: Preserves the public Harbor import API over the generic extension-based implementation.
# ABOUTME: Lazily resolves proposal-only compatibility symbols so ordinary imports stay policy-neutral.

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from aec_bench.harness.harbor_importing.contracts import (
    HarborImportError,
)
from aec_bench.harness.harbor_importing.core import (
    import_harbor_job,
    import_harbor_trial,
    iter_harbor_trial_dirs,
)

if TYPE_CHECKING:
    from aec_bench.harness.harbor_importing.proposal import (
        ProposalHarborImportEvidence,
    )


def load_proposal_harbor_import_evidence(
    *,
    trial_dir: Path,
    repo_root: Path,
) -> ProposalHarborImportEvidence | None:
    """Load proposal-only completed evidence through its extension."""

    from aec_bench.harness.harbor_importing.proposal import (
        load_proposal_harbor_import_evidence as load_evidence,
    )

    return load_evidence(
        trial_dir=trial_dir,
        repo_root=repo_root,
    )


def load_proposal_harbor_candidate_failure_evidence(
    *,
    trial_dir: Path,
    repo_root: Path,
) -> ProposalHarborImportEvidence | None:
    """Load proposal-only candidate-failure evidence through its extension."""

    from aec_bench.harness.harbor_importing.proposal import (
        load_proposal_harbor_candidate_failure_evidence as load_evidence,
    )

    return load_evidence(
        trial_dir=trial_dir,
        repo_root=repo_root,
    )


def __getattr__(name: str) -> Any:
    if name == "ProposalHarborImportEvidence":
        from aec_bench.harness.harbor_importing.proposal import (
            ProposalHarborImportEvidence,
        )

        globals()[name] = ProposalHarborImportEvidence
        return ProposalHarborImportEvidence
    raise AttributeError(name)


__all__ = (
    "HarborImportError",
    "ProposalHarborImportEvidence",
    "import_harbor_job",
    "import_harbor_trial",
    "iter_harbor_trial_dirs",
    "load_proposal_harbor_candidate_failure_evidence",
    "load_proposal_harbor_import_evidence",
)
