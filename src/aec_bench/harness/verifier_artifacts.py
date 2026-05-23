# ABOUTME: Verifier artifact ingestion helpers for harness collection in aec-bench Python.
# ABOUTME: Converts reward and optional details artifacts into validated EvaluationResult objects.

import json
from pathlib import Path
from typing import Any, cast

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck


def read_verifier_artifacts(
    *,
    reward_path: Path | None,
    details_path: Path | None,
    output_parseable: bool,
    schema_valid: bool,
) -> EvaluationResult:
    reward_payload = _read_json_file(reward_path)
    details_payload = _read_json_file(details_path)

    if reward_payload is None:
        return EvaluationResult(
            reward=0.0,
            validity=ValidityCheck(
                output_parseable=output_parseable,
                schema_valid=schema_valid,
                verifier_completed=False,
                errors=["missing verifier reward artifact"],
            ),
            breakdown=details_payload,
        )

    reward = float(reward_payload.get("reward", 0.0))
    return EvaluationResult(
        reward=reward,
        validity=ValidityCheck(
            output_parseable=output_parseable,
            schema_valid=schema_valid,
            verifier_completed=True,
        ),
        breakdown=details_payload,
    )


def _read_json_file(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
