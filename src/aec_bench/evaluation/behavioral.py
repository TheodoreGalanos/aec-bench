# ABOUTME: LLM-driven behavioral trace loading, classification, and scoring utilities.
# ABOUTME: Adapts TrialRecord conversation artifacts into typed traces without Harbor scraping.

from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Protocol, cast

from aec_bench.config import resolve_artifact_path
from aec_bench.contracts.behavioral_types import (
    BondType,
    ClassifiedTrace,
    StructuralScore,
    TurnClassification,
)
from aec_bench.contracts.jsonl import read_jsonl
from aec_bench.contracts.trial_record import TrialRecord

logger = logging.getLogger(__name__)


class BehavioralTraceError(Exception):
    pass


class BehavioralClassificationError(Exception):
    pass


@dataclass(frozen=True)
class BondTypeMetadata:
    chemical_analogy: str
    du_et_al_equivalent: str
    description: str
    indicators: tuple[str, ...]


BOND_TAXONOMY: Mapping[BondType, BondTypeMetadata] = {
    BondType.EXECUTION: BondTypeMetadata(
        chemical_analogy="Covalent",
        du_et_al_equivalent="Normal Operation",
        description="Straightforward tool use or direct action advancing the task",
        indicators=(
            "tool_call",
            "code_execution",
            "file_write",
            "api_request",
            "command_invocation",
            "structured_output",
            "formatting",
            "summary",
        ),
    ),
    BondType.VERIFICATION: BondTypeMetadata(
        chemical_analogy="Hydrogen",
        du_et_al_equivalent="Self-Reflection",
        description="Checking or comparing prior work against expectations",
        indicators=(
            "result_comparison",
            "error_checking",
            "output_validation",
            "backward_reference",
            "test_assertion",
        ),
    ),
    BondType.DELIBERATION: BondTypeMetadata(
        chemical_analogy="Metallic",
        du_et_al_equivalent="Deep Reasoning",
        description="Multi-step reasoning along a committed path",
        indicators=(
            "causal_chain",
            "step_by_step",
            "committed_plan",
            "reasoning_chain",
            "because_therefore",
        ),
    ),
    BondType.EXPLORATION: BondTypeMetadata(
        chemical_analogy="Van der Waals",
        du_et_al_equivalent="Exploration",
        description="Branching, comparing alternatives, or hypothesizing",
        indicators=(
            "hedging_language",
            "alternative_consideration",
            "branching",
            "hypothesis_forming",
            "question_posing",
        ),
    ),
}


@dataclass(frozen=True)
class ToolCall:
    tool_name: str
    arguments: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    tool_name: str
    output: str
    is_error: bool = False


@dataclass(frozen=True)
class Turn:
    turn_index: int
    role: str
    content: str
    tool_calls: tuple[ToolCall, ...] = ()
    tool_results: tuple[ToolResult, ...] = ()


@dataclass(frozen=True)
class BehavioralTrace:
    trace_id: str
    model_name: str
    task_description: str
    turns: tuple[Turn, ...]
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TransitionMatrix:
    matrix: tuple[tuple[float, ...], ...]
    labels: tuple[str, ...]
    sample_count: int


class BehavioralLLMClient(Protocol):
    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 4000,
    ) -> str: ...


_BOND_LIST = list(BondType)
_BOND_INDEX = {bond: index for index, bond in enumerate(_BOND_LIST)}


def load_behavioral_trace(record: TrialRecord) -> BehavioralTrace:
    # Try trajectory first — prefer structured trajectory.jsonl over conversation.jsonl
    trajectory_path = record.outputs.trajectory_path
    if trajectory_path is not None:
        path = resolve_artifact_path(trajectory_path)
        if path is not None:
            turns = _parse_trajectory_to_turns(path)
            return BehavioralTrace(
                trace_id=record.trial_id,
                model_name=record.agent.model,
                task_description=record.inputs.instruction,
                turns=tuple(turns),
                metadata=_trace_metadata(record),
            )

    # Fall back to conversation.jsonl
    conversation_path = record.outputs.conversation_path
    if conversation_path is None:
        raise BehavioralTraceError("trial record is missing a conversation artifact")
    path = resolve_artifact_path(conversation_path)
    if path is None:
        raise BehavioralTraceError(f"conversation artifact does not exist: {conversation_path}")

    messages = read_jsonl(path)
    turns = _parse_transcript_messages(messages)
    return BehavioralTrace(
        trace_id=record.trial_id,
        model_name=record.agent.model,
        task_description=record.inputs.instruction,
        turns=tuple(turns),
        metadata=_trace_metadata(record),
    )


def build_classification_prompt(
    turns: Sequence[Turn],
    context_turns: Sequence[Turn] = (),
) -> str:
    type_defs = []
    for bond_type in _BOND_LIST:
        metadata = BOND_TAXONOMY[bond_type]
        indicators = ", ".join(metadata.indicators)
        type_defs.append(
            f"- **{bond_type.value}** ({metadata.du_et_al_equivalent}): "
            f"{metadata.description}. Indicators: {indicators}"
        )
    types_section = "\n".join(type_defs)

    context_section = ""
    if context_turns:
        context_blocks = [_format_turn_for_prompt(turn) for turn in context_turns[-3:]]
        context_section = "\n## Prior Context (for reference only, do not classify)\n\n" + "\n\n".join(context_blocks)

    turn_blocks = [_format_turn_for_prompt(turn) for turn in turns]
    turns_section = "\n\n".join(turn_blocks)
    indices_str = ", ".join(str(turn.turn_index) for turn in turns)

    return f"""You are a behavioral analyst classifying turns in an AI agent trace.

## Bond Type Definitions

{types_section}

## Classification Rules

1. Each turn gets exactly one bond type
2. EXECUTION: tool calls, direct actions, formatting, summaries -
    the obvious next step advancing the task
3. DELIBERATION: committed reasoning chain - working through HOW to solve a problem step by step
4. EXPLORATION: branching, comparing alternatives - deciding WHAT to do
5. VERIFICATION: checking backward at own work - comparing results
    against expectations, error detection, self-correction
6. Tie-breaking priority: VERIFICATION > EXPLORATION > DELIBERATION > EXECUTION
{context_section}

## Turns to Classify

{turns_section}

## Response Format

Return a JSON object with this exact structure:
```json
{{
  "classifications": [
    {{
      "turn_index": <int>,
      "bond_type": "<execution|deliberation|exploration|verification>",
      "confidence": <float 0-1>,
      "rationale": "<brief explanation>"
    }}
  ]
}}
```

Classify turns: {indices_str}"""


def parse_classification_response(
    response: str,
    expected_indices: Sequence[int],
) -> list[TurnClassification]:
    json_str = _extract_json(response)
    try:
        payload = json.loads(json_str)
        raw_classifications = cast(list[dict[str, object]], payload.get("classifications", []))
    except (json.JSONDecodeError, TypeError):
        raise BehavioralClassificationError("Failed to parse LLM response") from None

    classifications: list[TurnClassification] = []
    classified_indices: set[int] = set()
    for entry in raw_classifications:
        try:
            turn_index = _to_int(entry["turn_index"])
            bond_type = BondType(str(entry["bond_type"]).lower())
            confidence = min(1.0, max(0.0, _to_float(entry.get("confidence", 0.5))))
            rationale = str(entry.get("rationale", ""))
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("skipping malformed classification entry: %s", exc)
            continue
        classifications.append(
            TurnClassification(
                turn_index=turn_index,
                bond_type=bond_type,
                confidence=confidence,
                rationale=rationale,
            )
        )
        classified_indices.add(turn_index)

    for index in expected_indices:
        if index not in classified_indices:
            raise BehavioralClassificationError("LLM did not classify this turn")

    classifications.sort(key=lambda item: item.turn_index)
    return classifications


class LLMTurnClassifier:
    def __init__(
        self,
        *,
        client: BehavioralLLMClient,
        batch_size: int = 5,
        temperature: float = 0.0,
        max_tokens: int = 4000,
    ) -> None:
        self._client = client
        self._batch_size = batch_size
        self._temperature = temperature
        self._max_tokens = max_tokens

    def classify(self, turn: Turn, previous_turns: Sequence[Turn] = ()) -> TurnClassification:
        prompt = build_classification_prompt([turn], context_turns=previous_turns)
        response = self._client.complete(
            prompt,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )
        return parse_classification_response(response, expected_indices=[turn.turn_index])[0]

    def classify_trace(self, trace: BehavioralTrace) -> ClassifiedTrace:
        assistant_turns = [turn for turn in trace.turns if turn.role == "assistant"]
        all_classifications: list[TurnClassification] = []
        if not assistant_turns:
            return ClassifiedTrace(
                trace_id=trace.trace_id,
                model_name=trace.model_name,
                classifications=(),
                metadata=dict(trace.metadata),
            )

        batch_count = math.ceil(len(assistant_turns) / self._batch_size)
        for batch_index in range(batch_count):
            start = batch_index * self._batch_size
            end = start + self._batch_size
            batch = assistant_turns[start:end]
            context = assistant_turns[:start]
            prompt = build_classification_prompt(batch, context_turns=context)
            response = self._client.complete(
                prompt,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
            expected_indices = [turn.turn_index for turn in batch]
            all_classifications.extend(parse_classification_response(response, expected_indices=expected_indices))

        all_classifications.sort(key=lambda item: item.turn_index)
        return ClassifiedTrace(
            trace_id=trace.trace_id,
            model_name=trace.model_name,
            classifications=tuple(all_classifications),
            metadata=dict(trace.metadata),
        )


def compute_transition_counts(classifications: Sequence[TurnClassification]) -> list[list[int]]:
    counts = [[0] * len(_BOND_LIST) for _ in range(len(_BOND_LIST))]
    for previous, current in zip(classifications, classifications[1:], strict=False):
        counts[_BOND_INDEX[previous.bond_type]][_BOND_INDEX[current.bond_type]] += 1
    return counts


def normalize_transition_matrix(
    counts: Sequence[Sequence[int]] | list[list[int]],
    smoothing: float = 0.0,
) -> list[list[float]]:
    normalized: list[list[float]] = []
    for row in counts:
        smoothed = [float(value) + smoothing for value in row]
        row_sum = sum(smoothed)
        if row_sum <= 1e-12:
            normalized.append([0.0] * len(_BOND_LIST))
            continue
        normalized.append([value / row_sum for value in smoothed])
    return normalized


def build_transition_matrix(
    classified_trace: ClassifiedTrace,
    smoothing: float = 0.0,
) -> TransitionMatrix:
    counts = compute_transition_counts(classified_trace.classifications)
    normalized = normalize_transition_matrix(counts, smoothing=smoothing)
    return TransitionMatrix(
        matrix=tuple(tuple(row) for row in normalized),
        labels=tuple(bond.value for bond in _BOND_LIST),
        sample_count=len(classified_trace.classifications),
    )


def aggregate_transition_matrices(matrices: Sequence[TransitionMatrix]) -> TransitionMatrix:
    if not matrices:
        zero_row = tuple(0.0 for _ in _BOND_LIST)
        return TransitionMatrix(
            matrix=tuple(zero_row for _ in _BOND_LIST),
            labels=tuple(bond.value for bond in _BOND_LIST),
            sample_count=0,
        )

    total_samples = sum(matrix.sample_count for matrix in matrices)
    if total_samples == 0:
        zero_row = tuple(0.0 for _ in _BOND_LIST)
        return TransitionMatrix(
            matrix=tuple(zero_row for _ in _BOND_LIST),
            labels=tuple(bond.value for bond in _BOND_LIST),
            sample_count=0,
        )

    aggregate = [[0.0] * len(_BOND_LIST) for _ in range(len(_BOND_LIST))]
    for matrix in matrices:
        weight = matrix.sample_count / total_samples
        for row_index, row in enumerate(matrix.matrix):
            for column_index, value in enumerate(row):
                aggregate[row_index][column_index] += value * weight
    return TransitionMatrix(
        matrix=tuple(tuple(row) for row in aggregate),
        labels=tuple(bond.value for bond in _BOND_LIST),
        sample_count=total_samples,
    )


def build_ideal_pattern(
    traces: Sequence[ClassifiedTrace],
    reward_key: str | None = None,
    min_reward: float = 1.0,
) -> TransitionMatrix:
    if reward_key is None:
        filtered = list(traces)
    else:
        filtered = [trace for trace in traces if _to_float(trace.metadata.get(reward_key, 0.0)) >= min_reward]
    if not filtered:
        raise ValueError(f"No traces passed the reward filter (key={reward_key!r}, min={min_reward})")
    return aggregate_transition_matrices([build_transition_matrix(trace) for trace in filtered])


def build_ideal_sequence(
    traces: Sequence[ClassifiedTrace],
    reward_key: str | None = None,
    min_reward: float = 1.0,
) -> tuple[BondType, ...]:
    if reward_key is None:
        filtered = list(traces)
    else:
        filtered = [trace for trace in traces if _to_float(trace.metadata.get(reward_key, 0.0)) >= min_reward]
    sequences = [
        tuple(classification.bond_type for classification in trace.classifications)
        for trace in filtered
        if trace.classifications
    ]
    if not sequences:
        return ()
    counts = Counter(sequences)
    ranked = sorted(
        counts.items(),
        key=lambda item: (
            -item[1],
            -len(item[0]),
            tuple(bond.value for bond in item[0]),
        ),
    )
    return ranked[0][0]


def cosine_similarity_matrices(matrix_a: TransitionMatrix, matrix_b: TransitionMatrix) -> float:
    flat_a = [value for row in matrix_a.matrix for value in row]
    flat_b = [value for row in matrix_b.matrix for value in row]
    dot_product = sum(left * right for left, right in zip(flat_a, flat_b, strict=False))
    norm_a = math.sqrt(sum(value * value for value in flat_a))
    norm_b = math.sqrt(sum(value * value for value in flat_b))
    if norm_a <= 1e-12 or norm_b <= 1e-12:
        return 0.0
    return dot_product / (norm_a * norm_b)


def bond_sequence_edit_distance(seq_a: Sequence[BondType], seq_b: Sequence[BondType]) -> int:
    if not seq_a:
        return len(seq_b)
    if not seq_b:
        return len(seq_a)

    previous_row = list(range(len(seq_b) + 1))
    current_row = [0] * (len(seq_b) + 1)
    for left_index, left in enumerate(seq_a, start=1):
        current_row[0] = left_index
        for right_index, right in enumerate(seq_b, start=1):
            substitution_cost = 0 if left == right else 1
            current_row[right_index] = min(
                previous_row[right_index] + 1,
                current_row[right_index - 1] + 1,
                previous_row[right_index - 1] + substitution_cost,
            )
        previous_row, current_row = current_row, previous_row
    return previous_row[-1]


def score_trace_structural(
    classified_trace: ClassifiedTrace,
    *,
    ideal_matrix: TransitionMatrix,
    ideal_sequence: Sequence[BondType],
    reward: float | None = None,
) -> StructuralScore:
    trace_matrix = build_transition_matrix(classified_trace)
    trace_sequence = [classification.bond_type for classification in classified_trace.classifications]
    edit_distance = bond_sequence_edit_distance(trace_sequence, ideal_sequence)
    normalization = max(len(trace_sequence), len(ideal_sequence), 1)
    return StructuralScore(
        trace_id=classified_trace.trace_id,
        cosine_similarity=round(cosine_similarity_matrices(trace_matrix, ideal_matrix), 6),
        edit_distance=edit_distance,
        normalized_edit_distance=round(edit_distance / normalization, 6),
        reward=reward,
    )


def _format_turn_for_prompt(turn: Turn) -> str:
    lines = [f"--- Turn {turn.turn_index} (role: {turn.role}) ---"]
    if turn.content:
        content = turn.content[:2000]
        if len(turn.content) > 2000:
            content += "\n[... truncated ...]"
        lines.append(f"Content: {content}")
    for tool_call in turn.tool_calls:
        arguments = json.dumps(dict(tool_call.arguments))[:500]
        lines.append(f"Tool call: {tool_call.tool_name}({arguments})")
    for tool_result in turn.tool_results:
        output = tool_result.output[:500]
        error_tag = " [ERROR]" if tool_result.is_error else ""
        lines.append(f"Tool result{error_tag}: {output}")
    return "\n".join(lines)


def _extract_json(text: str) -> str:
    markdown_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if markdown_match is not None:
        return markdown_match.group(1).strip()
    object_match = re.search(r"\{.*\}", text, re.DOTALL)
    if object_match is not None:
        return object_match.group(0)
    return text


def _parse_trajectory_to_turns(path: Path) -> list[Turn]:
    """Convert a trajectory JSONL file into a list of Turn objects.

    Groups trajectory entries by step number. Step 0 entries with role system/user
    each produce a standalone Turn. All other steps produce one Turn per step with
    assistant content, tool_calls, and tool_results aggregated from their entries.
    """
    from aec_bench.contracts.trajectory import read_trajectory

    all_entries = read_trajectory(path)
    # Exclude warmup entries — they are cache priming, not agent reasoning
    entries = [e for e in all_entries if e.call_type != "warmup"]
    steps: dict[int, list] = {}
    for entry in entries:
        steps.setdefault(entry.step, []).append(entry)

    turns: list[Turn] = []
    turn_index = 0
    for step_num in sorted(steps):
        step_entries = steps[step_num]

        if step_num == 0:
            # Step 0 carries init messages — emit one Turn per system/user entry
            for entry in step_entries:
                if entry.role in ("system", "user"):
                    turns.append(
                        Turn(
                            turn_index=turn_index,
                            role=entry.role,
                            content=entry.content or "",
                        )
                    )
                    turn_index += 1
            continue

        # Agent turns: one Turn per step aggregating content + tool calls/results
        assistant_content = ""
        for entry in step_entries:
            if entry.role == "assistant":
                assistant_content = entry.content or ""
                break

        tool_calls = tuple(
            ToolCall(
                tool_name=entry.tool_name or "unknown",
                arguments=dict(entry.arguments) if entry.arguments else {},
            )
            for entry in step_entries
            if entry.role == "tool_call"
        )
        tool_results = tuple(
            ToolResult(
                tool_name=entry.tool_name or "unknown",
                output=entry.stdout or "",
                is_error=entry.exit_code is not None and entry.exit_code != 0,
            )
            for entry in step_entries
            if entry.role == "tool_result"
        )

        turns.append(
            Turn(
                turn_index=turn_index,
                role="assistant",
                content=assistant_content,
                tool_calls=tool_calls,
                tool_results=tool_results,
            )
        )
        turn_index += 1

    return turns


def _trace_metadata(record: TrialRecord) -> dict[str, object]:
    agent_result = record.outputs.agent_result or {}
    return {
        "reward": record.evaluation.reward,
        "experiment_id": record.experiment_id,
        "task_id": record.task.task_id,
        "adapter": record.agent.adapter,
        "compute_backend": record.environment.compute_backend,
        "turns_used": agent_result.get("turns_used"),
        "max_turns": agent_result.get("max_turns"),
    }


def _parse_transcript_messages(messages: Sequence[dict[str, object]]) -> list[Turn]:
    fmt = _detect_transcript_format(messages)
    if fmt == "canonical":
        return _parse_canonical_messages(messages)
    if fmt == "openai":
        return _parse_openai_messages(messages)
    return _parse_anthropic_messages(messages)


def _detect_transcript_format(messages: Sequence[dict[str, object]]) -> str:
    for message in messages:
        if "event" in message:
            return "canonical"
        if message.get("role") == "tool":
            return "openai"
        if "tool_calls" in message:
            return "openai"
        content = message.get("content")
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict) and "type" in first:
                return "anthropic"
    return "anthropic"


def _parse_canonical_messages(messages: Sequence[dict[str, object]]) -> list[Turn]:
    turns: list[Turn] = []
    turn_index = 0
    for message in messages:
        role = str(message.get("role", ""))
        content = str(message.get("content", ""))
        event = str(message.get("event", "message"))
        if role == "assistant":
            tool_calls: tuple[ToolCall, ...] = ()
            if event == "tool_call":
                tool_calls = (
                    ToolCall(
                        tool_name=str(message.get("tool_name", "unknown")),
                        arguments={},
                    ),
                )
            turns.append(
                Turn(
                    turn_index=turn_index,
                    role=role,
                    content=content,
                    tool_calls=tool_calls,
                )
            )
            turn_index += 1
            continue
        if role == "tool":
            if turns and turns[-1].role == "assistant":
                turns[-1] = replace(
                    turns[-1],
                    tool_results=turns[-1].tool_results
                    + (
                        ToolResult(
                            tool_name=str(message.get("tool_name", "unknown")),
                            output=content,
                            is_error=False,
                        ),
                    ),
                )
            continue
        turns.append(Turn(turn_index=turn_index, role=role, content=content))
        turn_index += 1
    return turns


def _parse_anthropic_messages(messages: Sequence[dict[str, object]]) -> list[Turn]:
    turns: list[Turn] = []
    turn_index = 0
    pending_tool_results: list[ToolResult] = []
    for message in messages:
        role = str(message.get("role", ""))
        content = message.get("content", "")
        if role == "user" and isinstance(content, list):
            pending_tool_results.extend(_anthropic_tool_results(content))
            if turns and turns[-1].role == "assistant":
                turns[-1] = replace(
                    turns[-1],
                    tool_results=tuple(pending_tool_results),
                )
            pending_tool_results = []
            continue
        if role == "user" and isinstance(content, str):
            turns.append(Turn(turn_index=turn_index, role=role, content=content))
            turn_index += 1
            continue
        if role != "assistant":
            continue
        turns.append(_anthropic_assistant_turn(content=content, turn_index=turn_index))
        turn_index += 1
    return turns


def _parse_openai_messages(messages: Sequence[dict[str, object]]) -> list[Turn]:
    turns: list[Turn] = []
    turn_index = 0
    for message in messages:
        role = str(message.get("role", ""))
        if role == "tool":
            if turns and turns[-1].role == "assistant":
                turns[-1] = replace(
                    turns[-1],
                    tool_results=turns[-1].tool_results + (_openai_tool_result(message, messages),),
                )
            continue
        if role == "user":
            turns.append(Turn(turn_index=turn_index, role=role, content=str(message.get("content", ""))))
            turn_index += 1
            continue
        if role != "assistant":
            continue
        turns.append(_openai_assistant_turn(message=message, turn_index=turn_index))
        turn_index += 1
    return turns


def _find_tool_name_by_call_id(messages: Sequence[dict[str, object]], call_id: str) -> str:
    for message in messages:
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
            if tool_call.get("id") == call_id:
                function_payload = tool_call.get("function", {})
                if isinstance(function_payload, dict):
                    return str(function_payload.get("name", "unknown"))
    return "unknown"


def _to_int(value: object) -> int:
    return int(str(value))


def _to_float(value: object) -> float:
    return float(str(value))


def _anthropic_tool_results(content: list[object]) -> list[ToolResult]:
    tool_results: list[ToolResult] = []
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_result":
            continue
        tool_results.append(
            ToolResult(
                tool_name="bash",
                output=str(block.get("content", "")),
                is_error=bool(block.get("is_error", False)),
            )
        )
    return tool_results


def _anthropic_assistant_turn(*, content: object, turn_index: int) -> Turn:
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    if isinstance(content, list):
        for block in content:
            text_part = _anthropic_text_part(block)
            if text_part is not None:
                text_parts.append(text_part)
                continue
            tool_call = _anthropic_tool_call(block)
            if tool_call is not None:
                tool_calls.append(tool_call)
    elif isinstance(content, str):
        text_parts.append(content)
    return Turn(
        turn_index=turn_index,
        role="assistant",
        content="\n".join(text_parts),
        tool_calls=tuple(tool_calls),
    )


def _anthropic_text_part(block: object) -> str | None:
    if not isinstance(block, dict) or block.get("type") != "text":
        return None
    return str(block.get("text", ""))


def _anthropic_tool_call(block: object) -> ToolCall | None:
    if not isinstance(block, dict) or block.get("type") != "tool_use":
        return None
    raw_input = block.get("input", {})
    arguments = raw_input if isinstance(raw_input, dict) else {"raw": raw_input}
    return ToolCall(
        tool_name=str(block.get("name", "unknown")),
        arguments=cast(dict[str, object], arguments),
    )


def _openai_tool_result(
    message: dict[str, object],
    messages: Sequence[dict[str, object]],
) -> ToolResult:
    return ToolResult(
        tool_name=_find_tool_name_by_call_id(messages, str(message.get("tool_call_id", ""))),
        output=str(message.get("content", "")),
        is_error=False,
    )


def _openai_assistant_turn(*, message: dict[str, object], turn_index: int) -> Turn:
    tool_calls = tuple(_openai_tool_calls(message))
    return Turn(
        turn_index=turn_index,
        role="assistant",
        content=str(message.get("content", "") or ""),
        tool_calls=tool_calls,
    )


def _openai_tool_calls(message: dict[str, object]) -> list[ToolCall]:
    tool_calls: list[ToolCall] = []
    for tool_call in cast(list[dict[str, object]], message.get("tool_calls", [])):
        function_payload = cast(dict[str, object], tool_call.get("function", {}))
        tool_calls.append(
            ToolCall(
                tool_name=str(function_payload.get("name", "unknown")),
                arguments=_parse_openai_arguments(function_payload.get("arguments", "{}")),
            )
        )
    return tool_calls


def _parse_openai_arguments(raw_arguments: object) -> dict[str, object]:
    try:
        parsed_arguments = json.loads(str(raw_arguments))
    except json.JSONDecodeError:
        return {"raw": str(raw_arguments)}
    if isinstance(parsed_arguments, dict):
        return cast(dict[str, object], parsed_arguments)
    return {"raw": str(raw_arguments)}
