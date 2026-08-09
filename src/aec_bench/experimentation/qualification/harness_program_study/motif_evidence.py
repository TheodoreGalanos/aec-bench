# ABOUTME: Derives motif-library evidence and learned Hx/px subjects from verified harness-program reports.
# ABOUTME: Keeps candidate-search evidence separate from promotion while forbidding holdout-derived selection.

from __future__ import annotations

from aec_bench.experimentation.governance.motifs import HarnessProgramEvidenceReference
from aec_bench.experimentation.qualification.motif_materialization import (
    encode_harness_motif_template,
    encode_program_motif_template,
)

from .contracts import HarnessProgramStudyReport
from .verification import verify_harness_program_study_report


def harness_program_study_evidence(report: HarnessProgramStudyReport) -> HarnessProgramEvidenceReference:
    """Convert completed discovery/calibration evidence without promoting motifs or accessing holdouts."""
    verify_harness_program_study_report(report)
    if report.split not in {"discovery", "calibration"}:
        raise ValueError("motif harness-program evidence may only come from discovery or calibration")
    if not report.cost_evidence_complete:
        raise ValueError("motif harness-program evidence requires complete cost evidence")
    subject_hx_template_sha256, subject_px_template_sha256 = harness_program_study_learned_subject(report)
    return HarnessProgramEvidenceReference.create(
        analysis_sha256=report.analysis_sha256,
        subject_hx_template_sha256=subject_hx_template_sha256,
        subject_px_template_sha256=subject_px_template_sha256,
        review_lineage_ids=report.review_lineage_ids,
        split=report.split,
        harness_main_effect=report.analysis.harness_main_effect.estimate,
        program_main_effect=report.analysis.program_main_effect.estimate,
        interaction=report.analysis.interaction.estimate,
        joint_uplift=report.analysis.joint_uplift.estimate,
        joint_incremental_uplift=report.analysis.joint_incremental_uplift.estimate,
        joint_incremental_uplift_lower_bound=report.analysis.joint_incremental_uplift.interval.lower,
        validity_rate=report.validity_rate,
        estimated_cost_usd=float(report.estimated_cost_usd),
        holdout_accessed_during_selection=False,
    )


def harness_program_study_learned_subject(report: HarnessProgramStudyReport) -> tuple[str, str]:
    """Return the one exact learned Hx/px template pair evaluated by a verified report."""

    verify_harness_program_study_report(report)
    subjects = {
        (
            encode_harness_motif_template(candidate.request.learned_harness_recipe).template_sha256,
            encode_program_motif_template(candidate.request.learned_program).template_sha256,
        )
        for candidate in report.candidates
    }
    if len(subjects) != 1:
        raise ValueError("harness-program-study evidence mixes multiple learned Hx/px template subjects")
    return next(iter(subjects))
