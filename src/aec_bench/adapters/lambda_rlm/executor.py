# ABOUTME: Plan executor for the lambda-rlm adapter.
# ABOUTME: Walks the execution plan tree, dispatches extract/review/generate calls per section.

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

from aec_bench.adapters.advisor import default_advise
from aec_bench.adapters.lambda_rlm.combinators import split_text
from aec_bench.adapters.lambda_rlm.compose_bridge import render_compose_section
from aec_bench.adapters.lambda_rlm.config import LambdaRlmConfig, TemplateMeta
from aec_bench.adapters.lambda_rlm.consistency import aggregate_consistency, vote_merge
from aec_bench.adapters.lambda_rlm.prompts import (
    build_extraction_prompt,
    build_generation_prompt,
    build_reduce_prompt,
    build_structure_retry_guidance,
)
from aec_bench.adapters.lambda_rlm.review import run_review
from aec_bench.adapters.lambda_rlm.state import (
    ExecutionPlan,
    PlanState,
    SectionPlan,
)
from aec_bench.adapters.lambda_rlm.structure_validator import (
    StructureValidationResult,
    validate_section_structure,
)
from aec_bench.adapters.lambda_rlm.uncertainty import RunningStats, compute_joint_score
from aec_bench.adapters.rlm.client import RlmClient, RlmCompletionResponse, RlmMessage
from aec_bench.adapters.rlm.parallel import parallel
from aec_bench.contracts.advisor import AdvisorRequest
from aec_bench.contracts.constitution import (
    InformationMinimalityParams,
    SourceFidelityParams,
)
from aec_bench.contracts.repl import OutputField
from aec_bench.contracts.rubric import Rubric
from aec_bench.templates.report.session import ReportSession
from aec_bench.templates.report.sources import resolve_source_label

_log = logging.getLogger(__name__)

_PLANNING_SYSTEM_PROMPT = (
    "Extract the requested report facts into a JSON object keyed by the requested slots. "
    "Use only the provided sources and their declared precedence. Do not invent values. "
    "Leave unsupported slots empty and follow the task's gap policy."
)
_SCOPE_EVOLUTION_SYSTEM_PROMPT = (
    "Summarise how the report requirements changed across the supplied sources. "
    "Identify explicit decisions, unresolved conflicts, and exclusions. Follow the declared "
    "source precedence. Ground each conclusion in source text; do not infer agreement."
)
_BACK_BRIEF_SYSTEM_PROMPT = (
    "Summarise reusable phrasing and structure from the reference documents by requested topic. "
    "Do not transfer their case-specific facts into the active report. "
    "Return a JSON object keyed by topic; use an empty string where no pattern is supported."
)


class PlanExecutor:
    """Executes a lambda-rlm plan: extract → review → generate for each section."""

    def __init__(
        self,
        *,
        client: RlmClient,
        model: str,
        template: ReportSession,
        source_docs: dict[str, str],
        config: LambdaRlmConfig,
        trajectory_callback: Any | None = None,
        source_fidelity: SourceFidelityParams | None = None,
        information_minimality: InformationMinimalityParams | None = None,
        rubric: Rubric | None = None,
        boilerplate_fragments: dict[str, Any] | None = None,
        template_meta: TemplateMeta | None = None,
        sandbox: DocumentSandbox | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._template = template
        self._source_docs = source_docs
        self._config = config
        self._max_workers = config.max_parallel_workers
        self._cb = trajectory_callback
        self._source_fidelity = source_fidelity
        self._information_minimality = information_minimality
        self._rubric = rubric or template.rubric
        self._boilerplate_fragments = boilerplate_fragments or {}
        self._template_meta = template_meta
        self._sandbox = sandbox
        self._stderr = sys.stderr
        self._state_lock = __import__("threading").Lock()
        self._token_stats = RunningStats()
        self._advisor_calls = 0

    def execute(self, plan: ExecutionPlan, *, state: PlanState | None = None) -> PlanState:
        """Run the full plan and return final state."""
        state = state if state is not None else PlanState(estimated_calls=plan.total_estimated_calls)

        self._emit(
            "plan",
            f"{plan.active_section_count} sections, "
            f"{len(plan.skipped_sections)} skipped, "
            f"~{plan.total_estimated_calls} estimated calls",
        )

        self._run_planning_phase(state)  # no-op unless agentic + enabled

        for section_id in plan.section_order:
            section_plan = plan.section_plans[section_id]
            state.current_section = section_id

            # Compose-mode sections short-circuit the extract/review/generate
            # pipeline — boilerplate fragments are looked up declaratively and
            # only fill/generated blocks make LLM calls (via the bridge).
            if self._is_compose_section(section_id):
                state.phase = "compose"
                self._compose_section(section_id, state)
                continue

            # Phase 2: Extract
            state.phase = "extract"
            self._extract_section(section_plan, state)

            # Phase 3: Review
            should_review, reason = self._should_run_review(section_id, state)
            self._emit("review_decision", f"{section_id}: {reason}")
            if should_review:
                state.phase = "review"
                self._review_section(section_id, section_plan, state)

            # Phase 4: Generate
            state.phase = "generate"
            self._generate_section(section_id, state)

        if self._config.review.enabled and self._config.review.trigger != "never" and self._rubric:
            result, tokens = run_review(
                client=self._client,
                model=self._model,
                section_title="Complete report",
                writing_guidance=[self._criteria_text(section) for section in self._template.schema.sections],
                input_sources=list(self._source_docs),
                extracted_data=self._template.submit().sections,
                dependency_summaries={},
                source_fidelity=self._source_fidelity,
            )
            state.reviews["__report__"] = result
            state.llm_calls += 1
            state.tokens_used += sum(tokens)
            if self._cb:
                self._cb("report_review", None, None, state)
        state.phase = "complete"
        state.current_section = None
        self._emit(
            "done",
            f"{state.llm_calls} calls, {state.tokens_used:,} tokens",
        )
        return state

    def _emit(self, tag: str, message: str) -> None:
        """Write a real-time progress line to stderr."""
        self._stderr.write(f"[{tag:12s}] {message}\n")
        self._stderr.flush()

    def _run_planning_phase(self, state: PlanState) -> None:
        """One LLM turn upfront to populate compose_scratchpad.

        Gated by config.compose.mode == 'agentic' AND
        config.planning_phase.enabled. No-op otherwise.
        """
        if self._config.compose.mode != "agentic":
            return
        if not self._config.planning_phase.enabled:
            return
        slots = self._config.planning_phase.extract_slots
        sources = self._config.planning_phase.sources
        if not slots:
            return

        state.phase = "planning"
        self._emit(
            "planning",
            f"seeding {len(slots)} slots from {len(sources)} source(s)",
        )

        source_bodies = []
        for label in sources:
            body = self._resolve_source(label)
            if body:
                source_bodies.append(f"### Source: {label}\n{body}")
        sources_block = "\n\n".join(source_bodies) if source_bodies else "(no sources)"

        slot_list = ", ".join(slots)
        prompt = (
            f"Extract the following slots from the sources. Return JSON only.\n\n"
            f"Slots: {slot_list}\n\n"
            f"{sources_block}\n\n"
            f"Respond with a JSON object mapping each slot name to a short value "
            f"(or empty string when the source doesn't state it)."
        )

        guidance = self._template_meta.planning_guidance if self._template_meta else None
        planning_system_prompt = _PLANNING_SYSTEM_PROMPT
        if guidance:
            planning_system_prompt = planning_system_prompt + f" Domain context: {guidance}"
        response = self._client.generate(
            model=self._model,
            messages=[RlmMessage(role="user", content=prompt)],
            system_prompt=planning_system_prompt,
        )
        state.llm_calls += 1
        state.tokens_used += response.input_tokens + response.output_tokens

        from aec_bench.adapters.lambda_rlm.compose_bridge import _extract_json_object

        parsed = _extract_json_object(response.output_text)
        # Only non-empty values go into the scratchpad — empty-string slots
        # fall back to per-block resolution.
        for slot, value in parsed.items():
            if slot in slots and value:
                state.compose_scratchpad[slot] = value

        self._emit(
            "planning",
            f"scratchpad seeded with {len(state.compose_scratchpad)} / {len(slots)} slots",
        )

        if self._cb:
            self._cb("planning", None, None, state)

        self._run_scope_evolution_phase(state)
        self._run_back_brief_phase(state)

    def _run_scope_evolution_phase(self, state: PlanState) -> None:
        """Planning pass that reads the primary source and produces an
        descriptive summary of requirement changes on the scratchpad under
        the reserved key `_scope_evolution`.

        Gated by config.compose.mode == 'agentic' AND
        config.planning_phase.scope_evolution.enabled. No-op otherwise.
        """
        if self._config.compose.mode != "agentic":
            return
        se_cfg = self._config.planning_phase.scope_evolution
        if not se_cfg.enabled:
            return
        if not se_cfg.sources:
            return

        state.phase = "scope_evolution"
        self._emit(
            "scope_evolution",
            f"summarising scope arc across {len(se_cfg.sources)} source(s)",
        )

        source_bodies = []
        for label in se_cfg.sources:
            body = self._resolve_source(label)
            if body:
                source_bodies.append(f"### Source: {label}\n{body}")
        if not source_bodies:
            self._emit("scope_evolution", "no source content found — skipping")
            return

        prompt = (
            "Summarise changes in report requirements across these sources. "
            "Identify explicit decisions, unresolved conflicts, and exclusions. "
            "If the requirements did not change, state that explicitly. "
            "Return a plain-text summary.\n\n" + "\n\n".join(source_bodies)
        )

        model = se_cfg.model or self._model
        scope_evolution_system_prompt = _SCOPE_EVOLUTION_SYSTEM_PROMPT
        if self._template_meta and self._template_meta.planning_guidance:
            scope_evolution_system_prompt = (
                scope_evolution_system_prompt + f" Domain context: {self._template_meta.planning_guidance}"
            )
        response = self._client.generate(
            model=model,
            messages=[RlmMessage(role="user", content=prompt)],
            system_prompt=scope_evolution_system_prompt,
            max_output_tokens=se_cfg.max_output_tokens,
        )
        state.llm_calls += 1
        state.tokens_used += response.input_tokens + response.output_tokens

        digest = response.output_text.strip()
        if digest:
            state.compose_scratchpad["_scope_evolution"] = digest

        self._emit(
            "scope_evolution",
            f"digest seeded ({len(digest)} chars)" if digest else "digest empty — skipping",
        )

        if self._cb:
            self._cb("scope_evolution", None, None, state)

    def _run_back_brief_phase(self, state: PlanState) -> None:
        """Second planning pass — summarise reference docs into per-topic digest.

        Gated by config.compose.mode == 'agentic' AND
        config.planning_phase.back_brief.enabled. No-op otherwise.
        """
        if self._config.compose.mode != "agentic":
            return
        bb_cfg = self._config.planning_phase.back_brief
        if not bb_cfg.enabled:
            return
        if not bb_cfg.sources or not bb_cfg.topics:
            return

        state.phase = "back_brief"
        self._emit(
            "back_brief",
            f"summarising {len(bb_cfg.sources)} reference(s) across {len(bb_cfg.topics)} topic(s)",
        )

        source_bodies = []
        for label in bb_cfg.sources:
            body = self._resolve_source(label)
            if body:
                source_bodies.append(f"### Reference: {label}\n{body}")
        if not source_bodies:
            self._emit("back_brief", "no reference content found — skipping")
            return

        topic_list = ", ".join(bb_cfg.topics)
        prompt = (
            f"Extract REUSABLE PHRASING PATTERNS by topic from these "
            f"reference reports. Describe how the topic is typically worded "
            f"(clauses, tone, register, formatting) — do NOT summarise or "
            f"carry across project-specific scope, deliverables, "
            f"personnel, dollar amounts, rates, dates, or standards.\n\n"
            f"Topics: {topic_list}\n\n"
            + "\n\n".join(source_bodies)
            + "\n\nReturn JSON mapping each topic to a phrasing digest."
        )

        model = bb_cfg.model or self._model
        back_brief_system_prompt = _BACK_BRIEF_SYSTEM_PROMPT
        if self._template_meta and self._template_meta.planning_guidance:
            back_brief_system_prompt = (
                back_brief_system_prompt + f" Domain context: {self._template_meta.planning_guidance}"
            )
        response = self._client.generate(
            model=model,
            messages=[RlmMessage(role="user", content=prompt)],
            system_prompt=back_brief_system_prompt,
            max_output_tokens=bb_cfg.max_output_tokens,
        )
        state.llm_calls += 1
        state.tokens_used += response.input_tokens + response.output_tokens

        from aec_bench.adapters.lambda_rlm.compose_bridge import _extract_json_object

        parsed = _extract_json_object(response.output_text)
        digest = {t: parsed.get(t, "") for t in bb_cfg.topics if parsed.get(t)}
        state.compose_scratchpad["_back_brief"] = digest

        self._emit(
            "back_brief",
            f"digest seeded with {len(digest)} / {len(bb_cfg.topics)} topics",
        )

        if self._cb:
            self._cb("back_brief", None, None, state)

    def _is_compose_section(self, section_id: str) -> bool:
        """Return True if the schema declares this section as compose-mode with blocks."""
        for section in self._template._schema.sections:
            if section.id == section_id:
                return section.generation_mode == "compose" and section.blocks is not None
        return False

    def _compose_section(self, section_id: str, state: PlanState) -> None:
        """Render a compose-mode section through the bridge and fold stats into state."""
        section = next(s for s in self._template._schema.sections if s.id == section_id)
        blocks = section.blocks
        if blocks is None:
            msg = f"Compose section {section_id} is missing blocks"
            raise ValueError(msg)

        voice = self._template_meta.voice if self._template_meta else None
        domain = self._template_meta.domain if self._template_meta else None

        content, trace, stats = render_compose_section(
            blocks=blocks,
            fragments=self._boilerplate_fragments,
            client=self._client,
            model=self._model,
            source_resolver=self._resolve_source,
            scratchpad=(state.compose_scratchpad if self._config.compose.mode == "agentic" else None),
            voice_override=voice,
            domain_override=domain,
            section_guidance=self._criteria_text(section),
            sandbox=self._sandbox,
        )

        state.sections[section_id] = content
        state.composition_traces[section_id] = [
            {
                "block_index": entry.block_index,
                "block_type": entry.block_type,
                "text": entry.text,
                "start_offset": entry.start_offset,
                "end_offset": entry.end_offset,
                "ref": entry.ref,
                "prompt": entry.prompt,
                "sources": list(entry.sources),
                "resolved_slots": dict(entry.resolved_slots),
                "provenance": list(entry.provenance),
                "slot_provenance": {k: list(v) for k, v in entry.slot_provenance.items()},
                "declared_provenance": list(entry.declared_provenance),
                "fetched_provenance": list(entry.fetched_provenance),
            }
            for entry in trace
        ]
        state.llm_calls += stats.calls
        state.tokens_used += stats.input_tokens + stats.output_tokens

        fields = self._template.schema.sections
        section = next(s for s in fields if s.id == section_id)
        values = _parse_json_response(content)
        if not values or not set(values) & section.fields.keys():
            if len(section.fields) == 1 and next(iter(section.fields.values())).dtype in {"str", "table"}:
                values = {next(iter(section.fields)): content}
            else:
                values = {"content": content}
        result = self._template.fill_section(section_id, values)
        if not result.success:
            state.validation_failures[section_id] = result.error

        status = self._template.get_status()
        self._emit(
            "compose",
            f"{section_id} "
            f"({stats.calls} calls, {stats.input_tokens:,} in / {stats.output_tokens:,} out) "
            f"[{status.completed_sections}/{status.total_sections} sections filled]",
        )

        if self._cb:
            self._cb("compose", section_id, None, state)

    def _extract_section(self, section_plan: SectionPlan, state: PlanState) -> None:
        """Run leaf extraction (and reduce if chunked) for all sources in a section."""
        section_id = section_plan.section_id
        state._uncertainty_scoring_active = self._config.uncertainty_scoring_active
        state.extractions.setdefault(section_id, {})

        ops_by_source = self._group_leaf_ops_by_source(section_plan)

        section_info = self._get_section_info(section_id)
        dependency_context = self._get_dependency_context(section_id)

        # Run source extractions in parallel when multiple sources
        source_items = list(ops_by_source.items())
        if len(source_items) > 1 and self._max_workers > 1:

            def extract_call(
                source_label: str,
                source_ops: list[Any],
            ) -> Callable[[], tuple[str, dict[str, Any]]]:
                return lambda: self._extract_source(
                    section_id=section_id,
                    section_info=section_info,
                    source_label=source_label,
                    ops=source_ops,
                    dependency_context=dependency_context,
                    state=state,
                )

            results = parallel(
                [extract_call(source_label, source_ops) for source_label, source_ops in source_items],
                max_workers=self._max_workers,
            )
            for result in results:
                if not isinstance(result, tuple):
                    continue  # ParallelError — skip
                label, extracted = result
                if extracted:
                    state.extractions[section_id][label] = extracted
        else:
            for source_label, ops in source_items:
                label, extracted = self._extract_source(
                    section_id=section_id,
                    section_info=section_info,
                    source_label=source_label,
                    ops=ops,
                    dependency_context=dependency_context,
                    state=state,
                )
                if extracted:
                    state.extractions[section_id][label] = extracted

        self._emit_confidence_summary(
            section_id=section_id,
            source_count=len(source_items),
            state=state,
        )
        self._update_uncertainty_scores(
            section_id=section_id,
            source_count=len(source_items),
            state=state,
        )

    def _group_leaf_ops_by_source(
        self,
        section_plan: SectionPlan,
    ) -> dict[str, list[Any]]:
        """Group leaf operations by source label for a section."""
        ops_by_source: dict[str, list[Any]] = {}
        for op in section_plan.leaf_ops:
            ops_by_source.setdefault(op.source, []).append(op)
        return ops_by_source

    def _extract_source(
        self,
        *,
        section_id: str,
        section_info: dict[str, Any],
        source_label: str,
        ops: list[Any],
        dependency_context: dict[str, str],
        state: PlanState,
    ) -> tuple[str, dict[str, Any]]:
        """Extract one source, using reduce only when the source was chunked."""
        source_text = self._resolve_source(source_label)
        if not source_text:
            return source_label, {}

        if len(ops) == 1 and ops[0].total_chunks == 1:
            extracted, consistency = self._extract_source_chunk(
                section_info=section_info,
                source_label=source_label,
                chunk_text=source_text,
                dependency_context=dependency_context,
                state=state,
            )
            self._record_source_consistency(
                section_id=section_id,
                source_label=source_label,
                consistency=consistency,
                state=state,
            )
            self._finalize_source_confidence(
                section_id=section_id,
                source_label=source_label,
                expected_chunks=1,
                state=state,
            )
            return source_label, extracted

        chunks = split_text(
            source_text,
            k_star=ops[0].total_chunks,
            tau_star=self._config.planner.context_window_chars,
        )
        chunk_results: list[dict[str, Any]] = []
        chunk_consistency: list[float] = []
        for chunk in chunks:
            extracted, consistency = self._extract_source_chunk(
                section_info=section_info,
                source_label=source_label,
                chunk_text=chunk,
                dependency_context=dependency_context,
                state=state,
            )
            chunk_results.append(extracted)
            if consistency is not None:
                chunk_consistency.append(consistency)

        if chunk_consistency:
            self._record_source_consistency(
                section_id=section_id,
                source_label=source_label,
                consistency=sum(chunk_consistency) / len(chunk_consistency),
                state=state,
            )

        self._finalize_source_confidence(
            section_id=section_id,
            source_label=source_label,
            expected_chunks=len(chunks),
            state=state,
        )

        merged = self._reduce(
            section_info=section_info,
            source_label=source_label,
            chunk_results=chunk_results,
            state=state,
        )
        return source_label, merged

    def _extract_source_chunk(
        self,
        *,
        section_info: dict[str, Any],
        source_label: str,
        chunk_text: str,
        dependency_context: dict[str, str],
        state: PlanState,
    ) -> tuple[dict[str, Any], float | None]:
        """Extract one chunk, optionally fanning out to K candidates."""
        if self._config.extract.k_candidates > 1:
            merged, consistency = self._leaf_extract_k(
                section_info=section_info,
                source_label=source_label,
                chunk_text=chunk_text,
                dependency_context=dependency_context,
                state=state,
                k=self._config.extract.k_candidates,
                temperature=self._config.extract.temperature,
            )
            return merged, consistency

        extracted = self._leaf_extract(
            section_info=section_info,
            source_label=source_label,
            chunk_text=chunk_text,
            dependency_context=dependency_context,
            state=state,
        )
        return extracted, None

    def _record_source_consistency(
        self,
        *,
        section_id: str,
        source_label: str,
        consistency: float | None,
        state: PlanState,
    ) -> None:
        """Persist a per-source consistency score when K extraction is active."""
        if consistency is None:
            return

        with self._state_lock:
            state.extraction_consistency.setdefault(section_id, {})[source_label] = consistency

    def _coerce_confidence(self, value: Any) -> float | None:
        """Coerce a model-emitted confidence value into the [0, 1] interval."""
        if value is None:
            return None

        try:
            confidence = float(value)
        except (TypeError, ValueError):
            _log.warning("Malformed confidence value %r; ignoring", value)
            return None

        if confidence < 0.0 or confidence > 1.0:
            _log.warning("Out-of-range confidence value %r; clamping to [0, 1]", value)
            confidence = max(0.0, min(1.0, confidence))

        return confidence

    def _finalize_source_confidence(
        self,
        *,
        section_id: str,
        source_label: str,
        expected_chunks: int,
        state: PlanState,
    ) -> None:
        """Promote chunk-level confidence to source-level confidence when possible."""
        with self._state_lock:
            chunk_values = list(
                state.extraction_confidence_chunks.get(section_id, {}).get(source_label, []),
            )

            if expected_chunks == 1:
                if len(chunk_values) == 1:
                    state.extraction_confidence.setdefault(section_id, {})[source_label] = chunk_values[0]
                return

            if len(chunk_values) == expected_chunks:
                state.extraction_confidence.setdefault(section_id, {})[source_label] = min(
                    chunk_values,
                )
                if section_id in state.extraction_confidence_missing:
                    state.extraction_confidence_missing[section_id].pop(source_label, None)
                    if not state.extraction_confidence_missing[section_id]:
                        state.extraction_confidence_missing.pop(section_id, None)
                return

            state.extraction_confidence_missing.setdefault(section_id, {})[source_label] = "partial_chunks_missing"

    def _emit_confidence_summary(
        self,
        *,
        section_id: str,
        source_count: int,
        state: PlanState,
    ) -> None:
        """Emit a per-section summary of extracted confidence values."""
        source_confidence = state.extraction_confidence.get(section_id, {})
        values = list(source_confidence.values())
        missing_count = len(state.extraction_confidence_missing.get(section_id, {}))

        if values:
            suffix = f"({len(values)}/{source_count} sources"
            if missing_count:
                suffix += f", {missing_count} missing"
            suffix += ")"
            self._emit(
                "confidence",
                f"{section_id}: mean={sum(values) / len(values):.2f}, min={min(values):.2f} {suffix}",
            )
            return

        if missing_count:
            self._emit(
                "confidence",
                f"{section_id}: no valid confidence ({missing_count}/{source_count} missing)",
            )

    def _update_uncertainty_scores(
        self,
        *,
        section_id: str,
        source_count: int,
        state: PlanState,
    ) -> None:
        """Compute per-source uncertainty scores when scoring is active."""
        state._uncertainty_scoring_active = self._config.uncertainty_scoring_active
        if not self._config.uncertainty_scoring_active:
            return

        if self._token_stats.n < self._config.uncertainty.min_samples:
            return

        source_scores: dict[str, float] = {}
        source_tokens = state.leaf_output_tokens.get(section_id, {})
        source_confidence = state.extraction_confidence.get(section_id, {})

        for source_label, token_counts in source_tokens.items():
            confidence = source_confidence.get(source_label)
            if confidence is None or not token_counts:
                continue

            mean_tokens = sum(token_counts) / len(token_counts)
            z_len = self._token_stats.z_score(mean_tokens)
            source_scores[source_label] = compute_joint_score(
                confidence,
                z_len,
                self._config.uncertainty.lambda_,
                self._config.uncertainty.min_confidence_eps,
            )

        with self._state_lock:
            if source_scores:
                state.uncertainty_scores[section_id] = source_scores
            else:
                state.uncertainty_scores.pop(section_id, None)
            state._uncertainty_population_stats = self._token_stats.as_dict()

        if source_scores:
            self._emit(
                "uncertainty",
                f"{section_id}: max={max(source_scores.values()):.2f} "
                f"({len(source_scores)}/{source_count} sources scored)",
            )

    def _section_max_uncertainty(
        self,
        section_id: str,
        state: PlanState,
    ) -> float | None:
        """Return the maximum source uncertainty score for a section, if any."""
        scores = state.uncertainty_scores.get(section_id, {})
        if not scores:
            return None
        return max(scores.values())

    def _section_mean_consistency(
        self,
        section_id: str,
        state: PlanState,
    ) -> float | None:
        """Return the mean source consistency score for a section, if any."""
        scores = state.extraction_consistency.get(section_id, {})
        if not scores:
            return None
        return sum(scores.values()) / len(scores)

    def _should_run_review(
        self,
        section_id: str,
        state: PlanState,
    ) -> tuple[bool, str]:
        """Return whether review should run for a section and the decision reason."""
        review_config = self._config.review
        if not review_config.enabled:
            return False, "review disabled"

        trigger = review_config.trigger
        if trigger == "always":
            return True, "review trigger: always"
        if trigger == "never":
            return False, "review trigger: never"

        max_uncertainty = self._section_max_uncertainty(section_id, state)
        mean_consistency = self._section_mean_consistency(section_id, state)

        if trigger == "uncertainty":
            if max_uncertainty is None:
                return (
                    True,
                    "review trigger: no uncertainty data, falling back to always",
                )

            threshold = self._config.uncertainty.review_joint_threshold
            should_run = max_uncertainty > threshold
            action = "run" if should_run else "skip"
            return (
                should_run,
                f"review {action}: uncertainty={max_uncertainty:.2f} threshold={threshold:.2f}",
            )

        if trigger == "consistency":
            if mean_consistency is None:
                return (
                    True,
                    "review trigger: no consistency data, falling back to always",
                )

            threshold = review_config.consistency_threshold
            should_run = mean_consistency < threshold
            action = "run" if should_run else "skip"
            return (
                should_run,
                f"review {action}: consistency={mean_consistency:.2f} threshold={threshold:.2f}",
            )

        if trigger == "both":
            if max_uncertainty is None:
                return (
                    True,
                    "review trigger: no uncertainty data, falling back to always",
                )
            if mean_consistency is None:
                return (
                    True,
                    "review trigger: no consistency data, falling back to always",
                )

            uncertainty_threshold = self._config.uncertainty.review_joint_threshold
            consistency_threshold = review_config.consistency_threshold
            should_run = max_uncertainty > uncertainty_threshold and mean_consistency < consistency_threshold
            action = "run" if should_run else "skip"
            return (
                should_run,
                f"review {action}: uncertainty={max_uncertainty:.2f} "
                f"threshold={uncertainty_threshold:.2f}, "
                f"consistency={mean_consistency:.2f} "
                f"threshold={consistency_threshold:.2f}",
            )

        return True, f"review trigger: unsupported {trigger!r}, falling back to always"

    def _leaf_extract_k(
        self,
        *,
        section_info: dict[str, Any],
        source_label: str,
        chunk_text: str,
        dependency_context: dict[str, str],
        state: PlanState,
        k: int,
        temperature: float,
    ) -> tuple[dict[str, Any], float]:
        """Run K extraction calls for one chunk, then vote-merge the candidates."""
        from concurrent.futures import ThreadPoolExecutor

        section_id = section_info["id"]
        confidence_start = len(
            state.extraction_confidence_chunks.get(section_id, {}).get(source_label, []),
        )
        max_workers = max(1, min(k, self._max_workers))

        def _one_call(_: int) -> dict[str, Any]:
            return self._leaf_extract(
                section_info=section_info,
                source_label=source_label,
                chunk_text=chunk_text,
                dependency_context=dependency_context,
                state=state,
                temperature=temperature,
            )

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            candidates = list(pool.map(_one_call, range(k)))

        self._collapse_chunk_confidence(
            section_id=section_id,
            source_label=source_label,
            start_index=confidence_start,
            candidate_count=k,
            state=state,
        )
        self._record_extraction_candidates(
            section_id=section_id,
            source_label=source_label,
            candidates=candidates,
            state=state,
        )

        merged, per_field = vote_merge(candidates)
        return merged, aggregate_consistency(per_field)

    def _collapse_chunk_confidence(
        self,
        *,
        section_id: str,
        source_label: str,
        start_index: int,
        candidate_count: int,
        state: PlanState,
    ) -> None:
        """Replace per-candidate confidence with one mean confidence for the chunk."""
        with self._state_lock:
            section_chunks = state.extraction_confidence_chunks.get(section_id)
            if not section_chunks or source_label not in section_chunks:
                return

            chunk_values = section_chunks[source_label]
            candidate_values = list(chunk_values[start_index:])
            del chunk_values[start_index:]

            if len(candidate_values) == candidate_count:
                chunk_values.append(sum(candidate_values) / candidate_count)

            if not chunk_values:
                section_chunks.pop(source_label, None)
                if not section_chunks:
                    state.extraction_confidence_chunks.pop(section_id, None)

    def _record_extraction_candidates(
        self,
        *,
        section_id: str,
        source_label: str,
        candidates: list[dict[str, Any]],
        state: PlanState,
    ) -> None:
        """Persist raw extraction candidates when the artifact flag is enabled."""
        if not self._config.extract.keep_candidates_artifact:
            return

        with self._state_lock:
            if state.extraction_candidates is None:
                state.extraction_candidates = {}
            state.extraction_candidates.setdefault(section_id, {}).setdefault(
                source_label,
                [],
            ).extend(candidates)

    def _leaf_extract(
        self,
        *,
        section_info: dict[str, Any],
        source_label: str,
        chunk_text: str,
        dependency_context: dict[str, str],
        state: PlanState,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Run a single leaf extraction call."""
        priority_map = self._get_source_priority(section_info["id"])
        source_priority = priority_map.get(source_label)
        prompt = build_extraction_prompt(
            section_title=section_info["title"],
            generation_mode=section_info["generation_mode"],
            writing_guidance=section_info["writing_guidance"],
            source_label=source_label,
            chunk_text=chunk_text,
            dependency_context=dependency_context,
            source_fidelity=self._source_fidelity,
            information_minimality=self._information_minimality,
            source_priority=source_priority,
        )

        response = self._client.generate(
            model=self._model,
            messages=[RlmMessage(role="user", content=prompt)],
            system_prompt=None,
            temperature=temperature if temperature is not None else self._config.extract.temperature,
        )
        with self._state_lock:
            section_id = section_info["id"]
            state.llm_calls += 1
            state.tokens_used += response.input_tokens + response.output_tokens
            state.leaf_output_tokens.setdefault(section_id, {}).setdefault(
                source_label,
                [],
            ).append(response.output_tokens)
            self._token_stats.push(response.output_tokens)
            state._uncertainty_population_stats = self._token_stats.as_dict()

        extracted = _parse_json_response(response.output_text)
        raw_confidence = extracted.pop("__confidence__", None)
        confidence = self._coerce_confidence(raw_confidence)

        with self._state_lock:
            if raw_confidence is None:
                state.extraction_confidence_missing.setdefault(section_id, {})[source_label] = "missing_key"
            elif confidence is None:
                state.extraction_confidence_missing.setdefault(section_id, {})[source_label] = "parse_failure"
            else:
                state.extraction_confidence_chunks.setdefault(section_id, {}).setdefault(
                    source_label,
                    [],
                ).append(confidence)

        fields = ", ".join(list(extracted.keys())[:5])
        self._emit(
            "extract",
            f"{section_info['id']} ← {source_label} "
            f"({response.input_tokens:,} in / {response.output_tokens:,} out) "
            f"fields: [{fields}]",
        )

        if self._cb:
            self._cb("leaf_extract", section_info["id"], source_label, state)

        return extracted

    def _reduce(
        self,
        *,
        section_info: dict[str, Any],
        source_label: str,
        chunk_results: list[dict[str, Any]],
        state: PlanState,
    ) -> dict[str, Any]:
        """Merge chunked extraction results via a reduce LLM call."""
        prompt = build_reduce_prompt(
            section_title=section_info["title"],
            source_label=source_label,
            extraction_results=chunk_results,
        )

        response = self._client.generate(
            model=self._model,
            messages=[RlmMessage(role="user", content=prompt)],
            system_prompt=None,
        )
        with self._state_lock:
            state.llm_calls += 1
            state.tokens_used += response.input_tokens + response.output_tokens

        self._emit(
            "reduce",
            f"{section_info['id']} ← {source_label} "
            f"({len(chunk_results)} chunks merged, "
            f"{response.input_tokens:,} in / {response.output_tokens:,} out)",
        )

        if self._cb:
            self._cb("reduce", section_info["id"], source_label, state)

        return _parse_json_response(response.output_text)

    def _review_section(
        self,
        section_id: str,
        section_plan: SectionPlan,
        state: PlanState,
    ) -> None:
        """Run contract review for a section's extractions."""
        section_info = self._get_section_info(section_id)
        merged_data = _merge_source_extractions(
            state.extractions.get(section_id, {}),
        )
        dependency_summaries = self._get_dependency_summaries(section_id)

        source_priority = self._get_source_priority(section_id)
        result, tokens = run_review(
            client=self._client,
            model=self._model,
            section_title=section_info["title"],
            writing_guidance=section_info["writing_guidance"],
            input_sources=section_plan.sources,
            extracted_data=merged_data,
            dependency_summaries=dependency_summaries,
            source_fidelity=self._source_fidelity,
            source_priority=source_priority,
        )
        state.llm_calls += 1
        state.tokens_used += tokens[0] + tokens[1]
        state.reviews[section_id] = result

        status_label = result.status
        detail = ""
        if result.gaps:
            detail = f" gaps: {result.gaps[:3]}"
        if result.reextract_sources:
            detail += f" reextract: {result.reextract_sources}"
        self._emit(
            "review",
            f"{section_id} → {status_label} ({tokens[0]:,} in / {tokens[1]:,} out){detail}",
        )

        if self._cb:
            self._cb("review", section_id, None, state)

        # Each source has its own retry count; a supplement pass is bounded too.
        source_attempts: dict[str, int] = {}
        for _ in range(self._config.review.max_supplements_per_section):
            if not result.needs_action:
                break
            changed = False
            for source_label in dict.fromkeys(result.reextract_sources):
                if source_label not in section_plan.sources:
                    continue
                if source_attempts.get(source_label, 0) >= self._config.review.max_retries_per_source:
                    continue
                resolved = resolve_source_label(source_label, self._source_docs)
                if resolved.resolved is None:
                    continue
                source_attempts[source_label] = source_attempts.get(source_label, 0) + 1
                source_text = self._source_docs[resolved.resolved]
                guidance = result.supplement_guidance or ""
                extracted = self._leaf_extract(
                    section_info=section_info,
                    source_label=source_label,
                    chunk_text=source_text + "\nReview guidance: " + guidance,
                    dependency_context=self._get_dependency_context(section_id),
                    state=state,
                )
                state.extractions.setdefault(section_id, {}).setdefault(source_label, {}).update(extracted)
                changed = True
            if not changed:
                break
            result, tokens = run_review(
                client=self._client,
                model=self._model,
                section_title=section_info["title"],
                writing_guidance=section_info["writing_guidance"],
                input_sources=section_plan.sources,
                extracted_data=_merge_source_extractions(state.extractions.get(section_id, {})),
                dependency_summaries=dependency_summaries,
                source_fidelity=self._source_fidelity,
                source_priority=source_priority,
            )
            state.llm_calls += 1
            state.tokens_used += sum(tokens)
            state.reviews[section_id] = result
        config = self._config.advisor
        if result.needs_action and config and config.enabled and self._advisor_calls < config.max_uses:
            self._advisor_calls += 1
            state.advisor_calls += 1
            advice = default_advise(
                request=AdvisorRequest(
                    goal=f"Resolve report requirements for {section_info['title']}",
                    problem=str(result.gaps + result.risks),
                    attempt=str(source_attempts),
                ),
                context_messages=[
                    {"content": f"{sid}: {content}"}
                    for sid, content in list(state.sections.items())[-config.context_window :]
                ]
                + [
                    {
                        "content": self._criteria_text(
                            next(section for section in self._template.schema.sections if section.id == section_id)
                        )
                    }
                ],
                client=self._client,
                model=config.model,
                max_response_tokens=config.max_response_tokens,
                adapter_context=(
                    "Advice is guidance, not evidence or a verifier decision. Follow the task's source policy."
                ),
            )
            state.llm_calls += 1
            state.tokens_used += advice.input_tokens + advice.output_tokens
            state.advisor_input_tokens += advice.input_tokens
            state.advisor_output_tokens += advice.output_tokens
            if advice.response:
                state.advice[section_id] = advice.response.advice
            if self._cb:
                self._cb("advisor", section_id, None, state)

    def _generate_section(
        self,
        section_id: str,
        state: PlanState,
    ) -> None:
        """Generate a section, optionally with structure-enforcement retries.

        Fast path (enforcement disabled or no required fields): single generate
        call, identical behaviour to the pre-enforcement baseline.

        Enforcement path: generate → validate → retry up to max_retries with a
        gap-list addendum on the regeneration prompt. On budget exhaustion the
        last content is accepted and the unresolved result is recorded in state.
        """
        section_info = self._get_section_info(section_id)
        cfg = self._config.structure_enforcement
        required_fields = tuple(f for f in section_info.get("fields", {}).values() if f.required)

        # Fast path: enforcement off, or section has no required fields.
        if not cfg.enabled or not required_fields:
            content = self._generate_section_once(
                section_id=section_id,
                section_info=section_info,
                state=state,
                retry_addendum=None,
            )
            self._finalise_section(section_id, content, state)
            return

        # Enforcement path: generate, validate, retry up to max_retries.
        retry_addendum: str | None = None
        last_result: StructureValidationResult | None = None
        for attempt in range(cfg.max_retries + 1):
            content = self._generate_section_once(
                section_id=section_id,
                section_info=section_info,
                state=state,
                retry_addendum=retry_addendum,
                required_fields=required_fields,
            )
            if self._cb:
                self._cb(
                    "structure_validation_attempt",
                    section_id,
                    {
                        "section_id": section_id,
                        "attempt_index": attempt,
                        "required_field_count": len(required_fields),
                    },
                    state,
                )

            result = validate_section_structure(
                section_id=section_id,
                section_title=section_info["title"],
                content=content,
                required_fields=required_fields,
                client=self._client,
                model=cfg.validator_model,
            )
            state.tokens_used += result.validator_input_tokens + result.validator_output_tokens
            last_result = result

            if result.passed:
                if self._cb:
                    self._cb(
                        "structure_validation_pass",
                        section_id,
                        {
                            "section_id": section_id,
                            "attempt_index": attempt,
                            "input_tokens": result.validator_input_tokens,
                            "output_tokens": result.validator_output_tokens,
                        },
                        state,
                    )
                self._finalise_section(section_id, content, state)
                return

            # Failed — record retry count and prepare addendum if budget remains.
            if attempt < cfg.max_retries:
                state.structure_retries[section_id] = attempt + 1
                retry_addendum = build_structure_retry_guidance(
                    missing=result.missing,
                    malformed=result.malformed,
                )
                if self._cb:
                    self._cb(
                        "structure_validation_retry",
                        section_id,
                        {
                            "section_id": section_id,
                            "attempt_index": attempt,
                            "missing": [g.field_name for g in result.missing],
                            "malformed": [g.field_name for g in result.malformed],
                            "input_tokens": result.validator_input_tokens,
                            "output_tokens": result.validator_output_tokens,
                        },
                        state,
                    )

        # Budget exhausted — accept last content, record unresolved.
        assert last_result is not None  # the loop runs at least once
        state.structure_unresolved[section_id] = last_result
        if self._cb:
            self._cb(
                "structure_validation_unresolved",
                section_id,
                {
                    "section_id": section_id,
                    "final_missing": [g.field_name for g in last_result.missing],
                    "final_malformed": [g.field_name for g in last_result.malformed],
                    "total_retries": state.structure_retries.get(section_id, 0),
                },
                state,
            )
        self._finalise_section(section_id, content, state)

    def _generate_section_once(
        self,
        *,
        section_id: str,
        section_info: dict[str, Any],
        state: PlanState,
        retry_addendum: str | None,
        required_fields: tuple[OutputField, ...] = (),
    ) -> str:
        """Single generate call. Returns the produced content string.

        Builds the generation prompt from extracted data and dependency
        sections, optionally appends a retry addendum for enforcement
        retries, then dispatches to synthesis or direct generate.
        """
        merged_data = _merge_source_extractions(
            state.extractions.get(section_id, {}),
        )
        dependency_sections = {
            dep: state.sections[dep] for dep in self._template.get_dependencies(section_id) if dep in state.sections
        }

        # Pass review insights (gaps/risks) to generation if available.
        review = state.reviews.get(section_id)
        source_priority = self._get_source_priority(section_id)
        prompt = build_generation_prompt(
            section_title=section_info["title"],
            writing_guidance=section_info["writing_guidance"],
            extracted_data=merged_data,
            dependency_sections=dependency_sections,
            review_gaps=review.gaps if review else None,
            review_risks=review.risks if review else None,
            source_fidelity=self._source_fidelity,
            source_priority=source_priority,
            required_fields=required_fields if required_fields else None,
        )
        if section_info.get("fields"):
            prompt += "\nReturn a JSON object with the declared field names and types: " + str(
                {name: f.dtype for name, f in section_info["fields"].items()}
            )
        if retry_addendum:
            prompt = f"{prompt}\n\n{retry_addendum}"

        if section_id in state.advice:
            prompt += "\nAdvisory suggestions (not source evidence):\n" + state.advice[section_id]

        if self._should_synthesise(section_id):
            return self._synthesise_section_content(
                section_id=section_id,
                prompt=prompt,
                state=state,
            )

        response = self._client.generate(
            model=self._model,
            messages=[RlmMessage(role="user", content=prompt)],
            system_prompt=None,
        )
        state.llm_calls += 1
        state.tokens_used += response.input_tokens + response.output_tokens
        self._emit(
            "generate",
            f"{section_id} ({response.input_tokens:,} in / {response.output_tokens:,} out)",
        )
        return response.output_text

    def _finalise_section(
        self,
        section_id: str,
        content: str,
        state: PlanState,
    ) -> None:
        """Record content into state and emit completion events.

        Shared by the enforcement and non-enforcement paths so both
        produce identical state mutations and trajectory events.
        """
        state.sections[section_id] = content

        # Decode field maps, or bind prose to the sole declared text field.
        fields = self._template.schema.sections
        section = next(s for s in fields if s.id == section_id)
        values = _parse_json_response(content)
        if not values or not set(values) & section.fields.keys():
            if len(section.fields) == 1 and next(iter(section.fields.values())).dtype in {"str", "table"}:
                values = {next(iter(section.fields)): content}
            else:
                values = {"content": content}
        result = self._template.fill_section(section_id, values)
        if not result.success:
            state.validation_failures[section_id] = result.error

        status = self._template.get_status()
        self._emit(
            "generate",
            f"{section_id} [{status.completed_sections}/{status.total_sections} sections filled]",
        )

        if self._cb:
            self._cb("generate", section_id, None, state)

    def _should_synthesise(self, section_id: str) -> bool:
        fill_config = self._config.fill_section
        if fill_config.k_candidates <= 1:
            return False
        if fill_config.tournament_mode != "synthesis":
            return False
        if fill_config.apply_to_sections:
            return section_id in fill_config.apply_to_sections
        return True

    def _synthesise_section_content(
        self,
        *,
        section_id: str,
        prompt: str,
        state: PlanState,
    ) -> str:
        """Generate K candidates in parallel, then synthesise one unified section.

        K LLM calls run concurrently via a ThreadPoolExecutor bounded by the
        adapter's max_parallel_workers config. Thread safety: RlmClient
        implementations are assumed to be thread-safe (Anthropic/Bedrock
        boto3 clients are; ReplayRlmClient holds an internal lock).
        """
        from concurrent.futures import ThreadPoolExecutor

        from aec_bench.adapters.lambda_rlm.synthesis import (
            CandidateGeneration,
            synthesise_section,
        )
        from aec_bench.templates.report.criteria import build_criteria_bundle

        fill_config = self._config.fill_section
        k = fill_config.k_candidates
        max_workers = max(1, min(k, self._max_workers))

        def _one_call(i: int) -> tuple[int, RlmCompletionResponse]:
            response = self._client.generate(
                model=self._model,
                messages=[RlmMessage(role="user", content=prompt)],
                system_prompt=None,
                temperature=fill_config.temperature,
            )
            self._emit(
                "synthesise",
                f"{section_id} candidate {i + 1}/{k} ({response.input_tokens:,} in / {response.output_tokens:,} out)",
            )
            return i, response

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            # Map preserves input order; materialise into a list so responses
            # are indexed by candidate id deterministically.
            results = list(pool.map(_one_call, range(k)))

        candidates: list[CandidateGeneration] = []
        for i, response in results:
            state.llm_calls += 1
            state.tokens_used += response.input_tokens + response.output_tokens
            candidates.append(
                CandidateGeneration(
                    candidate_id=f"cand-{i}",
                    content=response.output_text,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                ),
            )

        # Build criteria bundle from the actual TreeSection + rubric (if loaded).
        # If rubric is None, bundle.rubric_criteria is empty and synthesis runs
        # on writing_guidance only — acceptable but weaker. See initialiser for
        # where rubric is parsed from report_template.toml.
        section_tree = next(sec for sec in self._template._schema.sections if sec.id == section_id)
        bundle = build_criteria_bundle(section=section_tree, rubric=self._rubric)

        # References for the synthesiser: per-source extracted data (before the
        # prompt-level merge). Source extractions are treated as ground truth.
        references = {
            source_label: _stringify_extraction(source_data)
            for source_label, source_data in state.extractions.get(
                section_id,
                {},
            ).items()
            if source_data
        }

        from aec_bench.templates.report.criteria import filter_references

        permitted = filter_references(self._source_docs, bundle.eval_references)
        references = {
            key: value for key, value in references.items() if resolve_source_label(key, permitted).resolved is not None
        }
        for key, value in permitted.items():
            if not any(resolve_source_label(label, {key: value}).resolved for label in references):
                references[key] = value

        result = synthesise_section(
            section_id=section_id,
            candidates=candidates,
            bundle=bundle,
            references=references,
            config=fill_config.synthesis,
            client=self._client,
        )

        # Synthesis LLM call (or fallback — still worth counting the attempt).
        state.llm_calls += 1
        state.tokens_used += result.trajectory_event.get(
            "synthesiser_input_tokens",
            0,
        )
        state.tokens_used += result.trajectory_event.get(
            "synthesiser_output_tokens",
            0,
        )
        state.synthesis_events.append(result.trajectory_event)

        fallback_note = (
            f" [FALLBACK: {result.trajectory_event.get('fallback_reason')}]"
            if result.trajectory_event.get("fallback_used")
            else ""
        )
        self._emit(
            "synthesise",
            f"{section_id} synthesised "
            f"({result.trajectory_event.get('synthesiser_input_tokens', 0):,} in / "
            f"{result.trajectory_event.get('synthesiser_output_tokens', 0):,} out){fallback_note}",
        )

        if self._cb:
            self._cb("synthesise", section_id, None, state)

        return result.content

    def _criteria_text(self, section: Any) -> str:
        from aec_bench.templates.report.criteria import build_criteria_bundle

        criteria = build_criteria_bundle(section=section, rubric=self._rubric).format_for_judge()
        rules = [
            rule.model_dump(mode="json")
            for rule in self._template.rules
            if not rule.sections or section.id in rule.sections
        ]
        return criteria + ("\nPublic writing checks: " + json.dumps(rules) if rules else "")

    def _get_section_info(self, section_id: str) -> dict[str, Any]:
        """Get section metadata from the template schema."""
        for sec in self._template._schema.sections:
            if sec.id == section_id:
                return {
                    "id": sec.id,
                    "title": sec.title,
                    "generation_mode": sec.generation_mode or "transform",
                    "writing_guidance": list(sec.writing_guidance) + [self._criteria_text(sec)],
                    "input_mapping": list(sec.input_mapping),
                    "fields": dict(sec.fields),
                }
        return {
            "id": section_id,
            "title": section_id,
            "generation_mode": "transform",
            "writing_guidance": [],
            "input_mapping": [],
            "fields": {},
        }

    def _get_source_priority(self, section_id: str) -> dict[str, int]:
        """Look up the per-source priority map for a section.

        Returns an empty dict when the section has no source_priority configured
        or when the section id is not found in the schema.
        """
        for section in self._template._schema.sections:
            if section.id == section_id:
                return dict(section.source_priority)
        return {}

    def _resolve_source(self, source_label: str) -> str:
        """Resolve a template source label to document content.

        Source labels can be 'doc:section' (e.g. 'brief:Description/Background')
        or plain doc names (e.g. 'brief'). Matches against discovered document
        keys by trying exact match first, then prefix match on the doc part.

        When a sandbox is configured, whole-doc bare-label slices are fetched via
        the sandbox API so future anchor-first slicing can be added in one place.
        """
        if self._sandbox is not None:
            try:
                return self._sandbox.slice(source_label, None).text
            except KeyError:
                return ""

        return resolve_source_label(source_label, self._source_docs).content

    def _get_dependency_context(self, section_id: str) -> dict[str, str]:
        """Get filled content from dependency sections (for extraction context)."""
        deps = self._template.get_dependencies(section_id)
        result = {}
        for dep in deps:
            ctx = self._template.get_section_context(section_id)
            raw = ctx.get(dep, "")
            # fill_section stores {"content": text}; extract the prose string
            if isinstance(raw, dict):
                result[dep] = raw.get("content", str(raw))
            else:
                result[dep] = str(raw) if raw else ""
        return result

    def _get_dependency_summaries(self, section_id: str) -> dict[str, str]:
        """Get short summaries of dependency sections for review."""
        deps = self._template.get_dependencies(section_id)
        summaries = {}
        for dep in deps:
            ctx = self._template.get_section_context(section_id)
            raw = ctx.get(dep, "")
            # fill_section stores {"content": text}; extract the prose string
            if isinstance(raw, dict):
                content = raw.get("content", str(raw))
            else:
                content = str(raw) if raw else ""
            if content:
                summaries[dep] = content[:300]
        return summaries


def _parse_json_response(raw_text: str) -> dict[str, Any]:
    """Parse a JSON response from the LLM, stripping markdown fences."""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
        return {"value": result}
    except json.JSONDecodeError:
        _log.warning("Failed to parse JSON response, wrapping as raw text")
        return {"raw_text": raw_text}


def _merge_source_extractions(
    source_data: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Flatten source-keyed extractions into a single dict for prompts."""
    merged: dict[str, Any] = {}
    for _source_label, data in source_data.items():
        merged.update(data)
    return merged


def _stringify_extraction(data: Any) -> str:
    """Render a source extraction dict for the synthesiser prompt.

    JSON with indented formatting keeps structure visible and is round-trip safe.
    """
    import json

    try:
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(data)
