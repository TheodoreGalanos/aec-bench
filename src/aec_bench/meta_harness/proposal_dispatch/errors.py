# ABOUTME: Defines fail-closed errors for governed proposal dispatch authorization and replay.
# ABOUTME: Keeps one shared error identity across contracts, validation, authorization, and replay.


class ProposalDispatchGovernanceError(ValueError):
    """Reject an incomplete or identity-drifted proposal dispatch authority chain."""
