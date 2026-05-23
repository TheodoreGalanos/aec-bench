# ABOUTME: Persists per-trial results from evolution cycles into the workspace.
# ABOUTME: Writes cycle_trials.jsonl files so the UI can show per-task pass/fail breakdowns.

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from aec_bench.contracts.evolution import EvolutionObservation

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrialOutcome:
    """Lightweight per-trial result for persistence and UI display."""

    trial_id: str
    task_id: str
    discipline: str
    reward: float
    field_scores: dict[str, float]
    turn_count: int
    tool_call_count: int
    tool_error_count: int
    bond_sequence: str
    errors: list[str]
    advisor_calls: int = 0
    advisor_input_tokens: int = 0
    advisor_output_tokens: int = 0


def extract_trial_outcome(obs: EvolutionObservation) -> TrialOutcome:
    """Extract the essential trial outcome from an enriched observation."""
    trial = obs.trial
    enrichment = obs.enrichment

    field_scores: dict[str, float] = {}
    for fs in enrichment.field_scores:
        field_scores[fs.field_name] = fs.reward

    digest = enrichment.trace_digest
    turn_count = digest.turn_count if digest else 0
    tool_call_count = digest.tool_call_count if digest else 0
    tool_error_count = digest.tool_error_count if digest else 0
    bond_sequence = digest.bond_sequence if digest else ""
    errors = list(digest.errors) if digest else []

    cost = trial.cost
    advisor_calls = cost.advisor_calls if cost and cost.advisor_calls is not None else 0
    advisor_input_tokens = cost.advisor_input_tokens if cost and cost.advisor_input_tokens is not None else 0
    advisor_output_tokens = cost.advisor_output_tokens if cost and cost.advisor_output_tokens is not None else 0

    return TrialOutcome(
        trial_id=trial.trial_id,
        task_id=trial.task.task_id,
        discipline=obs.discipline,
        reward=trial.evaluation.reward,
        field_scores=field_scores,
        turn_count=turn_count,
        tool_call_count=tool_call_count,
        tool_error_count=tool_error_count,
        bond_sequence=bond_sequence,
        errors=errors,
        advisor_calls=advisor_calls,
        advisor_input_tokens=advisor_input_tokens,
        advisor_output_tokens=advisor_output_tokens,
    )


def persist_cycle_trials(
    workspace_root: Path,
    cycle: int,
    run_id: str,
    observations: list[EvolutionObservation],
) -> Path:
    """Write per-trial outcomes for a cycle to the workspace.

    Creates ``_trials/{run_id}/cycle_{cycle:03d}.jsonl`` with one JSON line
    per trial. Returns the path to the written file.
    """
    trials_dir = workspace_root / "_trials" / run_id
    trials_dir.mkdir(parents=True, exist_ok=True)

    path = trials_dir / f"cycle_{cycle:03d}.jsonl"
    lines: list[str] = []
    for obs in observations:
        outcome = extract_trial_outcome(obs)
        lines.append(json.dumps(asdict(outcome), default=str))

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info(
        "Persisted %d trial outcomes for cycle %d to %s",
        len(observations),
        cycle,
        path,
    )
    return path


def load_cycle_trials(
    workspace_root: Path,
    run_id: str | None = None,
) -> dict[int, list[TrialOutcome]]:
    """Load persisted trial outcomes grouped by cycle number.

    When run_id is None, loads the most recent run (lexicographically last).
    Returns a dict mapping cycle number to list of TrialOutcome.
    """
    trials_dir = workspace_root / "_trials"
    if not trials_dir.is_dir():
        return {}

    if run_id is None:
        run_dirs = sorted(d for d in trials_dir.iterdir() if d.is_dir())
        if not run_dirs:
            return {}
        run_dir = run_dirs[-1]
    else:
        run_dir = trials_dir / run_id
        if not run_dir.is_dir():
            return {}

    result: dict[int, list[TrialOutcome]] = {}
    for path in sorted(run_dir.glob("cycle_*.jsonl")):
        cycle_num = int(path.stem.split("_")[1])
        outcomes: list[TrialOutcome] = []
        for line in path.read_text(encoding="utf-8").strip().split("\n"):
            if line:
                data = json.loads(line)
                outcomes.append(TrialOutcome(**data))
        result[cycle_num] = outcomes

    return result
