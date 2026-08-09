# ABOUTME: Defines the canonical public API for content-addressed harness/program motifs.
# ABOUTME: Keeps contracts, promotion, persistence, and selection cohesive behind one package.

from aec_bench.experimentation.governance.motifs.contracts import (
    BranchingCharacteristic,
    EvidenceSplit,
    FanoutCharacteristic,
    HarnessProgramEvidenceReference,
    HarnessProgramMotif,
    MotifApplicabilityDescriptor,
    MotifStatus,
    MotifStructuralDescriptor,
    MotifTemplate,
    NonNegativeFiniteFloat,
    PairedRepairEvidenceReference,
    QualityEvidenceReference,
    StateMode,
    TemplateKind,
    TransferEvidenceReference,
    UnitFloat,
)
from aec_bench.experimentation.governance.motifs.promotion import (
    MotifPromotionDecision,
    MotifPromotionPolicy,
    apply_motif_promotion,
    decide_motif_promotion,
)
from aec_bench.experimentation.governance.motifs.selection import (
    MotifSelectionDecision,
    MotifSelectionOutcome,
    MotifSelectionReason,
    MotifSelectionRequest,
    resolve_motif_selection,
    select_motif,
)
from aec_bench.experimentation.governance.motifs.store import (
    MotifLibrary,
    MotifLibraryArtifact,
    load_pinned_motif_library,
    write_motif_library_artifact,
)

__all__ = [
    "BranchingCharacteristic",
    "EvidenceSplit",
    "HarnessProgramEvidenceReference",
    "FanoutCharacteristic",
    "HarnessProgramMotif",
    "MotifApplicabilityDescriptor",
    "MotifLibrary",
    "MotifLibraryArtifact",
    "MotifPromotionDecision",
    "MotifPromotionPolicy",
    "MotifSelectionDecision",
    "MotifSelectionOutcome",
    "MotifSelectionReason",
    "MotifSelectionRequest",
    "MotifStatus",
    "MotifStructuralDescriptor",
    "MotifTemplate",
    "NonNegativeFiniteFloat",
    "PairedRepairEvidenceReference",
    "QualityEvidenceReference",
    "StateMode",
    "TemplateKind",
    "TransferEvidenceReference",
    "UnitFloat",
    "apply_motif_promotion",
    "decide_motif_promotion",
    "load_pinned_motif_library",
    "resolve_motif_selection",
    "select_motif",
    "write_motif_library_artifact",
]
