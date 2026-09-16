# ABOUTME: LambdaRlmAdapter — wires planner, executor, and template into the Adapter protocol.
# ABOUTME: Runs the plan/extract/review/generate pipeline and returns a structured AdapterResult.

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from aec_bench.adapters.lambda_rlm.config import TemplateMeta
    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

from aec_bench.adapters.base import (
    AdapterCapabilities,
    AdapterFailureKind,
    AdapterRequest,
    AdapterResult,
    AdapterStopReason,
    initialize_transcript,
)
from aec_bench.adapters.config import record_effective_configuration
from aec_bench.adapters.lambda_rlm.config import LambdaRlmConfig, validate_lambda_config
from aec_bench.adapters.lambda_rlm.executor import PlanExecutor
from aec_bench.adapters.lambda_rlm.planner import build_execution_plan
from aec_bench.adapters.lambda_rlm.state import PlanState
from aec_bench.adapters.output_commit import configured_output_completion_commit, configured_output_completion_contract
from aec_bench.adapters.rlm.client import RlmClient, RlmCompletionResponse, RlmMessage
from aec_bench.adapters.runtime_limits import AdapterRuntimeLimitError, configured_positive_int
from aec_bench.adapters.subagent_trajectory import record_subagent_call
from aec_bench.contracts.adapter_execution import (
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
from aec_bench.templates.report.criteria import validate_rubric
from aec_bench.templates.report.output import REPORT_OUTPUT_FORMATS, write_report
from aec_bench.templates.report.session import ReportSession
from aec_bench.templates.report.sources import contained_path
from aec_bench.trajectory.writer import TrajectoryWriter

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class _LambdaTranscriptEntry(TranscriptEntry):
    """TranscriptEntry extended with a call_type label for lambda-rlm phases."""

    call_type: str | None = None


class _TokenCountingClient:
    """Thin wrapper around an RlmClient that accumulates input/output token totals."""

    def __init__(
        self,
        inner: RlmClient,
        *,
        max_calls: int | None = None,
        token_budget: int | None = None,
        instruction: str = "",
        system_prompt: str | None = None,
        trajectory_writer: TrajectoryWriter | None = None,
        parent_tool_call_id: str | None = None,
        trajectory_agent_name: Callable[[], str] | None = None,
    ) -> None:
        self.model_clients: dict[str, RlmClient] = {}
        self._inner = inner
        self.token_budget = token_budget
        self.instruction = instruction
        self.system_prompt = system_prompt
        self._trajectory_writer = trajectory_writer
        self._parent_tool_call_id = parent_tool_call_id
        self._trajectory_agent_name = trajectory_agent_name
        self.stop_error: Exception | None = None
        self.usage_known = True
        self.per_model: dict[str, dict[str, int]] = {}
        self._max_calls = max_calls
        self._calls_started = 0
        self._lock = threading.Lock()
        self.total_input: int = 0
        self.total_output: int = 0
        self.total_cache_read: int = 0
        self.total_cache_write: int = 0

    @property
    def calls_started(self) -> int:
        """Return the exact number of provider calls admitted by the wrapper."""

        with self._lock:
            return self._calls_started

    def generate(
        self,
        *,
        model: str,
        messages: list[RlmMessage],
        system_prompt: str | None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> RlmCompletionResponse:
        with self._lock:
            if self.stop_error is not None:
                raise self.stop_error
            if self._max_calls is not None and self._calls_started >= self._max_calls:
                self.stop_error = AdapterRuntimeLimitError(f"max_turns={self._max_calls} exhausted")
                raise self.stop_error
            self._calls_started += 1
            usage = self.per_model.setdefault(
                model,
                {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0},
            )
            usage["calls"] += 1

        policy = "\n\n".join(p for p in [self.system_prompt, system_prompt] if p)
        task_messages = [RlmMessage(role="user", content=self.instruction)] if self.instruction else []
        try:
            output_settings = {"max_output_tokens": max_output_tokens} if max_output_tokens is not None else {}
            response = record_subagent_call(
                lambda: self.model_clients.get(model, self._inner).generate(
                    model=model,
                    messages=task_messages + messages,
                    system_prompt=policy or None,
                    temperature=temperature,
                    **output_settings,
                ),
                writer=self._trajectory_writer,
                parent_tool_call_id=self._parent_tool_call_id,
                agent_name=(
                    self._trajectory_agent_name() if self._trajectory_agent_name is not None else "lambda_rlm:subcall"
                ),
                model=model,
                messages=task_messages + messages,
                system_prompt=policy or None,
            )
        except Exception as exc:
            with self._lock:
                self.usage_known = False
                self.stop_error = exc
            raise
        with self._lock:
            self.total_input += response.input_tokens
            self.total_output += response.output_tokens
            self.total_cache_read += response.cache_read_tokens
            self.total_cache_write += response.cache_write_tokens
            usage = self.per_model[model]
            usage["input_tokens"] += response.input_tokens
            usage["output_tokens"] += response.output_tokens
            usage["cache_read_tokens"] += response.cache_read_tokens
            usage["cache_write_tokens"] += response.cache_write_tokens
            if response.error_message:
                self.usage_known = False
                self.stop_error = RuntimeError(response.error_message)
            elif self.token_budget is not None and self.total_input + self.total_output >= self.token_budget:
                self.stop_error = AdapterRuntimeLimitError(f"Observed token budget {self.token_budget} reached")
        if response.error_message:
            raise RuntimeError(response.error_message)
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
        template: ReportSession,
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
        self._execution_lock = threading.Lock()
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
        self._rubric = rubric or template.rubric
        self._boilerplate_fragments = boilerplate_fragments or {}
        self._template_meta = template_meta
        self._sandbox = sandbox

    @property
    def boilerplate_fragments(self) -> dict[str, Any]:
        """Read-only view of compose-mode boilerplate fragments loaded for this adapter."""
        return self._boilerplate_fragments

    # -- Adapter protocol -------------------------------------------------------

    def execute(self, request: AdapterRequest) -> AdapterResult:
        """Keep invocations that share this adapter's workspace separate."""
        with self._execution_lock:
            return self._execute(request)

    def _execute(self, request: AdapterRequest) -> AdapterResult:
        """Run the report pipeline with fresh mutable report state."""
        validate_lambda_config(self._config)
        if request.output_format not in REPORT_OUTPUT_FORMATS:
            raise ValueError(f"Unsupported report output format: {request.output_format}")
        contained_path(Path(self._workspace), request.output_path)
        contract = configured_output_completion_contract(request)
        if contract is not None or configured_output_completion_commit(request, contract=contract):
            raise ValueError("lambda-RLM does not support explicit output commitment")
        output_target = contained_path(Path(self._workspace), request.output_path)
        if output_target in {
            Path(self._workspace).resolve() / name
            for name in (
                "sections.json",
                "composition_trace.json",
                "extraction_candidates.json",
                "grounding_report.json",
            )
        }:
            raise ValueError("Report output path conflicts with an auxiliary artifact")
        self._template = self._template.fresh()
        unknown_targets = set(self._config.fill_section.apply_to_sections) - {
            s.id for s in self._template.schema.sections
        }
        if unknown_targets:
            raise ValueError(f"Unknown fill_section.apply_to_sections: {sorted(unknown_targets)}")
        validate_rubric(self._template.schema, self._rubric, self._source_docs)
        transcript = initialize_transcript(request)

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
        max_turns = configured_positive_int(request.configuration, "max_turns")
        token_budget = min(
            self._config.token_budget,
            configured_positive_int(request.configuration, "token_budget") or self._config.token_budget,
        )
        state = PlanState(estimated_calls=plan.total_estimated_calls)
        plan_call_id = str(uuid4())
        counting_client = _TokenCountingClient(
            self._client,
            max_calls=max_turns,
            token_budget=token_budget,
            instruction=request.instruction,
            system_prompt=request.system_prompt,
            trajectory_writer=self._traj,
            parent_tool_call_id=plan_call_id,
            trajectory_agent_name=lambda: f"lambda_rlm:{state.phase}",
        )
        if self._advisor_client is not None and self._advisor_config is not None:
            counting_client.model_clients[self._advisor_config.model] = self._advisor_client
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
        run_error: Exception | None = None
        if self._traj is not None:
            self._traj.new_step(call_type="main")
            self._traj.tool_call("execute_plan", plan_summary, tool_call_id=plan_call_id)
        try:
            executor.execute(plan, state=state)
        except Exception as exc:
            run_error = exc
        run_error = counting_client.stop_error or run_error
        if self._traj is not None:
            self._traj.tool_result(
                "execute_plan",
                stdout=f"Executed {counting_client.calls_started} model calls",
                stderr=type(run_error).__name__ if run_error is not None else "",
                exit_code=1 if run_error is not None else 0,
                tool_call_id=plan_call_id,
                metadata={"phase": "execute_plan", "plan_state": state.snapshot()},
            )

        state.llm_calls = counting_client.calls_started
        state.tokens_used = counting_client.total_input + counting_client.total_output
        total_input = counting_client.total_input
        total_output = counting_client.total_output
        total_cache_read = counting_client.total_cache_read
        total_cache_write = counting_client.total_cache_write

        model_costs = [
            estimate_cost_usd(
                model,
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                cache_read_tokens=usage["cache_read_tokens"],
                cache_write_tokens=usage["cache_write_tokens"],
            )
            for model, usage in counting_client.per_model.items()
        ]
        cost_known = counting_client.usage_known and all(cost is not None for cost in model_costs)
        cost = sum(cost for cost in model_costs if cost is not None) if cost_known else None
        cost_str = f", est ${cost:.3f}" if cost is not None else ""

        # Write a completion entry after all phases finish
        completion_summary = (
            f"Executed {state.llm_calls} LLM calls, "
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
        submission = write_report(self._template, request.output_path, request.output_format, workspace=self._workspace)
        output_path = request.output_path
        output_text = output_target.read_text(encoding="utf-8")

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
        is_complete = submission.complete and not state.structure_unresolved and run_error is None
        status = AgentOutputStatus.COMPLETED if is_complete else AgentOutputStatus.PARTIAL
        failure_kind = None if is_complete else AdapterFailureKind.MISSING_OUTPUT

        stop_reason = None
        if isinstance(run_error, AdapterRuntimeLimitError):
            token_stop = counting_client.total_input + counting_client.total_output >= token_budget
            failure_kind = (
                AdapterFailureKind.TOKEN_BUDGET_REACHED if token_stop else AdapterFailureKind.TURN_LIMIT_REACHED
            )
            stop_reason = AdapterStopReason.TOKEN_BUDGET if token_stop else AdapterStopReason.ITERATION_CAP
        elif run_error is not None:
            failure_kind = AdapterFailureKind.PROVIDER_ERROR

        if not is_complete:
            transcript.append(
                _LambdaTranscriptEntry(
                    role=TranscriptRole.ASSISTANT,
                    call_type="report_diagnostics",
                    content=json.dumps(
                        {
                            "gaps": submission.gaps,
                            "validation_failures": state.validation_failures,
                            "public_checks": {key: asdict(value) for key, value in submission.diagnostics.items()},
                            "rejected_drafts": {key: state.sections.get(key, "") for key in state.validation_failures},
                            "structure_unresolved": {
                                key: asdict(value) for key, value in state.structure_unresolved.items()
                            },
                        },
                        default=str,
                    ),
                )
            )
        if real_gaps:
            _log.warning("Template incomplete; gaps: %s", real_gaps)

        return AdapterResult(
            adapter_name=self._adapter_name,
            resolved_model=self._model_name,
            configuration_record=record_effective_configuration(
                resolved_model=self._model_name,
                configuration=dict(request.configuration)
                | {
                    "report_config": _configuration_snapshot(self._config) | {"token_budget": token_budget},
                    "constitution": asdict(self._constitution) if self._constitution else None,
                    "report_assets": self._template.configuration(),
                    "usage_by_model": counting_client.per_model,
                },
            ),
            agent_output=AgentOutput(
                status=status,
                output_path=output_path,
                output_format=request.output_format,
                error_message=str(run_error)
                if run_error
                else (
                    str(
                        {
                            "gaps": submission.gaps,
                            "validation": state.validation_failures,
                            "structure": state.structure_unresolved,
                        }
                    )
                    if not is_complete
                    else None
                ),
            ),
            transcript=transcript,
            failure_kind=failure_kind,
            stop_reason=stop_reason,
            turns_used=counting_client.calls_started,
            max_turns=max_turns,
            raw_output_text=output_text,
            provider_error=str(run_error)
            if run_error and not isinstance(run_error, AdapterRuntimeLimitError)
            else None,
            usage_model_calls=counting_client.calls_started - state.advisor_calls,
            usage_input_tokens=total_input - state.advisor_input_tokens if counting_client.usage_known else None,
            usage_output_tokens=total_output - state.advisor_output_tokens if counting_client.usage_known else None,
            usage_cache_read_tokens=total_cache_read,
            usage_cache_write_tokens=total_cache_write,
            usage_advisor_calls=state.advisor_calls if self._config.advisor else None,
            usage_advisor_input_tokens=state.advisor_input_tokens
            if self._config.advisor and counting_client.usage_known
            else None,
            usage_advisor_output_tokens=state.advisor_output_tokens
            if self._config.advisor and counting_client.usage_known
            else None,
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

        if self._sandbox is None:
            raise RuntimeError("grounding report requires an initialized document sandbox")

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


def _configuration_snapshot(config: LambdaRlmConfig) -> dict[str, Any]:
    result = asdict(config)
    result["grounding"]["custom_facts"] = {
        key: pattern.pattern for key, pattern in config.grounding.custom_facts.items()
    }
    return result
