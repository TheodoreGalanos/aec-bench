# ABOUTME: Tests the phase-neutral factorial-experiment API and its persisted schema boundary.
# ABOUTME: Proves public imports resolve to one implementation without rewriting historical artifacts.

from __future__ import annotations

from aec_bench.meta_harness.factorial_experiment import (
    FactorialExperimentReport,
    FactorialExperimentSpec,
    load_factorial_experiment_report,
    run_factorial_experiment,
    verify_factorial_experiment_report,
)
from aec_bench.meta_harness.factorial_experiment.contracts import (
    FactorialExperimentReport as ContractsFactorialExperimentReport,
)
from aec_bench.meta_harness.factorial_experiment.motif_evidence import (
    factorial_experiment_evidence as motif_evidence_factorial_experiment_evidence,
)
from aec_bench.meta_harness.factorial_experiment.persistence import (
    load_factorial_experiment_report as persistence_load_factorial_experiment_report,
)
from aec_bench.meta_harness.factorial_experiment.runtime import (
    run_factorial_experiment as runtime_run_factorial_experiment,
)
from aec_bench.meta_harness.factorial_experiment.verification import (
    verify_factorial_experiment_report as verification_verify_factorial_experiment_report,
)


def test_historical_stage_zero_schema_identifiers_remain_stable() -> None:
    assert FactorialExperimentSpec.model_fields["schema_version"].default == "aecbench.meta-harness-stage-zero-spec.v2"
    assert (
        FactorialExperimentReport.model_fields["schema_version"].default == "aecbench.meta-harness-stage-zero-report.v2"
    )


def test_factorial_experiment_package_reexports_each_canonical_implementation() -> None:
    from aec_bench.meta_harness.factorial_experiment import factorial_experiment_evidence

    assert FactorialExperimentReport is ContractsFactorialExperimentReport
    assert run_factorial_experiment is runtime_run_factorial_experiment
    assert load_factorial_experiment_report is persistence_load_factorial_experiment_report
    assert verify_factorial_experiment_report is verification_verify_factorial_experiment_report
    assert factorial_experiment_evidence is motif_evidence_factorial_experiment_evidence
