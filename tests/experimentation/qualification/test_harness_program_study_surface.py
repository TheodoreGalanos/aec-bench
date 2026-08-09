# ABOUTME: Tests the qualification-owned harness-program-study API and its persisted schema boundary.
# ABOUTME: Proves public imports resolve to one direct implementation and one current schema.

from __future__ import annotations

from aec_bench.experimentation.qualification.harness_program_study import (
    HarnessProgramStudyReport,
    HarnessProgramStudySpec,
    load_harness_program_study_report,
    run_harness_program_study,
    verify_harness_program_study_report,
)
from aec_bench.experimentation.qualification.harness_program_study.contracts import (
    HarnessProgramStudyReport as ContractsHarnessProgramStudyReport,
)
from aec_bench.experimentation.qualification.harness_program_study.motif_evidence import (
    harness_program_study_evidence as motif_evidence_harness_program_study_evidence,
)
from aec_bench.experimentation.qualification.harness_program_study.persistence import (
    load_harness_program_study_report as persistence_load_harness_program_study_report,
)
from aec_bench.experimentation.qualification.harness_program_study.runtime import (
    run_harness_program_study as runtime_run_harness_program_study,
)
from aec_bench.experimentation.qualification.harness_program_study.verification import (
    verify_harness_program_study_report as verification_verify_harness_program_study_report,
)


def test_harness_program_study_schema_identifiers_match_current_contracts() -> None:
    assert HarnessProgramStudySpec.model_fields["schema_version"].default == "aecbench.harness-program-study-spec.v1"
    assert (
        HarnessProgramStudyReport.model_fields["schema_version"].default == "aecbench.harness-program-study-report.v1"
    )


def test_harness_program_study_package_reexports_each_canonical_implementation() -> None:
    from aec_bench.experimentation.qualification.harness_program_study import harness_program_study_evidence

    assert HarnessProgramStudyReport is ContractsHarnessProgramStudyReport
    assert run_harness_program_study is runtime_run_harness_program_study
    assert load_harness_program_study_report is persistence_load_harness_program_study_report
    assert verify_harness_program_study_report is verification_verify_harness_program_study_report
    assert harness_program_study_evidence is motif_evidence_harness_program_study_evidence
