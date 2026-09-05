# ABOUTME: Runs local engineering-decision qualification across hydraulic, dam, and pump owners.
# ABOUTME: Publishes reproducible control evidence without model providers, weight training, or promotion claims.

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from aec_bench.experimentation.engineering_decisions.dam_investigation import run_dam_experiment
from aec_bench.experimentation.engineering_decisions.definitions import (
    HydraulicExperiment,
    ProjectPartition,
    VerifierExperiment,
)
from aec_bench.experimentation.engineering_decisions.hydraulic_counterfactual import (
    run_hydraulic_experiment,
    run_verifier_experiment,
)
from aec_bench.experimentation.engineering_decisions.pump_continuation import run_pump_experiment
from aec_bench.experimentation.engineering_decisions.records import diagnostics
from aec_bench.lifecycles.stormwater_design.hydraulics.lineages import HydraulicLineage


def qualify_engineering_decisions(output: Path, seeds: tuple[int, ...] = (2, 8, 12)) -> dict[str, Any]:
    """Run complete deterministic controls in new private local output storage."""
    if not seeds or len(seeds) != len(set(seeds)):
        raise ValueError("provide distinct, non-empty project seeds")
    lineages = [HydraulicLineage(seed=seed) for seed in seeds]
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("qualification output must be empty")
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    definition = (
        HydraulicExperiment()
        if seeds == (2, 8, 12)
        else HydraulicExperiment(partitions=(ProjectPartition(split="development", seeds=seeds),))
    )
    hydraulic_records = run_hydraulic_experiment(output / "hydraulic", definition)
    challenge_records = run_verifier_experiment(output / "challenges", VerifierExperiment(seed=seeds[0]))
    dam_records = run_dam_experiment(output / "dam")
    pump_records = run_pump_experiment(output / "pump")
    hydraulic = [diagnostics(record) for record in hydraulic_records]
    challenges = [diagnostics(record) for record in challenge_records]
    dam = [diagnostics(record) for record in dam_records if record.agent.model == "evidence_first"]
    unsupported = next(
        diagnostics(record)
        for record in dam_records
        if record.agent.model == "unsupported" and record.task_id.endswith("/investigation-fault")
    )
    late = next(
        diagnostics(record)
        for record in dam_records
        if record.agent.model == "late" and record.task_id.endswith("/investigation-urgent-fault")
    )
    pump = next(
        diagnostics(record) for record in pump_records if not record.agent.configuration["omit_verification_work"]
    )
    omitted = next(
        diagnostics(record) for record in pump_records if record.agent.configuration["omit_verification_work"]
    )
    good_liability = pump["evaluation"]["metrics"]["terminal_liability"]
    bad_liability = omitted["evaluation"]["metrics"]["terminal_liability"]
    checks = {
        "canonical_trial_evidence": all(
            record.evidence_status.value == "verified"
            for record in (*hydraulic_records, *challenge_records, *dam_records, *pump_records)
        ),
        "hydraulic_controls": all(r["expectation_met"] for r in hydraulic),
        "verifier_challenges": all(r["expectation_met"] for r in challenges),
        "distinct_projects": len({x.source().model_dump_json() for x in lineages}) == len(lineages),
        "causal_readiness_change": any(r["baseline_readiness"] != r["revision_readiness"] for r in hydraulic),
        "dam_sufficient_evidence": all(r["evaluation"]["successful"] and not r["rejections"] for r in dam),
        "dam_unsupported_response_rejected": unsupported["evaluation"]["response_correct"]
        and not unsupported["evaluation"]["successful"],
        "dam_delay_detected": late["evaluation"]["evidence_complete"] and not late["evaluation"]["response_timely"],
        "pump_matched_conditions": pump["opening_state_id"] == omitted["opening_state_id"]
        and pump["immediate_service"] == omitted["immediate_service"]
        and pump["horizon_seconds"] == omitted["horizon_seconds"],
        "pump_replay": pump["replay_valid"] and omitted["replay_valid"],
        "pump_handover_contrast": pump["handover_complete"] and not omitted["handover_complete"],
        "pump_delayed_liability": bad_liability["overdue_calendar_seconds"]
        > good_liability["overdue_calendar_seconds"],
    }
    module_path = Path(__file__).resolve()
    source_root = module_path.parents[2]
    owned_paths = [
        module_path,
        *source_root.joinpath("experimentation/engineering_decisions").glob("*.py"),
        *source_root.joinpath("lifecycles/stormwater_design").rglob("*.py"),
        *source_root.joinpath("worlds/monitoring/dam_seepage").glob("*.py"),
        *source_root.joinpath("worlds/monitoring/dam_seepage").glob("*.json"),
        source_root / "worlds/stewardship/wastewater_pump_station/handover.py",
    ]
    report = {
        "checks": checks,
        "passed": all(checks.values()),
        "scope": "local synthetic environment and verifier qualification; no model performance or training result",
        "seeds": list(seeds),
        "partitions": [p.model_dump(mode="json") for p in definition.partitions],
        "split_unit": "project_lineage",
        "acceptance_sealed": False,
        "source_sha256": {
            p.relative_to(source_root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(set(owned_paths))
        },
        "hydraulic": hydraulic,
        "verifier_challenges": challenges,
        "dam": {"evidence_first": dam, "unsupported": unsupported, "late": late},
        "pump": {"complete_handover": pump, "omitted_work": omitted},
    }
    (output / "qualification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Qualify engineering-decision experiments locally without model calls."
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="Empty private directory for generated packages and evidence"
    )
    parser.add_argument("--seeds", type=int, nargs="+", default=[2, 8, 12], help="Distinct synthetic project seeds")
    args = parser.parse_args()
    report = qualify_engineering_decisions(args.output, tuple(args.seeds))
    print(
        json.dumps(
            {"passed": report["passed"], "checks": report["checks"], "report": str(args.output / "qualification.json")}
        )
    )
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
