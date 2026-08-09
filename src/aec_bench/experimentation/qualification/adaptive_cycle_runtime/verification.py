# ABOUTME: Loads and independently verifies complete adaptive-cycle evidence lineages.
# ABOUTME: Recomputes each terminal prefix in deterministic fail-closed diagnostic order.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.evolution.repair_lifecycle import RepairCandidate
from aec_bench.experimentation.governance.motifs import (
    MotifLibrary,
    load_pinned_motif_library,
)
from aec_bench.experimentation.qualification.adaptive_cycle_runtime.artifacts import (
    verify_artifact,
)
from aec_bench.experimentation.qualification.adaptive_cycle_runtime.contracts import (
    AdaptiveCycleReport,
    AdaptiveCycleSpec,
    AdaptiveCycleTerminalStage,
    repair_terminal_reason,
)
from aec_bench.experimentation.qualification.harness_program_study import (
    HarnessProgramStudyReport,
    load_harness_program_study_report,
)
from aec_bench.experimentation.qualification.motif_learning import (
    MotifLearningReport,
)
from aec_bench.experimentation.qualification.repair_runtime import RepairTerminalRecord


@dataclass(frozen=True)
class _CommonEvidence:
    input_library: MotifLibrary
    spec: AdaptiveCycleSpec
    source_stage: HarnessProgramStudyReport
    repair_terminal: RepairTerminalRecord
    final_library: MotifLibrary


@dataclass(frozen=True)
class _LearningEvidence:
    repaired_candidate: RepairCandidate
    child_stage: HarnessProgramStudyReport
    report: MotifLearningReport
    library: MotifLibrary


def load_adaptive_cycle_report(path: Path) -> AdaptiveCycleReport:
    """Load and revalidate every artifact and cross-stage identity in a report."""

    source_path = Path(path)
    try:
        report = AdaptiveCycleReport.model_validate_json(source_path.read_text(encoding="utf-8"))
    except Exception as error:
        raise ValueError(f"invalid adaptive cycle report: {source_path}") from error
    if source_path.parent.name != report.content_sha256:
        raise ValueError("adaptive cycle report path does not match its content identity")
    verify_adaptive_cycle_report(report)
    return report


def verify_adaptive_cycle_report(report: AdaptiveCycleReport) -> None:
    """Fail closed unless the report exactly binds all recomputed stage evidence."""

    validated = AdaptiveCycleReport.model_validate(report.model_dump(mode="python"))
    _verify_referenced_artifacts(validated)
    common = _load_common_evidence(validated)
    _verify_common_evidence(validated, common)

    if validated.terminal_stage is AdaptiveCycleTerminalStage.REPAIR:
        _verify_repair_stop(validated, common)
        return

    learning = _load_learning_evidence(validated)
    _verify_learning_evidence(validated, common, learning)
    _verify_motif_stop(validated, common, learning)


def _verify_referenced_artifacts(report: AdaptiveCycleReport) -> None:
    references = tuple(
        reference
        for reference in (
            report.input_motif_library.artifact,
            report.repaired_candidate,
            report.child_calibration_report,
            report.motif_learning_report,
            report.learning_motif_library,
            report.spec_artifact,
            report.source_stage_report,
            report.repair_terminal,
            report.motif_library,
        )
        if reference is not None
    )
    for reference in references:
        verify_artifact(reference)


def _load_common_evidence(report: AdaptiveCycleReport) -> _CommonEvidence:
    return _CommonEvidence(
        input_library=load_pinned_motif_library(report.input_motif_library),
        spec=AdaptiveCycleSpec.model_validate_json(Path(report.spec_artifact.path).read_text(encoding="utf-8")),
        source_stage=load_harness_program_study_report(Path(report.source_stage_report.path)),
        repair_terminal=RepairTerminalRecord.model_validate_json(
            Path(report.repair_terminal.path).read_text(encoding="utf-8")
        ),
        final_library=MotifLibrary.model_validate_json(Path(report.motif_library.path).read_text(encoding="utf-8")),
    )


def _verify_common_evidence(
    report: AdaptiveCycleReport,
    evidence: _CommonEvidence,
) -> None:
    if (
        evidence.spec.content_sha256 != report.spec_sha256
        or evidence.spec.source_stage.content_sha256 != evidence.source_stage.spec_sha256
    ):
        raise ValueError("adaptive cycle spec does not bind its source stage")
    if evidence.spec.input_motif_library != report.input_motif_library:
        raise ValueError("adaptive cycle report does not bind its pinned input archive")
    if evidence.source_stage.kernel_ref != report.kernel_ref:
        raise ValueError("adaptive cycle source stage does not use the reported fixed kernel")
    if evidence.final_library.archive_sha256 != report.final_archive_sha256:
        raise ValueError("adaptive cycle final library does not match its reported archive")


def _verify_repair_stop(
    report: AdaptiveCycleReport,
    evidence: _CommonEvidence,
) -> None:
    if repair_terminal_reason(evidence.repair_terminal.result.status) is not report.terminal_reason:
        raise ValueError("adaptive cycle repair terminal reason does not match its repair evidence")
    if evidence.final_library != evidence.input_library:
        raise ValueError("adaptive cycle repair stop changed its pinned motif library")


def _load_learning_evidence(
    report: AdaptiveCycleReport,
) -> _LearningEvidence:
    assert report.repaired_candidate is not None
    assert report.child_calibration_report is not None
    assert report.motif_learning_report is not None
    assert report.learning_motif_library is not None
    return _LearningEvidence(
        repaired_candidate=RepairCandidate.model_validate_json(
            Path(report.repaired_candidate.path).read_text(encoding="utf-8")
        ),
        child_stage=load_harness_program_study_report(Path(report.child_calibration_report.path)),
        report=MotifLearningReport.model_validate_json(
            Path(report.motif_learning_report.path).read_text(encoding="utf-8")
        ),
        library=MotifLibrary.model_validate_json(Path(report.learning_motif_library.path).read_text(encoding="utf-8")),
    )


def _verify_learning_evidence(
    report: AdaptiveCycleReport,
    common: _CommonEvidence,
    learning: _LearningEvidence,
) -> None:
    repair_decision = common.repair_terminal.result.decision
    if (
        repair_decision is None
        or common.repair_terminal.result.child_candidate_id != learning.repaired_candidate.candidate_id
    ):
        raise ValueError("adaptive cycle accepted repair terminal is missing its repaired child")
    if learning.child_stage.kernel_ref != report.kernel_ref:
        raise ValueError("adaptive cycle child stage does not use the reported fixed kernel")
    if (
        learning.report.source_stage_report_sha256 != common.source_stage.content_sha256
        or learning.report.child_calibration_report_sha256 != learning.child_stage.content_sha256
        or learning.report.repair_terminal != report.repair_terminal
        or learning.report.repair_terminal != learning.report.repair_evidence.terminal
        or learning.report.repair_evidence.decision_sha256
        != canonical_content_sha256(repair_decision.model_dump(mode="json"))
        or learning.report.input_archive_sha256 != common.input_library.archive_sha256
    ):
        raise ValueError("adaptive cycle motif learning lineage does not match its source evidence")
    if (
        learning.library.archive_sha256 != report.learning_archive_sha256
        or learning.library.archive_sha256 != learning.report.output_archive_sha256
        or learning.report.final_motif_sha256 != report.learned_motif_sha256
        or not any(motif.motif_sha256 == report.learned_motif_sha256 for motif in learning.library.motifs)
    ):
        raise ValueError("adaptive cycle learning archive does not match its learning report")


def _verify_motif_stop(
    report: AdaptiveCycleReport,
    common: _CommonEvidence,
    learning: _LearningEvidence,
) -> None:
    if common.final_library != learning.library:
        raise ValueError("adaptive cycle motif stop changed its learning archive")
    if (
        learning.report.final_status is not report.final_status
        or learning.report.final_motif_sha256 != report.final_motif_sha256
    ):
        raise ValueError("adaptive cycle motif stop does not match its promotion report")
