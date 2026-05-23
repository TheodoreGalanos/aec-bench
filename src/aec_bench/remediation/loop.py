# ABOUTME: Remediation orchestrator — iterates propose → apply → re-verify until plateau / target / max.
# ABOUTME: Tracks per-criterion attempt count; escalates to HITL after 2 failed attempts.

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aec_bench.contracts.remediation import (
    HitlItem,
    PatchProposal,
    PatchStatus,
    RemediationIteration,
    RemediationResult,
)
from aec_bench.remediation.applier import (
    AmbiguousLocator,
    AnnotatedPatch,
    SectionNotFound,
    apply_annotated_patch,
    apply_patches,
    split_sections,
)
from aec_bench.remediation.section_resolver import (
    extract_section_refs,
    match_refs_to_sections,
)
from aec_bench.remediation.span_extractor import (
    extract_quoted_spans,
    locate_span_in_section,
)
from aec_bench.remediation.verifier_runner import VerifierResult


@dataclass(frozen=True)
class RemediationConfig:
    max_iterations: int = 3
    plateau_threshold: float = 0.02
    target_reward: float | None = None
    max_attempts_per_criterion: int = 2


Proposer = Callable[..., PatchProposal]
VerifierFn = Callable[..., VerifierResult]
SectionSelectorFn = Callable[[str, list[str]], list[str]]
IterationCallback = Callable[[RemediationIteration], bool]


_MARKER_START = "<<<REVIEW>>>"
_MARKER_END = "<<<END_REVIEW>>>"


def _collect_unsatisfied(details: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Return a list of (section_id, criterion, evidence) tuples from verifier details."""
    out: list[tuple[str, str, str]] = []
    for dim_id, dim in details.items():
        if not isinstance(dim, dict):
            continue
        criteria = dim.get("unsatisfied", []) or []
        evidence = dim.get("evidence", "") or ""
        for c in criteria:
            out.append((dim_id, str(c), evidence))
    return out


def _get_section_text(current_output: str, section_id: str) -> str | None:
    """Return the section's text body, or None when no unique match is found."""
    sections = split_sections(current_output)
    if section_id in sections:
        start, end = sections[section_id]
        return current_output[start:end]
    candidates = [
        k
        for k in sections
        if k.startswith(section_id + "_") or k.endswith("_" + section_id) or ("_" + section_id + "_") in k
    ]
    if len(candidates) == 1:
        start, end = sections[candidates[0]]
        return current_output[start:end]
    return None


def _annotate_span(section_text: str, span: str) -> str:
    """Wrap the span with review markers. Span is known to appear exactly once."""
    return section_text.replace(span, f"{_MARKER_START}{span}{_MARKER_END}", 1)


def _write_log_entry(log_path: Path, entry: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def _resolve_target_sections(
    dimension_id: str,
    evidence: str,
    current_output: str,
    selector: SectionSelectorFn | None,
) -> list[str]:
    """Return list of section_ids to propose against for this criterion.

    Priority cascade:
      1. Regex-extract section refs from evidence -> match against real sections
      2. Dimension id literal match (legacy)
      3. LLM selector (when injected)
      4. Empty -- caller uses full-output fallback
    """
    sections = split_sections(current_output)
    available = list(sections.keys())

    refs = extract_section_refs(evidence)
    matched = match_refs_to_sections(refs, available) if refs else []
    if matched:
        return matched

    if _get_section_text(current_output, dimension_id) is not None:
        return [dimension_id]

    if selector is not None:
        picked = selector(evidence, available)
        if picked:
            return [p for p in picked if p in available]

    return []


def run_remediation_loop(
    *,
    run_dir: Path,
    task_dir: Path,
    proposer: Proposer,
    verifier: VerifierFn,
    config: RemediationConfig | None = None,
    section_selector: SectionSelectorFn | None = None,
    on_iteration: IterationCallback | None = None,
) -> RemediationResult:
    """Iterate propose → apply → re-verify until a stop condition is met."""
    cfg = config or RemediationConfig()
    current_output = (run_dir / "output.md").read_text()
    initial_details = json.loads((run_dir / "logs" / "verifier" / "details.json").read_text())

    attempt_count: dict[tuple[str, str], int] = {}
    iterations: list[RemediationIteration] = []
    hitl: list[HitlItem] = []
    current_details = initial_details

    # If there are no unsatisfied criteria, exit immediately
    unsatisfied = _collect_unsatisfied(current_details)
    if not unsatisfied:
        return RemediationResult(
            iterations=tuple(iterations),
            hitl_items=tuple(hitl),
            stop_reason="no_defects",
            final_reward=float(current_details.get("reward", 0.0)),
            final_output_text=current_output,
        )

    reward_before = float(current_details.get("reward", 0.0))

    for iteration_num in range(1, cfg.max_iterations + 1):
        unsatisfied = _collect_unsatisfied(current_details)
        if not unsatisfied:
            return RemediationResult(
                iterations=tuple(iterations),
                hitl_items=tuple(hitl),
                stop_reason="no_defects",
                final_reward=reward_before,
                final_output_text=current_output,
            )

        log_path = run_dir / "remediation" / f"iteration_{iteration_num}" / "proposer_log.jsonl"
        proposals: list[PatchProposal] = []
        # Parallel list tracking which path each proposal took + the located span (if any).
        # Used at apply time to dispatch annotated patches through apply_annotated_patch.
        traces: list[tuple[PatchProposal, str, str | None]] = []

        for section_id, criterion, evidence in unsatisfied:
            target_sections = _resolve_target_sections(
                dimension_id=section_id,
                evidence=evidence,
                current_output=current_output,
                selector=section_selector,
            )

            if not target_sections:
                # Full-output v1 fallback -- caller never resolved a section
                key = (section_id, criterion)
                attempts = attempt_count.get(key, 0)
                if attempts >= cfg.max_attempts_per_criterion:
                    continue
                log_entry: dict[str, Any] = {
                    "section_id": section_id,
                    "resolved_section_id": None,
                    "original_dimension_id": section_id,
                    "criterion": criterion,
                    "evidence": evidence,
                    "resolution_method": "fallback",
                    "section_chars": 0,
                    "quoted_spans_extracted": 0,
                    "span_located": None,
                    "path": "v1_locator",
                    "fallback_reason": "no_sections_resolved",
                }
                proposal = proposer(
                    section_id=section_id,
                    section_excerpt=current_output,
                    criterion=criterion,
                    evidence=evidence,
                )
                log_entry["proposal_status"] = proposal.status.value
                log_entry["confidence"] = proposal.confidence
                _write_log_entry(log_path, log_entry)
                attempt_count[key] = attempts + 1
                traces.append((proposal, "v1_locator", None))
                proposals.append(proposal)
                continue

            # Determine resolution_method by re-running the primary check
            # (minor redundancy but keeps the log accurate).
            refs = extract_section_refs(evidence)
            matched = match_refs_to_sections(refs, list(split_sections(current_output).keys())) if refs else []
            if matched:
                resolution_method = "regex"
            elif _get_section_text(current_output, section_id) is not None:
                resolution_method = "dimension_id"
            else:
                resolution_method = "llm_selector"

            for resolved_section_id in target_sections:
                key = (resolved_section_id, criterion)
                attempts = attempt_count.get(key, 0)
                if attempts >= cfg.max_attempts_per_criterion:
                    continue

                section_text = _get_section_text(current_output, resolved_section_id)

                log_entry = {
                    "section_id": resolved_section_id,
                    "resolved_section_id": resolved_section_id,
                    "original_dimension_id": section_id,
                    "criterion": criterion,
                    "evidence": evidence,
                    "resolution_method": resolution_method,
                    "section_chars": len(section_text) if section_text else 0,
                }

                candidate_spans = extract_quoted_spans(evidence)
                span = locate_span_in_section(section_text, candidate_spans) if section_text else None
                log_entry["quoted_spans_extracted"] = len(candidate_spans)
                log_entry["span_located"] = span

                if span is not None and section_text is not None:
                    annotated = _annotate_span(section_text, span)
                    proposal = proposer(
                        section_id=resolved_section_id,
                        annotated_section=annotated,
                        span_to_replace=span,
                        criterion=criterion,
                        evidence=evidence,
                    )
                    path = "annotated"
                else:
                    proposal = proposer(
                        section_id=resolved_section_id,
                        section_excerpt=section_text,
                        criterion=criterion,
                        evidence=evidence,
                    )
                    path = "v1_locator"
                    log_entry["fallback_reason"] = "no_quoted_span_in_evidence"

                log_entry["path"] = path
                log_entry["proposal_status"] = proposal.status.value
                log_entry["confidence"] = proposal.confidence
                _write_log_entry(log_path, log_entry)

                attempt_count[key] = attempts + 1
                traces.append((proposal, path, span))
                proposals.append(proposal)

        apply_traces = [t for t in traces if t[0].status == PatchStatus.APPLY]
        if not apply_traces:
            for p in proposals:
                if p.status != PatchStatus.APPLY:
                    hitl.append(
                        HitlItem(
                            section_id=p.patch.section_id,
                            criterion=p.criterion,
                            evidence=p.evidence,
                            suggested_resolution=p.rationale,
                            attempt_count=attempt_count[(p.patch.section_id, p.criterion)],
                        )
                    )
            return RemediationResult(
                iterations=tuple(iterations),
                hitl_items=tuple(hitl),
                stop_reason="no_patches_available",
                final_reward=reward_before,
                final_output_text=current_output,
            )

        applied = 0
        rejected_count = 0
        for proposal, path_name, span in apply_traces:
            if path_name == "annotated" and span is not None:
                annotated_patch = AnnotatedPatch(
                    section_id=proposal.patch.section_id,
                    span_to_replace=span,
                    replacement=proposal.patch.replacement,
                )
                try:
                    current_output = apply_annotated_patch(current_output, annotated_patch)
                    applied += 1
                except (SectionNotFound, AmbiguousLocator):
                    rejected_count += 1
            else:
                result = apply_patches(current_output, [proposal.patch])
                current_output = result.patched_text
                applied += result.applied_count
                rejected_count += len(result.rejected)

        verifier_result = verifier(
            output_md_text=current_output,
            task_dir=task_dir,
        )
        reward_after = verifier_result.reward
        current_details = verifier_result.details

        iterations.append(
            RemediationIteration(
                iteration=iteration_num,
                patches_applied=applied,
                patches_rejected=rejected_count,
                reward_before=reward_before,
                reward_after=reward_after,
            )
        )

        # Any criterion that attempted+exhausted but still failing → HITL now.
        # Rubric-aware resolution means proposals target resolved sections (not
        # dimension ids), so compare on criterion alone — a criterion is "still
        # failing" if the verifier lists it again under any dimension.
        still_unsatisfied_criteria = {c for _, c, _ in _collect_unsatisfied(current_details)}
        for p in proposals:
            key = (p.patch.section_id, p.criterion)
            if (
                p.criterion in still_unsatisfied_criteria
                and attempt_count.get(key, 0) >= cfg.max_attempts_per_criterion
            ):
                hitl.append(
                    HitlItem(
                        section_id=p.patch.section_id,
                        criterion=p.criterion,
                        evidence=p.evidence,
                        suggested_resolution=p.rationale,
                        attempt_count=attempt_count[key],
                    )
                )

        if on_iteration is not None:
            should_continue = on_iteration(iterations[-1])
            if not should_continue:
                return RemediationResult(
                    iterations=tuple(iterations),
                    hitl_items=tuple(hitl),
                    stop_reason="interactive_stop",
                    final_reward=reward_after,
                    final_output_text=current_output,
                )

        if cfg.target_reward is not None and reward_after >= cfg.target_reward:
            return RemediationResult(
                iterations=tuple(iterations),
                hitl_items=tuple(hitl),
                stop_reason="target_reached",
                final_reward=reward_after,
                final_output_text=current_output,
            )

        delta = reward_after - reward_before
        reward_before = reward_after

        if abs(delta) < cfg.plateau_threshold:
            return RemediationResult(
                iterations=tuple(iterations),
                hitl_items=tuple(hitl),
                stop_reason="plateau",
                final_reward=reward_after,
                final_output_text=current_output,
            )

    return RemediationResult(
        iterations=tuple(iterations),
        hitl_items=tuple(hitl),
        stop_reason="max_iterations",
        final_reward=reward_before,
        final_output_text=current_output,
    )
