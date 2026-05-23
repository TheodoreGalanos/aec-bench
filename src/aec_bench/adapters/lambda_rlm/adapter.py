# ABOUTME: LambdaRlmAdapter — wires planner, executor, and template into the Adapter protocol.
# ABOUTME: Runs the plan/extract/review/generate pipeline and returns a structured AdapterResult.

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aec_bench.adapters.lambda_rlm.config import TemplateMeta
    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

from aec_bench.adapters.base import (
    AdapterCapabilities,
    AdapterFailureKind,
    AdapterRequest,
    AdapterResult,
)
from aec_bench.adapters.config import record_effective_configuration
from aec_bench.adapters.lambda_rlm.config import LambdaRlmConfig
from aec_bench.adapters.lambda_rlm.executor import PlanExecutor
from aec_bench.adapters.lambda_rlm.planner import build_execution_plan
from aec_bench.adapters.lambda_rlm.state import PlanState
from aec_bench.adapters.rlm.client import RlmClient, RlmCompletionResponse, RlmMessage
from aec_bench.adapters.rlm.template import ReportTemplate
from aec_bench.adapters.transcript import (
    TokenUsage,
    TranscriptEntry,
    TranscriptEvent,
    TranscriptRole,
)
from aec_bench.contracts.advisor import AdvisorConfig
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.constitution import ConstitutionManifest
from aec_bench.contracts.pricing import estimate_cost_usd
from aec_bench.contracts.rubric import Rubric

_log = logging.getLogger(__name__)

_OUTPUT_FILENAME = "output.md"

_LEADING_H1_RE = re.compile(r"^# [^\n]*\n+")


def _strip_leading_top_level_heading(content: str) -> str:
    """Remove a leading top-level (``# ...``) heading line from *content* if present.

    The assembler owns section numbering, so any heading the LLM included would
    duplicate (and likely contradict) the canonical one.
    """
    return _LEADING_H1_RE.sub("", content, count=1)


@dataclass(frozen=True)
class _LambdaTranscriptEntry(TranscriptEntry):
    """TranscriptEntry extended with a call_type label for lambda-rlm phases."""

    call_type: str | None = None


class _TokenCountingClient:
    """Thin wrapper around an RlmClient that accumulates input/output token totals."""

    def __init__(self, inner: RlmClient) -> None:
        self._inner = inner
        self.total_input: int = 0
        self.total_output: int = 0
        self.total_cache_read: int = 0
        self.total_cache_write: int = 0

    def generate(
        self,
        *,
        model: str,
        messages: list[RlmMessage],
        system_prompt: str | None,
        temperature: float | None = None,
    ) -> RlmCompletionResponse:
        response = self._inner.generate(
            model=model,
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
        )
        self.total_input += response.input_tokens
        self.total_output += response.output_tokens
        self.total_cache_read += response.cache_read_tokens
        self.total_cache_write += response.cache_write_tokens
        return response


class LambdaRlmAdapter:
    """Adapter that runs the lambda-rlm deterministic pipeline.

    Phases:
      1. Plan  — build cost-optimal execution plan from template sections
      2. Extract — pull structured data from source documents (per section)
      3. Review  — contract alignment check (optional)
      4. Generate — compose section prose from extractions
      5. Output  — assemble full document and write to workspace
    """

    @classmethod
    def declare_capabilities(cls) -> AdapterCapabilities:
        """Declare which constitutional mechanisms this adapter enforces.

        Lambda-RLM's deterministic pipeline supports source tracing
        (enforced in extraction/review/generation prompts) and
        context filtering (dependency-context preview slicing). The
        pipeline does not scaffold, compact, or grant autonomy, so
        those capabilities are False.
        """
        return AdapterCapabilities(
            has_context_filtering=True,
            has_state_persistence=False,
            has_compaction=False,
            has_scaffolding=False,
            has_review_phase=True,
            has_source_tracing=True,
        )

    def __init__(
        self,
        *,
        adapter_name: str,
        model_name: str,
        client: RlmClient,
        template: ReportTemplate,
        source_docs: dict[str, str],
        config: LambdaRlmConfig,
        workspace: str,
        trajectory_writer: Any | None = None,
        advisor_client: RlmClient | None = None,
        advisor_config: AdvisorConfig | None = None,
        constitution: ConstitutionManifest | None = None,
        rubric: Rubric | None = None,
        boilerplate_fragments: dict[str, Any] | None = None,
        template_meta: TemplateMeta | None = None,
        sandbox: DocumentSandbox | None = None,
    ) -> None:
        self._adapter_name = adapter_name
        self._model_name = model_name
        self._client = client
        self._template = template
        self._source_docs = source_docs
        self._config = config
        self._workspace = workspace
        self._traj = trajectory_writer
        self._advisor_client = advisor_client
        self._advisor_config = advisor_config
        self._constitution = constitution
        self._rubric = rubric
        self._boilerplate_fragments = boilerplate_fragments or {}
        self._template_meta = template_meta
        self._sandbox = sandbox

    @property
    def boilerplate_fragments(self) -> dict[str, Any]:
        """Read-only view of compose-mode boilerplate fragments loaded for this adapter."""
        return self._boilerplate_fragments

    # -- Adapter protocol -------------------------------------------------------

    def execute(self, request: AdapterRequest) -> AdapterResult:
        """Run the full lambda-rlm pipeline and return an AdapterResult."""
        transcript: list[TranscriptEntry] = []

        # Phase 1: Plan
        sections = self._extract_section_dicts()
        plan = build_execution_plan(
            sections=sections,
            source_docs=self._source_docs,
            config=self._config.planner,
        )

        plan_summary = f"lambda-rlm plan: {plan.active_section_count} sections, ~{plan.total_estimated_calls} LLM calls"
        transcript.append(
            _LambdaTranscriptEntry(
                role=TranscriptRole.ASSISTANT,
                content=plan_summary,
                event=TranscriptEvent.MESSAGE,
                call_type="plan",
            )
        )
        _log.info(plan_summary)

        # Write a plan entry to the trajectory before execution begins
        plan_state_init = PlanState(estimated_calls=plan.total_estimated_calls, phase="plan")
        self._write_traj_entry(
            tool_name="plan",
            command=plan_summary,
            stdout=plan_summary,
            phase="plan",
            state=plan_state_init,
            extra_metadata={"template_progress": self._build_template_progress()},
        )

        # Phases 2–4: Extract → Review → Generate (via PlanExecutor)
        # Wrap client to capture separate input/output token totals
        counting_client = _TokenCountingClient(self._client)
        source_fidelity = self._constitution.source_fidelity if self._constitution else None
        information_minimality = self._constitution.information_minimality if self._constitution else None
        executor = PlanExecutor(
            client=counting_client,
            model=self._model_name,
            template=self._template,
            source_docs=self._source_docs,
            config=self._config,
            trajectory_callback=self._make_traj_callback(),
            source_fidelity=source_fidelity,
            information_minimality=information_minimality,
            rubric=self._rubric,
            boilerplate_fragments=self._boilerplate_fragments,
            template_meta=self._template_meta,
            sandbox=self._sandbox,
        )
        state = executor.execute(plan)

        total_input = counting_client.total_input
        total_output = counting_client.total_output
        total_cache_read = counting_client.total_cache_read
        total_cache_write = counting_client.total_cache_write

        cost = estimate_cost_usd(
            self._model_name,
            input_tokens=total_input,
            output_tokens=total_output,
            cache_read_tokens=total_cache_read,
            cache_write_tokens=total_cache_write,
        )
        cost_str = f", est ${cost:.3f}" if cost is not None else ""

        # Write a completion entry after all phases finish
        completion_summary = (
            f"Completed {state.llm_calls} LLM calls, "
            f"{state.tokens_used} tokens used"
            f" (cache read: {total_cache_read:,}, cache write: {total_cache_write:,})"
            f"{cost_str}"
        )
        self._write_traj_entry(
            tool_name="complete",
            command=completion_summary,
            stdout=completion_summary,
            phase="complete",
            state=state,
            extra_metadata={"template_progress": self._build_template_progress()},
        )

        # Add a single execution-summary entry to the transcript
        exec_summary = f"Executed {state.llm_calls} LLM calls, {state.tokens_used} tokens used"
        transcript.append(
            _LambdaTranscriptEntry(
                role=TranscriptRole.ASSISTANT,
                content=exec_summary,
                event=TranscriptEvent.MESSAGE,
                usage=TokenUsage(
                    input_tokens=total_input,
                    output_tokens=total_output,
                ),
                call_type="execute",
            )
        )

        # Phase 5: Submit and assemble output document
        submission = self._template.submit()
        output_text = self._assemble_output(submission.sections)

        output_path = str(Path(self._workspace) / _OUTPUT_FILENAME)
        Path(output_path).write_text(output_text, encoding="utf-8")

        # Write structured sections for downstream export (e.g. Word template population)
        sections_path = Path(self._workspace) / "sections.json"
        sections_path.write_text(
            json.dumps(submission.sections, indent=2, default=str),
            encoding="utf-8",
        )

        # Write per-section composition traces for any compose-mode sections
        # that ran. Each entry records verbatim/fill/generated provenance and
        # character offsets so downstream tools (report-gen, reviewer UIs) can
        # distinguish templated spans from model-written ones without having
        # to re-parse output.md.
        if state.composition_traces:
            trace_path = Path(self._workspace) / "composition_trace.json"
            trace_path.write_text(
                json.dumps(state.composition_traces, indent=2, default=str),
                encoding="utf-8",
            )

        # Layer 3 of Idea B: post-hoc grounding audit. Observability-only —
        # never affects reward. Only runs when sandbox is built AND
        # grounding.check is on.
        if self._sandbox is not None and self._config.grounding.check != "off":
            self._emit_grounding_report(state)

        if state.extraction_candidates:
            candidates_path = Path(self._workspace) / "extraction_candidates.json"
            candidates_path.write_text(
                json.dumps(state.extraction_candidates, indent=2, default=str),
                encoding="utf-8",
            )

        # Skipped sections (e.g. generation_mode=external) are intentional gaps
        real_gaps = [g for g in submission.gaps if g not in plan.skipped_sections]
        is_complete = len(real_gaps) == 0
        status = AgentOutputStatus.COMPLETED if is_complete else AgentOutputStatus.PARTIAL
        failure_kind = None if is_complete else AdapterFailureKind.MISSING_OUTPUT

        if real_gaps:
            _log.warning("Template incomplete; gaps: %s", real_gaps)

        return AdapterResult(
            adapter_name=self._adapter_name,
            resolved_model=self._model_name,
            configuration_record=record_effective_configuration(
                resolved_model=self._model_name,
                configuration=dict(request.configuration),
            ),
            agent_output=AgentOutput(
                status=status,
                output_path=output_path,
                output_format="md",
                error_message=None,
            ),
            transcript=transcript,
            failure_kind=failure_kind,
            raw_output_text=output_text,
            provider_error=None,
            usage_input_tokens=total_input,
            usage_output_tokens=total_output,
        )

    def adapter_name(self) -> str:
        return self._adapter_name

    def resolved_model(self) -> str:
        return self._model_name

    # -- Private helpers -------------------------------------------------------

    def _write_traj_entry(
        self,
        *,
        tool_name: str,
        command: str,
        stdout: str,
        phase: str,
        state: PlanState,
        extra_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Write a paired tool_call + tool_result entry to the trajectory writer."""
        if self._traj is None:
            return
        metadata: dict[str, Any] = {
            "phase": phase,
            "plan_state": state.snapshot(),
        }
        if extra_metadata:
            metadata.update(extra_metadata)
        self._traj.new_step(call_type="main")
        self._traj.tool_call(tool_name, command)
        self._traj.tool_result(tool_name, stdout=stdout, metadata=metadata)

    def _make_traj_callback(self) -> Callable[..., None] | None:
        """Return a callback for PlanExecutor that writes trajectory entries per phase."""
        if self._traj is None:
            return None

        def _callback(
            event_type: str,
            section_id: str,
            source: str | None,
            state: PlanState,
        ) -> None:
            # Map executor event types to phase labels
            phase = event_type if event_type != "leaf_extract" else "extract"
            command = f"{phase} {section_id}" if source is None else f"{phase} {section_id} ← {source}"
            extra: dict[str, Any] = {"section_id": section_id}
            if source is not None:
                extra["source"] = source
            if phase == "generate":
                extra["template_progress"] = self._build_template_progress()
            if phase == "synthesise" and state.synthesis_events:
                extra["synthesis"] = state.synthesis_events[-1]
            self._write_traj_entry(
                tool_name=phase,
                command=command,
                stdout=command,
                phase=phase,
                state=state,
                extra_metadata=extra,
            )

        return _callback

    def _emit_grounding_report(self, state: PlanState) -> None:
        """Run the grounding check across all compose-mode sections and write the report.

        Non-compose-mode sections (no entry in composition_traces) are silently
        skipped. The report is written to <workspace>/grounding_report.json as
        JSON and is observability-only — it never affects reward.
        """
        from aec_bench.adapters.lambda_rlm.grounding import run_grounding_check
        from aec_bench.contracts.grounding_report import GroundingReport

        # Back-brief topic digests live in compose_scratchpad under the
        # reserved ``_back_brief`` key (see PlanState docstring). Threading
        # this through lets the auditor resolve ``references/*:<topic>``
        # provenance refs the same way the generator did — without it,
        # legitimate back-brief grounded content shows up as flagged FPs
        # legitimate back-brief grounded content shows up as flagged FPs.
        back_brief: Mapping[str, str] | None = None
        bb = state.compose_scratchpad.get("_back_brief")
        if isinstance(bb, dict):
            back_brief = bb

        section_results = []
        for section_id, block_traces in state.composition_traces.items():
            section_text = state.sections.get(section_id)
            if section_text is None:
                continue
            result = run_grounding_check(
                section_id=section_id,
                section_text=section_text,
                block_traces=block_traces,
                sandbox=self._sandbox,
                custom_patterns=self._config.grounding.custom_facts,
                back_brief=back_brief,
            )
            section_results.append(result)

        report = GroundingReport(sections=tuple(section_results))
        report_path = Path(self._workspace) / "grounding_report.json"
        report_path.write_text(
            json.dumps(report.to_dict(), indent=2),
            encoding="utf-8",
        )

    def _build_template_progress(self) -> dict[str, Any]:
        """Build a template_progress dict from current template fill state."""
        status = self._template.get_status()
        sections = self._template._schema.sections
        filled_ids = set(self._template._filled.keys())
        return {
            "completed": status.completed_sections,
            "total": status.total_sections,
            "section_list": [{"id": s.id, "filled": s.id in filled_ids} for s in sections],
        }

    def _extract_section_dicts(self) -> list[dict[str, Any]]:
        """Convert template schema sections to the dicts expected by the planner."""
        result = []
        for sec in self._template._schema.sections:
            result.append(
                {
                    "id": sec.id,
                    "title": sec.title,
                    "generation_mode": sec.generation_mode or "transform",
                    "writing_guidance": list(sec.writing_guidance),
                    "input_mapping": list(sec.input_mapping),
                    "depends_on": list(sec.depends_on),
                }
            )
        return result

    def _assemble_output(self, sections: dict[str, dict[str, Any]]) -> str:
        """Join section prose values into a single markdown document.

        The assembler owns section numbering — every section gets a
        ``# {N}. {title}`` heading where N is its 1-indexed position in the
        template. LLM-supplied leading ``# ...`` headings on transform/guided
        content are stripped before the assembler prepends its own, so we
        never end up with duplicate or hallucinated section numbers.
        """
        parts: list[str] = []
        position = 0
        for section in self._template._schema.sections:
            filled = sections.get(section.id)
            if filled is None:
                continue
            content = filled.get("content", "")
            if not content:
                continue
            position += 1
            body = _strip_leading_top_level_heading(str(content))
            parts.append(f"# {position}. {section.title}\n\n{body}")
        return "\n\n".join(parts)
