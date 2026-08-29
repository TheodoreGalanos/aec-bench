#!/usr/bin/env python3
"""Run the bounded real-model pilot for Learning Study L01."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from aec_bench.adapters.rlm.client import RlmMessage
from aec_bench.adapters.rlm.providers import make_rlm_client
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.experimentation.learning_studies.l01_drainage import (
    L01DrainageRun,
    l01_drainage_outcome_projections,
    run_l01_drainage_study_sync,
)
from aec_bench.experimentation.learning_studies.lifecycles import LifecycleConsolidationContext
from aec_bench.lifecycles.stormwater_design.drainage_learning import (
    DRAINAGE_PROBE_TASK_ID,
    validate_drainage_staged_review_feedback,
)

MODEL = "azure:gpt-4.1-mini-standard"
DEPLOYMENT_NAME = "gpt-4.1-mini-standard"
CONSOLIDATION_TIMEOUT_SECONDS = 600
CONSOLIDATION_MAX_TOKENS = 2048
SUMMARY_NAME = "l01-pilot-summary.json"
PRIMARY_PROJECTIONS = (
    "drainage.staged-disclosure",
    "drainage.finding-continuity",
)


class AzureLifecycleConsolidator:
    """Turn the released public feedback into bounded structured memory."""

    def __init__(
        self,
        *,
        model: str = MODEL,
        max_tokens: int = CONSOLIDATION_MAX_TOKENS,
        timeout_seconds: int = CONSOLIDATION_TIMEOUT_SECONDS,
    ) -> None:
        self.model = model
        self._client = make_rlm_client(
            model,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
            cache=False,
        )
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cache_read_tokens = 0
        self.cache_write_tokens = 0
        self.last_lessons: list[dict[str, str]] = []

    def __call__(self, context: LifecycleConsolidationContext) -> None:
        feedback_payloads = self._read_feedback(context)
        prompt = _consolidation_prompt(feedback_payloads)
        self.calls += 1
        response = self._client.generate(
            model=self.model,
            messages=[RlmMessage(role="user", content=prompt)],
            system_prompt=(
                "You consolidate only the public feedback supplied in the user message. "
                "Do not use outside knowledge, hidden evaluator information, or filesystem paths."
            ),
        )
        self.input_tokens += response.input_tokens
        self.output_tokens += response.output_tokens
        self.cache_read_tokens += response.cache_read_tokens
        self.cache_write_tokens += response.cache_write_tokens
        if response.error_message:
            raise RuntimeError("consolidation-provider-error")
        lessons = _parse_lessons(response.output_text)
        lessons_json = (json.dumps({"lessons": lessons}, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        lessons_markdown = _lessons_markdown(lessons).encode("utf-8")
        if len(lessons_json) > 64_000 or len(lessons_markdown) > 64_000:
            raise ValueError("consolidation-output-invalid")

        memory_root = _validate_memory_boundary(context)
        memory_root.mkdir(parents=True, exist_ok=True)
        (memory_root / "lessons.json").write_bytes(lessons_json)
        (memory_root / "lessons.md").write_bytes(lessons_markdown)
        self.last_lessons = lessons

    @staticmethod
    def _read_feedback(context: LifecycleConsolidationContext) -> list[dict[str, Any]]:
        _validate_memory_boundary(context)
        if not context.feedback:
            raise ValueError("consolidation-input-invalid")
        payloads: list[dict[str, Any]] = []
        for item in context.feedback:
            path = item.path.resolve(strict=True)
            expected_parent = context.state_root.resolve(strict=True) / "feedback"
            if path.parent != expected_parent or path.suffix != ".json":
                raise ValueError("consolidation-input-invalid")
            payload = validate_drainage_staged_review_feedback(path.read_bytes())
            payloads.append(payload)
        encoded = json.dumps(payloads, ensure_ascii=False, sort_keys=True)
        if len(encoded.encode("utf-8")) > 200_000:
            raise ValueError("consolidation-input-too-large")
        return payloads


def _validate_memory_boundary(context: LifecycleConsolidationContext) -> Path:
    state_root = context.state_root.resolve(strict=True)
    memory_root = context.memory_root.resolve(strict=False)
    if memory_root.parent != state_root or memory_root.name != "memory":
        raise ValueError("consolidation-memory-boundary-invalid")
    if context.memory_root.is_symlink():
        raise ValueError("consolidation-memory-boundary-invalid")
    return context.memory_root


def _consolidation_prompt(payloads: Iterable[dict[str, Any]]) -> str:
    feedback = json.dumps(list(payloads), ensure_ascii=False, sort_keys=True, indent=2)
    return f"""Create transferable drainage-review lessons from the public feedback below.

Use ONLY facts and principles present in that feedback. Do not invent scores, findings,
causes, evaluator details, file paths, or project-specific facts. Keep each lesson useful
for reviewing a later staged-evidence submission. Return JSON only, with exactly this
shape:
{{
  "lessons": [
    {{
      "principle": "one concise review principle",
      "evidence": "which feedback fact supports it",
      "application": "how to apply it"
    }}
  ]
}}

Write 3 to 8 lessons. Each string must be concise and under 600 characters.

PUBLIC FEEDBACK:
{feedback}
"""


def _parse_lessons(text: str) -> list[dict[str, str]]:
    candidate = text.strip()
    if candidate.startswith("```") and candidate.endswith("```"):
        candidate = candidate.split("\n", 1)[1].rsplit("\n", 1)[0].strip()
    try:
        decoded = json.loads(candidate)
    except (json.JSONDecodeError, TypeError) as error:
        raise ValueError("consolidation-output-invalid") from error
    if not isinstance(decoded, dict) or set(decoded) != {"lessons"}:
        raise ValueError("consolidation-output-invalid")
    raw_lessons = decoded["lessons"]
    if not isinstance(raw_lessons, list) or not 3 <= len(raw_lessons) <= 8:
        raise ValueError("consolidation-output-invalid")
    lessons: list[dict[str, str]] = []
    for raw in raw_lessons:
        if not isinstance(raw, dict) or set(raw) != {"principle", "evidence", "application"}:
            raise ValueError("consolidation-output-invalid")
        lesson = {key: raw[key] for key in ("principle", "evidence", "application")}
        if any(not isinstance(value, str) or not value.strip() or len(value) > 600 for value in lesson.values()):
            raise ValueError("consolidation-output-invalid")
        lessons.append(lesson)
    return lessons


def _lessons_markdown(lessons: list[dict[str, str]]) -> str:
    sections = ["# Drainage review lessons", ""]
    for index, lesson in enumerate(lessons, start=1):
        sections.extend(
            [
                f"## Lesson {index}: {lesson['principle']}",
                "",
                f"- **Evidence:** {lesson['evidence']}",
                f"- **Application:** {lesson['application']}",
                "",
            ]
        )
    return "\n".join(sections)


def _build_agent() -> AgentConfig:
    return AgentConfig(
        name="l01-real-model-pilot",
        adapter="tool_loop",
        model=MODEL,
        parameters={
            "max_turns_per_session": 120,
        },
    )


def _build_compute() -> ComputeConfig:
    return ComputeConfig(
        backend="local",
        resource_limits={
            "n_concurrent_trials": 1,
        },
    )


def _new_run_root(stage: str) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    root = Path("/Users/theodoros.galanos/LocalProjects/aec-bench-pilot-runs/l01") / f"{stage}-{stamp}"
    root.mkdir(parents=True, exist_ok=False)
    return root


def _cost_totals(records: Iterable[TrialRecord]) -> dict[str, Any]:
    records_list = list(records)
    result: dict[str, Any] = {}
    for field in (
        "model_calls",
        "tokens_in",
        "tokens_out",
        "cache_read_tokens",
        "cache_write_tokens",
        "estimated_cost_usd",
    ):
        values = [None if record.cost is None else getattr(record.cost, field) for record in records_list]
        known = [value for value in values if value is not None]
        result[field] = sum(known) if len(known) == len(values) and values else None
        result[f"{field}_known_records"] = len(known)
        result[f"{field}_unknown_records"] = len(values) - len(known)
    return result


def _trial_summary(
    *,
    study_run: L01DrainageRun,
    consolidator: AzureLifecycleConsolidator,
) -> dict[str, Any]:
    projections = l01_drainage_outcome_projections()
    trial_records = tuple(record for arm in study_run.execution.arm_runs for record in arm.trial_records)
    execution_by_id = {item.arm_run_id: item for item in study_run.execution.arm_runs}
    arms: dict[str, list[dict[str, Any]]] = {}
    for planned_arm in study_run.plan.arm_runs:
        result = execution_by_id[planned_arm.arm_run_id]
        trials: list[dict[str, Any]] = []
        for record in result.trial_records:
            measurement_values: dict[str, Any] = {}
            for projection_id, projection in projections.items():
                try:
                    projected = projection(record)
                    measurement_values[projection_id] = {
                        "eligible": projected.eligible,
                        "value": projected.value,
                        "reason": projected.reason,
                    }
                except Exception:
                    measurement_values[projection_id] = {
                        "eligible": False,
                        "value": None,
                        "reason": "projection-error",
                    }
            trials.append(
                {
                    "trial_id": record.trial_id,
                    "task_id": record.task_id,
                    "repetition": record.attempt,
                    "execution_status": record.execution_status.value,
                    "evaluation_status": record.evaluation_status.value,
                    "validity": (
                        None if record.evaluation is None else record.evaluation.validity.model_dump(mode="json")
                    ),
                    "measurements": measurement_values,
                }
            )
        arms.setdefault(planned_arm.arm_id, []).append(
            {
                "arm_run_id": planned_arm.arm_run_id,
                "repetition": planned_arm.repetition,
                "status": result.status.value,
                "trials": trials,
            }
        )

    return {
        "study_run_id": study_run.execution.study_run_id,
        "status": (
            "completed"
            if trial_records
            and all(record.execution_status.value == "completed" for record in trial_records)
            and all(
                record.evaluation is not None and record.evaluation.validity.verifier_completed
                for record in trial_records
            )
            else "completed_with_failures"
        ),
        "deployment": DEPLOYMENT_NAME,
        "model": MODEL,
        "agent": _build_agent().model_dump(mode="json"),
        "compute": _build_compute().model_dump(mode="json"),
        "trial_records": {
            "count": len(trial_records),
            "all_completed": all(record.execution_status.value == "completed" for record in trial_records),
            "all_verifiers_completed": all(
                record.evaluation is not None and record.evaluation.validity.verifier_completed
                for record in trial_records
            ),
            "cost_totals": _cost_totals(trial_records),
        },
        "arms": arms,
        "assessments": {
            "relations_reviewed_false": study_run.unreviewed_assessment.model_dump(mode="json"),
            "relations_reviewed_true": study_run.reviewed_assessment.model_dump(mode="json"),
        },
        "consolidation": {
            "operation_id": "update-lifecycle-review-memory",
            "calls": consolidator.calls,
            "input_tokens": consolidator.input_tokens,
            "output_tokens": consolidator.output_tokens,
            "cache_read_tokens": consolidator.cache_read_tokens,
            "cache_write_tokens": consolidator.cache_write_tokens,
            "lessons": consolidator.last_lessons,
        },
        "ceiling_diagnostics": _ceiling_diagnostics(study_run),
    }


def _ceiling_diagnostics(study_run: L01DrainageRun) -> dict[str, Any]:
    cold = next(item for item in study_run.plan.arm_runs if item.arm_id == "cold-reset")
    cold_result = next(item for item in study_run.execution.arm_runs if item.arm_run_id == cold.arm_run_id)
    probe = next((record for record in cold_result.trial_records if record.task_id == DRAINAGE_PROBE_TASK_ID), None)
    projections = l01_drainage_outcome_projections()
    scores: dict[str, Any] = {}
    for projection_id in PRIMARY_PROJECTIONS:
        if probe is None:
            scores[projection_id] = {"eligible": False, "value": None, "reason": "cold-probe-missing"}
            continue
        projected = projections[projection_id](probe)
        scores[projection_id] = {
            "eligible": projected.eligible,
            "value": projected.value,
            "reason": projected.reason,
        }
    eligible_values = [item["value"] for item in scores.values() if item["eligible"] and item["value"] is not None]
    headroom_limited = len(eligible_values) == len(PRIMARY_PROJECTIONS) and all(
        value >= 0.95 for value in eligible_values
    )
    return {
        "primary_measurements": list(PRIMARY_PROJECTIONS),
        "cold_arm_probe_scores": scores,
        "headroom_limited": headroom_limited,
        "interpretation": (
            "Cold-arm probe is approximately at ceiling on both primary measurements; no learning claim is supported."
            if headroom_limited
            else "Cold-arm probe is not at ceiling on every primary measurement."
        ),
    }


def _write_summary(run_root: Path, summary: dict[str, Any]) -> Path:
    path = run_root / SUMMARY_NAME
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def run_stage(*, stage: str, repetitions: int, run_root: Path) -> tuple[Path, dict[str, Any]]:
    required = ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_API_VERSION")
    if not all(os.environ.get(name) for name in required):
        raise RuntimeError("Azure OpenAI environment is incomplete")
    # PydanticAI's ``azure:`` model route reads the API version under the
    # OpenAI-compatible name, while the repository's .env uses Azure's name.
    os.environ["OPENAI_API_VERSION"] = os.environ["AZURE_OPENAI_API_VERSION"]
    consolidator = AzureLifecycleConsolidator()
    study_run = run_l01_drainage_study_sync(
        run_root=run_root,
        study_run_id=f"l01-real-model-{stage}-{run_root.name.rsplit('-', 1)[-1]}",
        agent=_build_agent(),
        compute=_build_compute(),
        consolidation_operation=consolidator,
        repetitions=repetitions,
    )
    summary = _trial_summary(study_run=study_run, consolidator=consolidator)
    return _write_summary(run_root, summary), summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("smoke", "pilot"), required=True)
    parser.add_argument("--repetitions", type=int)
    parser.add_argument("--run-root", type=Path)
    return parser.parse_args()


def main() -> int:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    args = _parse_args()
    repetitions = args.repetitions if args.repetitions is not None else (1 if args.stage == "smoke" else 3)
    if repetitions < 1:
        raise SystemExit("--repetitions must be positive")
    run_root = args.run_root or _new_run_root(args.stage)
    if run_root.exists() and any(run_root.iterdir()):
        raise SystemExit("run root must be empty")
    run_root.mkdir(parents=True, exist_ok=True)
    try:
        summary_path, summary = run_stage(stage=args.stage, repetitions=repetitions, run_root=run_root)
    except Exception as error:
        _write_summary(
            run_root,
            {
                "status": "failed",
                "stage": args.stage,
                "repetitions": repetitions,
                "deployment": DEPLOYMENT_NAME,
                "failure_type": type(error).__name__,
            },
        )
        print(f"{args.stage} failed ({type(error).__name__}); retained artifacts under {run_root}")
        return 1

    ceiling = summary["ceiling_diagnostics"]
    costs = summary["trial_records"]["cost_totals"]
    print(
        f"{args.stage} {summary['status']}: {summary['trial_records']['count']} TrialRecords; "
        f"cold primary scores={ceiling['cold_arm_probe_scores']}; "
        f"headroom_limited={ceiling['headroom_limited']}"
    )
    print(
        f"TrialRecord tokens in/out={costs['tokens_in']}/{costs['tokens_out']}; "
        f"estimated cost={costs['estimated_cost_usd']}; "
        f"consolidation calls/tokens in/out={summary['consolidation']['calls']}/"
        f"{summary['consolidation']['input_tokens']}/{summary['consolidation']['output_tokens']}"
    )
    print(f"Summary: {summary_path}")
    return 0 if summary["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
