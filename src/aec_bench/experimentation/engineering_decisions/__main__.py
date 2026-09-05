# ABOUTME: Runs one declared engineering decision experiment without model or provider calls.
# ABOUTME: Accepts a saved condition definition and publishes ordinary trial records and evidence.

import argparse
import json
from pathlib import Path

from aec_bench.experimentation.engineering_decisions.dam_investigation import run_dam_experiment
from aec_bench.experimentation.engineering_decisions.definitions import (
    DamExperiment,
    HydraulicExperiment,
    PumpExperiment,
    VerifierExperiment,
)
from aec_bench.experimentation.engineering_decisions.hydraulic_counterfactual import (
    run_hydraulic_experiment,
    run_verifier_experiment,
)
from aec_bench.experimentation.engineering_decisions.pump_continuation import run_pump_experiment


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a reproducible engineering decision control experiment.")
    parser.add_argument("experiment", choices=("hydraulic", "dam", "pump", "verifier"))
    parser.add_argument("--output", type=Path, required=True, help="Empty private output directory")
    parser.add_argument("--definition", type=Path, help="JSON condition definition, or a prior experiment.json")
    args = parser.parse_args()
    payload = json.loads(args.definition.read_text()) if args.definition else {}
    if isinstance(payload, dict) and "definition" in payload:
        payload = payload["definition"]
    if args.experiment == "hydraulic":
        records = run_hydraulic_experiment(args.output, HydraulicExperiment.model_validate(payload))
    elif args.experiment == "dam":
        records = run_dam_experiment(args.output, DamExperiment.model_validate(payload))
    elif args.experiment == "pump":
        records = run_pump_experiment(args.output, PumpExperiment.model_validate(payload))
    else:
        records = run_verifier_experiment(args.output, VerifierExperiment.model_validate(payload))
    print(json.dumps({"trials": len(records), "ledger": str(args.output / "ledger")}))


if __name__ == "__main__":
    main()
