# ABOUTME: Characterizes the stable motif-library facade across its cohesive canonical package.
# ABOUTME: Guards public symbol identity under either facade-first or canonical-first imports.

from __future__ import annotations

import importlib
import subprocess
import sys


def test_motif_library_facade_reexports_canonical_symbols_by_identity() -> None:
    facade = importlib.import_module("aec_bench.meta_harness.motif_library")
    canonical = importlib.import_module("aec_bench.meta_harness.motifs")
    contracts = importlib.import_module("aec_bench.meta_harness.motifs.contracts")
    promotion = importlib.import_module("aec_bench.meta_harness.motifs.promotion")
    store = importlib.import_module("aec_bench.meta_harness.motifs.store")
    selection = importlib.import_module("aec_bench.meta_harness.motifs.selection")

    expected = {
        "MotifStatus": contracts.MotifStatus,
        "MotifTemplate": contracts.MotifTemplate,
        "MotifApplicabilityDescriptor": contracts.MotifApplicabilityDescriptor,
        "MotifStructuralDescriptor": contracts.MotifStructuralDescriptor,
        "PairedRepairEvidenceReference": contracts.PairedRepairEvidenceReference,
        "FactorialEvidenceReference": contracts.FactorialEvidenceReference,
        "QualityEvidenceReference": contracts.QualityEvidenceReference,
        "TransferEvidenceReference": contracts.TransferEvidenceReference,
        "HarnessProgramMotif": contracts.HarnessProgramMotif,
        "MotifPromotionPolicy": promotion.MotifPromotionPolicy,
        "MotifPromotionDecision": promotion.MotifPromotionDecision,
        "decide_motif_promotion": promotion.decide_motif_promotion,
        "apply_motif_promotion": promotion.apply_motif_promotion,
        "apply_motif_promotion_v1_compatibility": promotion.apply_motif_promotion_v1_compatibility,
        "MotifLibrary": store.MotifLibrary,
        "MotifLibraryArtifact": store.MotifLibraryArtifact,
        "write_motif_library_artifact": store.write_motif_library_artifact,
        "load_pinned_motif_library": store.load_pinned_motif_library,
        "MotifSelectionOutcome": selection.MotifSelectionOutcome,
        "MotifSelectionReason": selection.MotifSelectionReason,
        "MotifSelectionRequest": selection.MotifSelectionRequest,
        "MotifSelectionDecision": selection.MotifSelectionDecision,
        "select_motif": selection.select_motif,
        "resolve_motif_selection": selection.resolve_motif_selection,
    }
    for name, implementation in expected.items():
        assert getattr(facade, name) is implementation
        assert getattr(canonical, name) is implementation


def test_motif_library_facade_is_stable_under_both_import_orders() -> None:
    programs = (
        """
import aec_bench.meta_harness.motif_library as facade
import aec_bench.meta_harness.motifs as canonical
assert facade.HarnessProgramMotif is canonical.HarnessProgramMotif
assert facade.MotifLibrary is canonical.MotifLibrary
assert facade.decide_motif_promotion is canonical.decide_motif_promotion
assert facade.select_motif is canonical.select_motif
""",
        """
import aec_bench.meta_harness.motifs as canonical
import aec_bench.meta_harness.motif_library as facade
assert facade.HarnessProgramMotif is canonical.HarnessProgramMotif
assert facade.MotifLibrary is canonical.MotifLibrary
assert facade.decide_motif_promotion is canonical.decide_motif_promotion
assert facade.select_motif is canonical.select_motif
""",
    )

    for program in programs:
        subprocess.run([sys.executable, "-c", program], check=True)
