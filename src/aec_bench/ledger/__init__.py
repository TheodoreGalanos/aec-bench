# ABOUTME: Ledger package for append-only trial record persistence in aec-bench.
# ABOUTME: The ledger remains the canonical storage boundary for experimental truth.

from aec_bench.ledger.index import (
    EVIDENCE_INDEX_SCHEMA_VERSION,
    EvidenceIndex,
    EvidenceIndexError,
    EvidenceIndexRebuildReport,
    EvidenceIndexRow,
    EvidenceIndexSchemaError,
)
from aec_bench.ledger.query import EvidenceQuery, EvidenceQueryError, EvidenceQueryPage
from aec_bench.ledger.verification import EvidenceVerificationReport, verify_evidence

__all__ = (
    "EVIDENCE_INDEX_SCHEMA_VERSION",
    "EvidenceIndex",
    "EvidenceIndexError",
    "EvidenceIndexRebuildReport",
    "EvidenceIndexRow",
    "EvidenceIndexSchemaError",
    "EvidenceQuery",
    "EvidenceQueryError",
    "EvidenceQueryPage",
    "EvidenceVerificationReport",
    "verify_evidence",
)
