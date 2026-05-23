# ABOUTME: Constitutional LLM inference engine: derives typed params from principles + metadata.
# ABOUTME: Follows the advisor.py pattern: structured JSON prompt, safe fallback, token tracking.

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from aec_bench.adapters.base import AdapterCapabilities
from aec_bench.adapters.rlm.client import RlmClient, RlmMessage
from aec_bench.contracts.constitution import (
    ConstitutionManifest,
    EarnedAutonomyParams,
    InformationMinimalityParams,
    ProgressObligationParams,
    SourceFidelityParams,
    StatePersistenceParams,
)

T = TypeVar("T")

_INFERENCE_SYSTEM_PROMPT = """\
You are configuring an agent harness using constitutional principles.

Given a set of principles, task metadata, and adapter capabilities, you must
derive concrete parameter values for each enabled principle that this adapter
can enforce.

Principles describe desired behaviour. Task metadata describes the task
context. Capabilities describe what mechanisms the adapter has. You produce
typed parameter values that serve the principles for this specific task.

Consider:
- Harder tasks benefit from more aggressive context filtering (less noise)
- Structured-output tasks need tighter progress obligations
- Tasks with many sources need generous search thresholds
- Open-ended tasks need lighter compression

Respond with ONLY a JSON object with the following shape (omit principles
the adapter doesn't support):

{
  "information_minimality": {
    "default_threshold": <int 500..10000>,
    "search_threshold": <int 5000..50000>,
    "preview_length": <int 100..500>,
    "truncation_strategy": "metadata" | "head" | "tail"
  },
  "state_persistence": {
    "preserve_variables": <bool>,
    "preserve_scratchpad": <bool>,
    "compaction_strategy": "llm_summary" | "state_only" | "full_reset"
  },
  "progress_obligation": {
    "gentle_nudge_turns": <int 3..30>,
    "strong_nudge_turns": <int 5..50>,
    "stall_threshold_turns": <int 1..10>
  },
  "source_fidelity": {
    "require_source_tracing": <bool>,
    "tbd_placeholder": <string>,
    "gap_framing": "exclude" | "tbd" | "omit"
  },
  "earned_autonomy": {
    "initial_mode": "constrained" | "guided" | "autonomous",
    "promotion_threshold": <int 1..10>,
    "demotion_on_stall": <bool>
  }
}

Return ONLY the JSON object, no other text.
"""


@dataclass(frozen=True)
class ConstitutionalInferenceResult:
    """Result of constitutional inference. Manifest is always populated; on
    error, unfilled parameter slots get constructor defaults."""

    manifest: ConstitutionManifest
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None


def _supported_principles(
    constitution: ConstitutionManifest,
    capabilities: AdapterCapabilities,
) -> list[str]:
    """Return names of principles that are (a) enabled and (b) supported by the adapter."""
    out: list[str] = []
    for p in constitution.principles:
        if not p.enabled:
            continue
        try:
            if capabilities.supports_principle(p.name):
                out.append(p.name)
        except ValueError:
            continue
    return out


def build_inference_prompt(
    *,
    constitution: ConstitutionManifest,
    task_metadata: dict[str, Any],
    capabilities: AdapterCapabilities,
) -> str:
    """Construct the user-message text for the inference call."""
    supported = _supported_principles(constitution, capabilities)

    parts: list[str] = []
    parts.append("=== Principles to configure (enabled + supported) ===")
    for p in constitution.principles:
        if p.name not in supported:
            continue
        parts.append(f"\n[{p.name}]")
        parts.append(f"  description: {p.description}")
        parts.append(f"  evaluation: {p.evaluation_criteria}")

    parts.append("\n=== Task metadata ===")
    parts.append(json.dumps(task_metadata, indent=2, default=str, sort_keys=True))

    parts.append("\n=== Adapter capabilities ===")
    cap_dict = {
        "has_context_filtering": capabilities.has_context_filtering,
        "has_state_persistence": capabilities.has_state_persistence,
        "has_compaction": capabilities.has_compaction,
        "has_scaffolding": capabilities.has_scaffolding,
        "has_review_phase": capabilities.has_review_phase,
        "has_source_tracing": capabilities.has_source_tracing,
    }
    parts.append(json.dumps(cap_dict, indent=2))

    parts.append("\nReturn a JSON object with typed parameters. Omit principles the adapter does not support.")
    return "\n".join(parts)


def _extract_json(text: str) -> dict[str, Any] | None:
    """Extract a JSON object from text, tolerating fenced code blocks."""
    fence_pattern = r"```(?:json)?\s*\n(.*?)```"
    matches = re.findall(fence_pattern, text, re.DOTALL)
    if matches:
        try:
            parsed = json.loads(matches[-1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return None


def _build_params_from_response(
    *,
    response_obj: dict[str, Any] | None,
    constitution: ConstitutionManifest,
    capabilities: AdapterCapabilities,
    fallback_to_defaults: bool,
) -> ConstitutionManifest:
    """Build a manifest with parameter models populated from a parsed response.

    - If a principle is disabled → leave slot as None (regardless of response).
    - If a principle is enabled + supported + response has data → use response.
    - If enabled + supported + response missing → fallback default instance
      (when fallback_to_defaults=True) or None.
    """
    supported = set(_supported_principles(constitution, capabilities))
    obj = response_obj or {}

    def _pick(
        name: str,
        builder: Callable[[dict[str, Any]], T],
        default_cls: Callable[[], T],
    ) -> T | None:
        if name not in supported:
            return None
        data = obj.get(name)
        if isinstance(data, dict):
            try:
                return builder(data)
            except (TypeError, ValueError, KeyError):
                pass
        return default_cls() if fallback_to_defaults else None

    information_minimality = _pick(
        "information_minimality",
        lambda d: InformationMinimalityParams(
            default_threshold=int(d.get("default_threshold", 2000)),
            search_threshold=int(d.get("search_threshold", 10_000)),
            preview_length=int(d.get("preview_length", 200)),
            truncation_strategy=d.get("truncation_strategy", "metadata"),
        ),
        InformationMinimalityParams,
    )

    state_persistence = _pick(
        "state_persistence",
        lambda d: StatePersistenceParams(
            preserve_variables=bool(d.get("preserve_variables", True)),
            preserve_scratchpad=bool(d.get("preserve_scratchpad", True)),
            compaction_strategy=d.get("compaction_strategy", "llm_summary"),
        ),
        StatePersistenceParams,
    )

    progress_obligation = _pick(
        "progress_obligation",
        lambda d: ProgressObligationParams(
            gentle_nudge_turns=int(d.get("gentle_nudge_turns", 10)),
            strong_nudge_turns=int(d.get("strong_nudge_turns", 20)),
            stall_threshold_turns=int(d.get("stall_threshold_turns", 3)),
        ),
        ProgressObligationParams,
    )

    source_fidelity = _pick(
        "source_fidelity",
        lambda d: SourceFidelityParams(
            require_source_tracing=bool(d.get("require_source_tracing", True)),
            tbd_placeholder=str(d.get("tbd_placeholder", "[TBD]")),
            gap_framing=d.get("gap_framing", "exclude"),
        ),
        SourceFidelityParams,
    )

    earned_autonomy = _pick(
        "earned_autonomy",
        lambda d: EarnedAutonomyParams(
            initial_mode=d.get("initial_mode", "constrained"),
            promotion_threshold=int(d.get("promotion_threshold", 2)),
            demotion_on_stall=bool(d.get("demotion_on_stall", True)),
        ),
        EarnedAutonomyParams,
    )

    return ConstitutionManifest(
        version=constitution.version,
        principles=constitution.principles,
        information_minimality=information_minimality,
        state_persistence=state_persistence,
        progress_obligation=progress_obligation,
        source_fidelity=source_fidelity,
        earned_autonomy=earned_autonomy,
    )


def merge_with_overrides(
    *,
    user: ConstitutionManifest,
    inferred: ConstitutionManifest,
) -> ConstitutionManifest:
    """Merge two manifests. User-provided parameter models take precedence."""
    return ConstitutionManifest(
        version=user.version,
        principles=user.principles,
        information_minimality=user.information_minimality or inferred.information_minimality,
        state_persistence=user.state_persistence or inferred.state_persistence,
        progress_obligation=user.progress_obligation or inferred.progress_obligation,
        source_fidelity=user.source_fidelity or inferred.source_fidelity,
        earned_autonomy=user.earned_autonomy or inferred.earned_autonomy,
    )


def infer_constitutional_parameters(
    *,
    constitution: ConstitutionManifest,
    task_metadata: dict[str, Any],
    capabilities: AdapterCapabilities,
    client: RlmClient,
    model: str,
) -> ConstitutionalInferenceResult:
    """Call the inference model and merge with any user overrides.

    - Principles with user-provided parameter models are respected (inference
      only fills missing slots).
    - On client error or unparseable response, all unfilled enabled+supported
      principles get constructor-default parameter instances.
    - Disabled principles always yield None regardless of response.
    """
    prompt = build_inference_prompt(
        constitution=constitution,
        task_metadata=task_metadata,
        capabilities=capabilities,
    )

    response = client.generate(
        model=model,
        messages=[RlmMessage(role="user", content=prompt)],
        system_prompt=_INFERENCE_SYSTEM_PROMPT,
    )

    if response.error_message:
        inferred = _build_params_from_response(
            response_obj=None,
            constitution=constitution,
            capabilities=capabilities,
            fallback_to_defaults=True,
        )
        merged = merge_with_overrides(user=constitution, inferred=inferred)
        return ConstitutionalInferenceResult(
            manifest=merged,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            error=response.error_message,
        )

    parsed = _extract_json(response.output_text)
    if parsed is None:
        inferred = _build_params_from_response(
            response_obj=None,
            constitution=constitution,
            capabilities=capabilities,
            fallback_to_defaults=True,
        )
        merged = merge_with_overrides(user=constitution, inferred=inferred)
        return ConstitutionalInferenceResult(
            manifest=merged,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            error="failed to parse inference response",
        )

    inferred = _build_params_from_response(
        response_obj=parsed,
        constitution=constitution,
        capabilities=capabilities,
        fallback_to_defaults=True,
    )

    merged = merge_with_overrides(user=constitution, inferred=inferred)
    return ConstitutionalInferenceResult(
        manifest=merged,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        error=None,
    )
