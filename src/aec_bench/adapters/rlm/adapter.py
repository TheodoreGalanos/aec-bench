# ABOUTME: RLM adapter integrating REPL engine, metadata, guardrails, and error tracking.
# ABOUTME: Runs a recursive language model loop with persistent Python execution environment.

from __future__ import annotations

import json
import logging
import re
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aec_bench.adapters.base import (
    AdapterCapabilities,
    AdapterFailureKind,
    AdapterRequest,
    AdapterResult,
)
from aec_bench.adapters.config import record_effective_configuration
from aec_bench.adapters.rlm.client import RlmClient, RlmMessage
from aec_bench.adapters.rlm.compaction import compact
from aec_bench.adapters.rlm.config import (
    ExecutionConfig,
    GuardrailConfig,
    SubcallConfig,
)
from aec_bench.adapters.rlm.context_filter import ContextFilter
from aec_bench.adapters.rlm.engine import (
    ReplEnvironment,
    parse_code_blocks,
    truncate_after_first_block,
)
from aec_bench.adapters.rlm.errors import ErrorLevel, ErrorTracker
from aec_bench.adapters.rlm.fill_parallel import fill_parallel as _fill_parallel
from aec_bench.adapters.rlm.guardrails import GuardrailState
from aec_bench.adapters.rlm.metadata import format_iteration_metadata
from aec_bench.adapters.rlm.parallel import parallel
from aec_bench.adapters.rlm.scaffolding import ScaffoldingState
from aec_bench.adapters.rlm.scratchpad import Scratchpad
from aec_bench.adapters.rlm.subcall_log import SubcallLog
from aec_bench.adapters.rlm.subcall_registry import build_subcall_functions
from aec_bench.adapters.rlm.template import ReportTemplate
from aec_bench.adapters.rlm.tokens import TokenTracker
from aec_bench.adapters.transcript import (
    TokenUsage,
    TranscriptEntry,
    TranscriptEvent,
    TranscriptRole,
    initialize_transcript,
)
from aec_bench.contracts.advisor import AdvisorConfig, AdvisorRequest, AdvisorResponse
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.constitution import ConstitutionManifest
from aec_bench.contracts.pricing import estimate_cost_usd

if TYPE_CHECKING:
    from aec_bench.adapters.advisor import AdvisorResult
    from aec_bench.contracts.constitution import StatePersistenceParams

logger = logging.getLogger(__name__)

_FINAL_MARKER = "FINAL"

_REPL_TOOL_NAME = "repl"
_REPL_TOOL_DESCRIPTION = (
    "Execute Python code in a persistent REPL environment. "
    "Variables persist across calls. Available functions: "
    "HELP() — list all commands; "
    "DOCS() / READ(name) — discover and read source documents; "
    "grep(text, pattern, context=3) — search a variable for a regex pattern; "
    "extract(doc, section='id') — LLM-powered goal-directed extraction; "
    "NOTE(key, value) / RECALL(key) — persistent scratchpad; "
    "FINAL_VAR(value) — declare final answer; "
    "report.fill_section(id, data) — fill template sections"
)
_REPL_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "code": {
            "type": "string",
            "description": "Python code to execute in the persistent REPL",
        }
    },
    "required": ["code"],
}

_SYSTEM_PROMPT = """\
{external_system_prompt}\
You are an RLM (Recursive Language Model) agent. The REPL is your extended \
cognition — not a tool you occasionally use, but HOW you think.

Your REPL variables persist forever, but your conversation history may be \
compacted. What you store in variables and the scratchpad is your true memory.

You have NO knowledge of the documents in this task. You must READ them to \
know what they contain. Writing content you have not read is hallucination.

CONTEXT MODEL — how your REPL output works:
- Tool results over 2000 chars are NOT shown to you in full. You receive \
a summary (type, size, preview) instead. The full data lives in your \
REPL variables — that is where your data is.
- grep() results are shown up to 10,000 chars with line numbers for navigation.
- Errors are always shown in full.
- print() of large data returns a summary, not the content. Do not try to \
force output by slicing, chunking, or looping — it will not work. Your \
data is already in variables. Use grep() and extract() to access it.
- Call SHOW_VARS() to see all variables with types and sizes.

Working pattern — section by section:
1. Discover: HELP() to see commands, DOCS() to list available documents
2. Read: READ(name) to load ALL documents into variables upfront
3. For EACH section:
   a. START(section_id) — get writing guidance and context
   b. Extract: extract(doc, section='section_id') for EACH source document. \
This is an LLM call that reads the full document and extracts data relevant \
to the section, guided by the writing rules. It sees everything you cannot.
   c. NOTE(key, value) — persist every extracted fact immediately
   d. FILL(section_id, fields) — compose from your stored notes
   e. Move to the next section immediately.

extract(doc, section='id') is your most powerful tool. One call per document \
per section replaces 10+ turns of grep. The LLM reads the full document \
knowing what the section needs and returns structured data.

Do NOT:
- Print large variables or paginate with slicing — it returns a summary
- Use grep as your primary data gathering method — use extract() instead
- Spend many turns gathering data before writing — work section by section
- Re-extract the same document repeatedly — one extract per document per section

Always: data in variables, compose from variables, never from memory.

{prohibited_section}\
{hints_section}\
{variables_section}\
"""


def build_constitution_section(manifest: ConstitutionManifest | None) -> str:
    """Generate the CONSTITUTION block for the agent's system prompt.

    The block surfaces active principles + key numeric values so the agent
    understands what the harness is enforcing. Returns empty string if no
    manifest is provided or no principles are enabled.
    """
    if manifest is None or not manifest.principles:
        return ""

    enabled_names = {p.name for p in manifest.principles if p.enabled}
    if not enabled_names:
        return ""

    lines: list[str] = ["CONSTITUTION — principles governing this session:"]

    if "information_minimality" in enabled_names and manifest.information_minimality:
        p = manifest.information_minimality
        lines.append(
            f"- Information Minimality: Tool results over {p.default_threshold:,} "
            f"chars are summarised. Your data lives in REPL variables. "
            f"Use grep() to search (up to {p.search_threshold:,} chars)."
        )

    if "state_persistence" in enabled_names and manifest.state_persistence:
        p = manifest.state_persistence
        lines.append(
            f"- State Persistence: Variables and scratchpad survive compaction "
            f"(strategy: {p.compaction_strategy}). Store anything worth keeping."
        )

    if "progress_obligation" in enabled_names and manifest.progress_obligation:
        p = manifest.progress_obligation
        lines.append(
            f"- Progress Obligation: Produce output within {p.gentle_nudge_turns} turns. "
            f"Extended data gathering without writing is considered speculation."
        )

    if "source_fidelity" in enabled_names and manifest.source_fidelity:
        p = manifest.source_fidelity
        if p.require_source_tracing:
            lines.append("- Source Fidelity: Every fact in your output must trace to extracted data.")
        if p.gap_framing == "exclude":
            lines.append(
                f"  When a source has no data for a topic, omit it entirely "
                f"or write {p.tbd_placeholder}. Do NOT fabricate."
            )
        elif p.gap_framing == "tbd":
            lines.append(
                f"  Use {p.tbd_placeholder} placeholder for any missing information. "
                f"A placeholder is always better than a fabrication."
            )
        elif p.gap_framing == "omit":
            lines.append("  Omit any topic that lacks source data entirely. Do not fabricate to fill gaps.")

    if "earned_autonomy" in enabled_names and manifest.earned_autonomy:
        p = manifest.earned_autonomy
        lines.append(
            f"- Earned Autonomy: Start in '{p.initial_mode}' mode. Freedom is earned by demonstrated progress."
        )

    return "\n".join(lines) + "\n"


def _build_system_prompt(
    *,
    hints: list[str] | None = None,
    variables: dict[str, str] | None = None,
    prohibited: list[str] | None = None,
    external_system_prompt: str = "",
    constitution: ConstitutionManifest | None = None,
) -> str:
    """Assemble the system prompt with optional hints, variables, and constitution."""
    external = ""
    if external_system_prompt:
        external = external_system_prompt.rstrip() + "\n\n"

    prohibited_section = ""
    if prohibited:
        formatted = "\n".join(f"- {p}" for p in prohibited)
        prohibited_section = f"You MUST NOT:\n{formatted}\n\n"

    hints_section = ""
    if hints:
        formatted_hints = "\n".join(f"- {h}" for h in hints)
        hints_section = f"Suggested approach:\n{formatted_hints}\n\n"

    variables_section = ""
    if variables:
        var_list = ", ".join(f"{n} ({t})" for n, t in sorted(variables.items()))
        variables_section = f"Pre-loaded variables: {var_list}\n\n"

    constitution_section = build_constitution_section(constitution)
    if constitution_section:
        constitution_section = "\n" + constitution_section + "\n"

    return (
        _SYSTEM_PROMPT.format(
            external_system_prompt=external,
            prohibited_section=prohibited_section,
            hints_section=hints_section,
            variables_section=variables_section,
        )
        + constitution_section
    )


def _format_code_preview(code: str) -> str:
    """Format a code snippet for the progress log line.

    For extract() calls, includes the field list so operators can see
    what data is being pulled. For everything else, shows the first
    line truncated to 80 chars.
    """
    first_line = code.strip().split("\n")[0]

    # Show extract() fields: extract(var, fields=["a", "b", "c"])
    if "extract(" in first_line:
        # Pull out the fields list from the full code block
        match = re.search(r"fields\s*=\s*\[([^\]]*)\]", code, re.DOTALL)
        if match:
            raw_fields = match.group(1)
            # Clean up: extract quoted field names
            field_names = re.findall(r'["\']([^"\']+)["\']', raw_fields)
            fields_str = ", ".join(field_names)
            # Build a compact preview: assignment + extract(var, [fields])
            var_match = re.match(r"(\w+)\s*=\s*extract\((\w+)", first_line)
            if var_match:
                return f"{var_match.group(1)} = extract({var_match.group(2)}, [{fields_str}])"
            return f"extract(..., [{fields_str}])"

    return first_line[:80]


def _make_final_var(repl: ReplEnvironment) -> Callable[[Any], str]:
    """Create a FINAL_VAR callable bound to the given REPL."""

    def final_var(value: Any) -> str:
        repl.final_value = value
        repl.final_called = True
        return f"FINAL_VAR set: {type(value).__name__}"

    return final_var


def _make_show_vars(repl: ReplEnvironment) -> Callable[[], list[str]]:
    """Create a SHOW_VARS callable bound to the given REPL."""

    def show_vars() -> list[str]:
        return sorted(repl.list_variables().keys())

    return show_vars


_SUBCALL_HELP: dict[str, str] = {
    "extract": (
        "  result = extract(doc, section='section_id')\n"
        "    → ExtractResult(.values: dict, .error: str|None)\n"
        "    Reads the full document and extracts data relevant to the section.\n"
        "    Uses writing guidance from the template to decide what to extract.\n"
        "    Also works without section: extract(doc, ['field1', 'field2'])\n"
    ),
    "summarise": ("  result = summarise(content=...)\n    → SummariseResult(.summary: str, .error: str|None)\n"),
    "calculate": (
        "  result = calculate(expression=..., variables={})\n    → CalculateResult(.values: dict, .error: str|None)\n"
    ),
    "retrieve": (
        "  result = retrieve(query=..., top_k=5)\n    → RetrieveResult(.results: list[dict], .error: str|None)\n"
    ),
    "verify": (
        "  result = verify(claim=..., evidence=...)\n"
        "    → VerificationResult(.passed: bool, .confidence: float, "
        ".explanation: str, .error: str|None)\n"
    ),
    "reason": (
        "  result = reason(question=..., context=...)\n"
        "    → ReasoningResult(.conclusion: str, .confidence: float, "
        ".rationale: str, .error: str|None)\n"
    ),
    "review": (
        "  result = review(section_content=..., writing_guidance=[...], extracted_data={...})\n"
        "    → SectionReviewResult(.status: str, .gaps: list, .risks: list, .error: str|None)\n"
        "    Use after FILL to check section quality against writing guidance.\n"
    ),
    "advisor": (
        "  result = ADVISOR(goal=..., problem=..., attempt=...)\n"
        "    → AdvisorResult(.response: AdvisorResponse, .error: str|None)\n"
        "    .response.advice: str, .response.suggested_action: str,\n"
        "    .response.confidence: float, .response.reasoning: str\n"
    ),
}


def _make_help(
    enabled_subcalls: set[str] | None = None,
) -> Callable[[], str]:
    """Create a HELP callable listing available commands.

    Only lists sub-calls that are in *enabled_subcalls*.  When ``None``,
    lists all sub-calls (backwards compatible).
    """
    show_all = enabled_subcalls is None

    def help_fn() -> str:
        parts = [
            "Available REPL commands:\n\n"
            "MEMORY:\n"
            "  NOTE(key, value) — persist data to scratchpad (survives compaction)\n"
            "  RECALL(key) → str — retrieve from scratchpad (no args = list all keys)\n"
            "  SHOW_VARS() — list all REPL variables with types and sizes\n"
            "  FINAL_VAR(value) — declare the final output and end the task\n"
            "  grep(text, pattern, context=3) — search text for regex, returns matching lines\n"
            "  SUBCALL_LOG — history of all sub-call invocations\n"
            "    .all() → list[dict]  |  .last(n) → list  |  .by_type(name) → list\n",
        ]

        subcall_lines = [
            _SUBCALL_HELP[name] for name in _SUBCALL_HELP if show_all or (enabled_subcalls and name in enabled_subcalls)
        ]
        if subcall_lines:
            parts.append(
                "\nSUB-CALLS (use an LLM to process data):\n"
                + "".join(subcall_lines)
                + "  text = llm_query(prompt) → str — general-purpose LLM call\n"
            )

        parts.append(
            "\nPARALLEL EXECUTION:\n"
            "  results = parallel([lambda: fn1(), lambda: fn2(), ...])\n"
            "    Run callables concurrently. Returns results in input order.\n"
            "    Failed items are ParallelError(index, error) — check with isinstance().\n"
            "  fill_parallel(generator, section_ids=None)\n"
            "    Fill unlocked template sections in parallel.\n"
            "    generator(section_id, context, guidance) → dict of field values.\n"
        )

        parts.append(
            "\nREPORT TEMPLATE (when 'report' variable exists):\n"
            "  report.fill_section(section_id, content_dict) → str\n"
            "    Returns a message string. Check for errors by reading the return value.\n"
            "  report.get_status() → TemplateStatus\n"
            "    .total_sections, .completed_sections, .unlocked, .pending, .completed\n"
            "  report.get_section_context(section_id) → dict\n"
            "  report.get_writing_guidance(section_id) → list[str]\n"
            "  report.get_dependencies(section_id) → list[str]\n"
            "  report.submit() → str — submit the completed report\n"
        )
        return "".join(parts)

    return help_fn


def _build_var_summary(repl: ReplEnvironment) -> dict[str, str]:
    """Build a type-hint summary of REPL variables matching script format."""
    summary: dict[str, str] = {}
    for name, type_name in repl.list_variables().items():
        val = repl.get_variable(name)
        if val is None:
            summary[name] = "None"
        elif isinstance(val, str):
            summary[name] = f"str({len(val):,})"
        elif isinstance(val, dict):
            summary[name] = f"dict({len(val)})"
        elif isinstance(val, list | tuple):
            summary[name] = f"list({len(val)})"
        else:
            summary[name] = type_name
    return summary


class RlmAdapter:
    """Adapter that runs a recursive REPL loop driven by an LLM client.

    Each iteration the model generates text that may contain a ```repl code
    block.  Code blocks are executed in a persistent ReplEnvironment and
    metadata about the execution is fed back.  The loop terminates when:

    - The model emits FINAL, calls FINAL_VAR(), or done=True on the response
    - The guardrail iteration cap or token budget is reached
    - A provider error occurs
    - The hard ceiling on per-call context size is hit
    """

    @classmethod
    def declare_capabilities(cls) -> AdapterCapabilities:
        """Declare which constitutional mechanisms this adapter supports."""
        return AdapterCapabilities(
            has_context_filtering=True,
            has_state_persistence=True,
            has_compaction=True,
            has_scaffolding=True,
            has_review_phase=True,
            has_source_tracing=True,
        )

    def __init__(
        self,
        *,
        adapter_name: str,
        model_name: str,
        client: RlmClient,
        guardrails: GuardrailConfig | None = None,
        execution: ExecutionConfig | None = None,
        hints: list[str] | None = None,
        subcall_client: RlmClient | None = None,
        subcall_model: str | None = None,
        subcall_configs: dict[str, SubcallConfig] | None = None,
        template: ReportTemplate | None = None,
        compaction_client: RlmClient | None = None,
        trajectory_writer: Any | None = None,
        scratchpad_path: str | None = None,
        external_system_prompt: str = "",
        workspace_path: str | None = None,
        prohibited: list[str] | None = None,
        advisor_client: RlmClient | None = None,
        advisor_config: AdvisorConfig | None = None,
        constitution: ConstitutionManifest | None = None,
    ) -> None:
        self._adapter_name = adapter_name
        self._model_name = model_name
        self._client = client
        self._guardrail_config = guardrails or GuardrailConfig()
        self._execution_config = execution or ExecutionConfig()
        self._hints = hints
        self._prohibited = prohibited
        self._subcall_client = subcall_client
        self._subcall_model = subcall_model
        self._subcall_configs = subcall_configs
        self._template = template
        self._compaction_client = compaction_client
        self._trajectory_writer = trajectory_writer
        self._scratchpad_path = scratchpad_path
        self._external_system_prompt = external_system_prompt
        self._workspace_path = workspace_path
        self._advisor_client = advisor_client
        self._advisor_config = advisor_config
        self.constitution = constitution

    # -- Constitution builder helpers -------------------------------------------

    def build_context_filter(self) -> ContextFilter:
        """Create a ContextFilter from the resolved constitutional params.

        Falls back to default InformationMinimalityParams when no constitution
        is set (or when its information_minimality field is None), preserving
        legacy behaviour.
        """
        from aec_bench.contracts.constitution import InformationMinimalityParams

        params = (
            self.constitution.information_minimality
            if self.constitution and self.constitution.information_minimality
            else InformationMinimalityParams()
        )
        return ContextFilter(params)

    def build_scaffolding_state(self) -> ScaffoldingState:
        """Create a ScaffoldingState from the resolved constitutional params.

        Falls back to default ProgressObligationParams and EarnedAutonomyParams
        when no constitution is set, preserving legacy behaviour.
        """
        from aec_bench.contracts.constitution import (
            EarnedAutonomyParams,
            ProgressObligationParams,
        )

        progress = (
            self.constitution.progress_obligation
            if self.constitution and self.constitution.progress_obligation
            else ProgressObligationParams()
        )
        autonomy = (
            self.constitution.earned_autonomy
            if self.constitution and self.constitution.earned_autonomy
            else EarnedAutonomyParams()
        )
        enabled = self._execution_config.scaffolding
        return ScaffoldingState(
            enabled=enabled,
            progress_params=progress,
            autonomy_params=autonomy,
        )

    def build_effective_system_prompt(self) -> str:
        """Return the resolved system prompt, including the constitution block."""
        return _build_system_prompt(
            hints=self._hints,
            variables=None,
            prohibited=self._prohibited,
            external_system_prompt=self._external_system_prompt,
            constitution=self.constitution,
        )

    def resolve_state_persistence_params(self) -> StatePersistenceParams:
        """Return state persistence params from the constitution or defaults."""
        from aec_bench.contracts.constitution import StatePersistenceParams

        if self.constitution and self.constitution.state_persistence:
            return self.constitution.state_persistence
        return StatePersistenceParams()

    # -- REPL command loading ----------------------------------------------------

    def _load_repl_commands(self, repl: ReplEnvironment) -> None:
        """Load task-specific REPL commands from workspace/repl_commands.py.

        Mirrors the loading logic in the legacy rlm_script.py: imports the
        module, reads template and validation data, and calls init_commands().
        """
        import importlib.util

        ws = Path(self._workspace_path)  # type: ignore[arg-type]
        commands_path = ws / "repl_commands.py"
        if not commands_path.exists():
            return

        spec = importlib.util.spec_from_file_location("repl_commands", str(commands_path))
        if spec is None or spec.loader is None:
            logger.warning("Could not load repl_commands.py — spec creation failed")
            return

        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        if not hasattr(mod, "init_commands"):
            logger.info("repl_commands.py has no init_commands — skipping")
            return

        template_data: dict[str, Any] = {}
        validation_data: dict[str, Any] = {}

        tpl_path = ws / "report_template.toml"
        if tpl_path.exists():
            import tomllib

            template_data = tomllib.loads(tpl_path.read_text())

        val_path = ws / "validation_rules.toml"
        if val_path.exists():
            import tomllib

            validation_data = tomllib.loads(val_path.read_text())

        mod.init_commands(
            repl_env=repl,
            template=self._template,
            template_data=template_data,
            validation_data=validation_data,
            workspace=self._workspace_path,
        )
        logger.info("REPL commands loaded from %s", commands_path)

    # -- Progress logging --------------------------------------------------------

    def _emit(self, tag: str, message: str) -> None:
        """Write a real-time progress line to stderr."""
        sys.stderr.write(f"[{tag:12s}] {message}\n")
        sys.stderr.flush()

    # -- Adapter protocol -------------------------------------------------------

    def execute(self, request: AdapterRequest) -> AdapterResult:
        """Run the REPL loop and return an AdapterResult."""
        repl = ReplEnvironment()
        error_tracker = ErrorTracker()
        gc = self._guardrail_config
        ec = self._execution_config
        guardrails = GuardrailState(
            token_budget=gc.token_budget,
            max_iterations=gc.max_iterations,
            max_subcall_depth=gc.max_subcall_depth,
            budget_warning_pct=gc.budget_warning_pct,
            max_subcalls=gc.max_subcalls,
            max_budget_usd=gc.max_budget_usd,
            billable_input_budget=gc.billable_input_budget,
        )
        token_tracker = TokenTracker(context_limit=ec.context_limit)
        scaffolding = self.build_scaffolding_state()
        ctx_filter = self.build_context_filter()

        transcript = initialize_transcript(request)
        system_prompt = self.build_effective_system_prompt()

        # --- Inject protected scaffolding into REPL ---
        final_var_fn = _make_final_var(repl)
        scaffolds: dict[str, Any] = {}

        repl.inject_object("FINAL_VAR", final_var_fn, protected=True)
        scaffolds["FINAL_VAR"] = final_var_fn
        repl.inject_object("FINAL", final_var_fn, protected=True)
        scaffolds["FINAL"] = final_var_fn
        repl.inject_object("context", request.instruction, protected=True)
        scaffolds["context"] = request.instruction

        show_vars_fn = _make_show_vars(repl)
        repl.inject_object("SHOW_VARS", show_vars_fn, protected=True)
        scaffolds["SHOW_VARS"] = show_vars_fn
        enabled_subcalls: set[str] | None = None
        if self._subcall_configs is not None:
            enabled_subcalls = {name for name, cfg in self._subcall_configs.items() if cfg.enabled}
        help_fn = _make_help(enabled_subcalls=enabled_subcalls)
        repl.inject_object("HELP", help_fn, protected=True)
        scaffolds["HELP"] = help_fn

        # --- Scratchpad ---
        scratchpad: Scratchpad | None = None
        if self._scratchpad_path:
            scratchpad = Scratchpad(path=self._scratchpad_path)
            repl.inject_object("NOTE", scratchpad.note, protected=True)
            scaffolds["NOTE"] = scratchpad.note
            repl.inject_object("RECALL", scratchpad.recall, protected=True)
            scaffolds["RECALL"] = scratchpad.recall

        # --- Inject sub-call functions into REPL ---
        subcall_log = SubcallLog()
        _cb_lock = threading.Lock()
        if self._subcall_configs:
            sc_client = self._subcall_client or self._client

            sc_model = self._subcall_model or self._model_name

            def _subcall_token_cb(inp: int, out: int) -> None:
                with _cb_lock:
                    sc_cost = (
                        estimate_cost_usd(
                            sc_model,
                            input_tokens=inp,
                            output_tokens=out,
                        )
                        or 0.0
                    )
                    token_tracker.record_subcall(
                        input_tokens=inp,
                        output_tokens=out,
                        cost_usd=sc_cost,
                    )
                    guardrails.record_subcall_tokens(
                        input_tokens=inp,
                        output_tokens=out,
                        cost_usd=sc_cost,
                    )

            functions = build_subcall_functions(
                configs=self._subcall_configs,
                client=sc_client,
                model=self._subcall_model or self._model_name,
                token_callback=_subcall_token_cb,
                subcall_log=subcall_log,
                template=self._template,
            )
            for name, fn in functions.items():
                repl.inject_object(name, fn, protected=True)
                scaffolds[name] = fn

        repl.inject_object("SUBCALL_LOG", subcall_log, protected=True)
        scaffolds["SUBCALL_LOG"] = subcall_log

        # --- Inject parallel execution into REPL ---
        _default_workers = ec.max_parallel_workers

        def _bound_parallel(callables, max_workers=None):
            return parallel(callables, max_workers=max_workers or _default_workers)

        repl.inject_object("parallel", _bound_parallel, protected=True)
        scaffolds["parallel"] = _bound_parallel

        # --- Inject template into REPL ---
        if self._template is not None:
            repl.inject_object("report", self._template)

            # Build fill_parallel bound to this template
            def _bound_fill_parallel(generator, section_ids=None, max_workers=None):
                return _fill_parallel(
                    template=self._template,
                    generator=generator,
                    section_ids=section_ids,
                    max_workers=max_workers or _default_workers,
                )

            repl.inject_object("fill_parallel", _bound_fill_parallel, protected=True)
            scaffolds["fill_parallel"] = _bound_fill_parallel

        # --- Inject grep for targeted text search ---
        def _grep(text: str, pattern: str, context: int = 3) -> str:
            """Search text for a regex pattern, returning matching lines with context."""
            import re as _re

            lines = text.split("\n")
            matches: list[str] = []
            try:
                compiled = _re.compile(pattern, _re.IGNORECASE)
            except _re.error as exc:
                return f"Invalid regex: {exc}"
            for i, line in enumerate(lines):
                if compiled.search(line):
                    start = max(0, i - context)
                    end = min(len(lines), i + context + 1)
                    chunk = "\n".join(f"{'>' if j == i else ' '} {j + 1:4d}: {lines[j]}" for j in range(start, end))
                    matches.append(chunk)
            if not matches:
                return f"No matches for /{pattern}/"
            header = f"{len(matches)} match(es) for /{pattern}/:\n"
            return header + "\n---\n".join(matches)

        repl.inject_object("grep", _grep, protected=True)
        scaffolds["grep"] = _grep

        # --- Inject ADVISOR function if configured ---
        if self._advisor_client and self._advisor_config and self._advisor_config.enabled:
            # Deferred import to avoid circular dependency via rlm/__init__.py
            from aec_bench.adapters.advisor import AdvisorResult, default_advise

            advisor_calls_made = 0
            _advisor_max = self._advisor_config.max_uses
            _advisor_model = self._advisor_config.model
            _advisor_client = self._advisor_client
            _advisor_max_tokens = self._advisor_config.max_response_tokens
            _advisor_context_window = self._advisor_config.context_window

            def _advisor_fn(
                *,
                goal: str,
                problem: str,
                attempt: str | None = None,
            ) -> AdvisorResult:
                nonlocal advisor_calls_made
                if advisor_calls_made >= _advisor_max:
                    budget_msg = (
                        f"Advisor budget exhausted ({_advisor_max}/{_advisor_max} calls used). Proceed on your own."
                    )
                    return AdvisorResult(
                        response=AdvisorResponse(
                            advice=budget_msg,
                            suggested_action="continue",
                            confidence=0.0,
                            reasoning="max_uses reached",
                        ),
                        input_tokens=0,
                        output_tokens=0,
                        error="max_uses_exhausted",
                    )

                context_msgs: list[dict[str, str]] = []
                if self._template:
                    status = self._template.get_status()
                    done = status.completed_sections
                    total = status.total_sections
                    progress_content = (
                        f"Template progress: {done}/{total} "
                        f"sections complete. "
                        f"Completed: {status.completed}. "
                        f"Unlocked: {status.unlocked}. "
                        f"Pending: {status.pending}."
                    )
                    context_msgs.append(
                        {
                            "role": "system",
                            "content": progress_content,
                        }
                    )
                if scratchpad:
                    keys = scratchpad.recall()
                    if keys:
                        context_msgs.append(
                            {
                                "role": "system",
                                "content": f"Scratchpad keys: {keys}",
                            }
                        )
                recent = [
                    {"role": e.role.value, "content": e.content}
                    for e in transcript[-_advisor_context_window:]
                    if e.content
                ]
                context_msgs.extend(recent)

                request_obj = AdvisorRequest(goal=goal, problem=problem, attempt=attempt)
                result = default_advise(
                    request=request_obj,
                    context_messages=context_msgs,
                    client=_advisor_client,
                    model=_advisor_model,
                    max_response_tokens=_advisor_max_tokens,
                    adapter_context=(
                        "The executor is using an RLM template with "
                        "REPL commands (FILL, SUBMIT, CONTEXT, etc.). "
                        "Guide it on which commands and approach to "
                        "use next."
                    ),
                )

                if result.error is None:
                    advisor_calls_made += 1

                traj = self._trajectory_writer
                if traj is not None:
                    resp = result.response
                    advisor_output = {
                        "advice": resp.advice if resp else "",
                        "suggested_action": (resp.suggested_action if resp else ""),
                        "confidence": (resp.confidence if resp else 0.0),
                        "reasoning": (resp.reasoning if resp else ""),
                    }
                    traj.tool_result(
                        "advisor",
                        stdout=resp.advice if resp else "",
                        metadata={
                            "advisor": True,
                            "advisor_input": {
                                "goal": goal,
                                "problem": problem,
                                "attempt": attempt,
                            },
                            "advisor_output": advisor_output,
                            "advisor_tokens": {
                                "input": result.input_tokens,
                                "output": result.output_tokens,
                            },
                            "advisor_call_number": (advisor_calls_made),
                            "advisor_calls_remaining": (_advisor_max - advisor_calls_made),
                        },
                    )

                return result

            repl.inject_object("ADVISOR", _advisor_fn, protected=True)
            scaffolds["ADVISOR"] = _advisor_fn

        # --- Load task-specific REPL commands ---
        if self._workspace_path and ec.scaffolding:
            self._load_repl_commands(repl)

        # --- REPL text-parsing loop ---
        traj = self._trajectory_writer
        if traj is not None:
            traj.system(system_prompt)
            traj.user(request.instruction)

        conversation: list[RlmMessage] = [
            RlmMessage(role="user", content=request.instruction),
        ]
        total_input_tokens = 0
        total_output_tokens = 0
        prev_var_names: set[str] = set()
        compaction_count = 0
        use_tool_use = hasattr(self._client, "generate_with_tools")

        while True:  # outer loop: restarts after compaction
            compacted_this_pass = False

            while True:  # inner loop: normal REPL iterations
                # --- guardrail pre-check ---
                verdict = guardrails.check()
                if not verdict.can_continue:
                    logger.info("Guardrail stop: %s", verdict.stop_reason)
                    self._close_trajectory(traj)
                    return self._build_result(
                        request=request,
                        transcript=transcript,
                        status=AgentOutputStatus.PARTIAL,
                        failure_kind=AdapterFailureKind.TURN_LIMIT_REACHED,
                        error_message=verdict.stop_reason,
                        usage_input=total_input_tokens,
                        usage_output=total_output_tokens,
                    )

                # --- model call ---
                iteration = guardrails.iteration_count
                if iteration <= 1:
                    self._emit(
                        "model",
                        f"calling {self._model_name}{'  (tool_use)' if use_tool_use else ''}...",
                    )
                if use_tool_use:
                    response = self._client.generate_with_tools(
                        model=self._model_name,
                        messages=conversation,
                        system_prompt=system_prompt,
                        tool_name=_REPL_TOOL_NAME,
                        tool_description=_REPL_TOOL_DESCRIPTION,
                        tool_parameters_schema=_REPL_TOOL_SCHEMA,
                    )
                else:
                    response = self._client.generate(
                        model=self._model_name,
                        messages=conversation,
                        system_prompt=system_prompt,
                    )

                total_input_tokens += response.input_tokens
                total_output_tokens += response.output_tokens
                call_cost = (
                    estimate_cost_usd(
                        self._model_name,
                        input_tokens=response.input_tokens,
                        output_tokens=response.output_tokens,
                        cache_read_tokens=response.cache_read_tokens,
                        cache_write_tokens=response.cache_write_tokens,
                    )
                    or 0.0
                )
                guardrails.record_iteration(
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    cost_usd=call_cost,
                    cache_read_tokens=response.cache_read_tokens,
                )
                turn_metrics = token_tracker.record_turn(
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    cache_read_tokens=response.cache_read_tokens,
                    cache_write_tokens=response.cache_write_tokens,
                )

                # --- provider error ---
                if response.error_message is not None:
                    logger.warning("Provider error: %s", response.error_message)
                    transcript.append(
                        TranscriptEntry(
                            role=TranscriptRole.ASSISTANT,
                            content=response.error_message,
                            usage=TokenUsage(
                                input_tokens=response.input_tokens,
                                output_tokens=response.output_tokens,
                            ),
                        )
                    )
                    self._close_trajectory(traj)
                    return self._build_result(
                        request=request,
                        transcript=transcript,
                        status=AgentOutputStatus.FAILED,
                        failure_kind=AdapterFailureKind.PROVIDER_ERROR,
                        error_message=response.error_message,
                        raw_output_text=response.output_text or None,
                        usage_input=total_input_tokens,
                        usage_output=total_output_tokens,
                    )

                # --- tool_call path (structural tool_use responses) ---
                if response.tool_call is not None:
                    code = response.tool_call.code
                    exec_result = repl.execute(code)
                    repl.restore_protected(scaffolds)

                    iteration = guardrails.iteration_count

                    # Error tracking
                    if exec_result.error:
                        error_tracker.record(
                            level=ErrorLevel.REPL,
                            iteration=iteration,
                            error=exec_result.error,
                            code_attempted=code,
                        )
                        logger.debug(
                            "REPL error at iteration %d: %s",
                            iteration,
                            exec_result.error.strip().split("\n")[-1],
                        )

                    # Variable changes
                    current_vars = set(repl.list_variables().keys())
                    all_new = current_vars - prev_var_names
                    # Filter out single-char loop variables (e.g. `for d in data`)
                    new_vars = sorted(v for v in all_new if len(v) > 1)
                    removed_vars = sorted(prev_var_names - current_vars)
                    prev_var_names = current_vars
                    var_diff = {"new": new_vars, "removed": removed_vars}

                    # Trajectory writing
                    if traj is not None:
                        traj.new_step()
                        traj.tool_call("repl", code)
                        step_meta = self._build_step_metadata(
                            repl=repl,
                            scratchpad=scratchpad,
                            turn_metrics_tokens={
                                "call_input": turn_metrics.call_input_tokens,
                                "grand_total": turn_metrics.grand_total_tokens,
                            },
                            var_diff=var_diff,
                        )
                        stdout = exec_result.error or exec_result.stdout or "(no output)"
                        traj.tool_result("repl", stdout=stdout, metadata=step_meta)

                    # Progress logging
                    code_preview = _format_code_preview(code)
                    template_info = ""
                    if self._template:
                        ts = self._template.get_status()
                        template_info = f" [{ts.completed_sections}/{ts.total_sections} sections]"
                    cost_info = f"${guardrails.total_cost_usd:.3f}" if guardrails.total_cost_usd else ""
                    token_info = f"{turn_metrics.call_input_tokens:,}in/{response.output_tokens:,}out"
                    var_info = f" +{new_vars}" if new_vars else ""
                    err_flag = " ERR" if exec_result.error else ""
                    self._emit(
                        f"turn {iteration}",
                        f"{code_preview} ({token_info} {cost_info}{var_info}{err_flag})",
                    )

                    # Transcript: full output for debugging/viewing
                    if response.output_text:
                        transcript.append(
                            TranscriptEntry(
                                role=TranscriptRole.ASSISTANT,
                                content=response.output_text,
                                usage=TokenUsage(
                                    input_tokens=response.input_tokens,
                                    output_tokens=response.output_tokens,
                                ),
                            )
                        )
                    full_output = exec_result.error or exec_result.stdout or "(no output)"
                    var_snapshot = repl.snapshot_variables()
                    if var_snapshot:
                        full_output += "\n--- variables ---\n" + json.dumps(var_snapshot, indent=2, default=str)

                    # Scaffolding footer — computed once, appended to both the
                    # LLM-visible context_msg and the transcript so runs can be
                    # audited for nudge delivery.
                    footer = ""
                    if self._template:
                        template_status = self._template.get_status()
                        footer = scaffolding.build_footer(
                            template_status=template_status,
                            scratchpad_keys=scratchpad.keys if scratchpad else [],
                        )

                    transcript.append(
                        TranscriptEntry(
                            role=TranscriptRole.TOOL,
                            content=full_output + (footer or ""),
                            event=TranscriptEvent.TOOL_RESULT,
                            tool_name="repl",
                        )
                    )

                    # Conversation: context-filtered output + variable diff
                    context_msg = ctx_filter.build_context_message(
                        stdout=exec_result.stdout,
                        error=exec_result.error,
                        code=code,
                        new_vars=new_vars if new_vars else None,
                    )
                    var_diff_text = ctx_filter.format_var_diff(
                        new=new_vars,
                        removed=removed_vars,
                        repl_vars={
                            name: repl.get_variable(name) for name in new_vars if repl.get_variable(name) is not None
                        },
                    )
                    if var_diff_text:
                        context_msg += "\n" + var_diff_text

                    if footer:
                        context_msg += footer

                    if response.output_text:
                        conversation.append(
                            RlmMessage(role="assistant", content=response.output_text),
                        )
                    conversation.append(
                        RlmMessage(
                            role="tool_call",
                            content=code,
                            tool_call_id=response.tool_call.call_id,
                            tool_name=response.tool_call.name,
                        )
                    )
                    conversation.append(
                        RlmMessage(
                            role="tool_result",
                            content=context_msg,
                            tool_call_id=response.tool_call.call_id,
                            tool_name=response.tool_call.name,
                        )
                    )

                    # Check FINAL
                    is_final = repl.final_called
                    if is_final:
                        self._emit(
                            "done",
                            f"{iteration} turns, "
                            f"{total_input_tokens + total_output_tokens:,} tokens, "
                            f"${guardrails.total_cost_usd:.3f}",
                        )
                        self._close_trajectory(traj)
                        return self._build_result(
                            request=request,
                            transcript=transcript,
                            status=AgentOutputStatus.COMPLETED,
                            raw_output_text=response.output_text or None,
                            usage_input=total_input_tokens,
                            usage_output=total_output_tokens,
                        )

                    # Scaffolding progress tracking
                    if self._template:
                        completed = self._template.get_status().completed_sections
                        scaffolding.record_progress(completed)

                    # Compaction check (per-call context)
                    if token_tracker.needs_compaction(
                        turn_metrics.call_input_tokens,
                        ec.compaction_threshold_pct,
                    ):
                        compaction_model = ec.compaction_model or self._model_name
                        compaction_client = self._compaction_client or self._client
                        compaction_result = compact(
                            client=compaction_client,
                            model=compaction_model,
                            repl=repl,
                            scratchpad=scratchpad,
                            template=self._template,
                            params=self.resolve_state_persistence_params(),
                        )
                        summary = compaction_result.summary
                        compaction_count += 1
                        self._emit(
                            "compaction",
                            f"#{compaction_count} — {len(summary):,} char summary, "
                            f"{compaction_result.input_tokens:,}in/"
                            f"{compaction_result.output_tokens:,}out",
                        )

                        compaction_cost = (
                            estimate_cost_usd(
                                compaction_model,
                                input_tokens=compaction_result.input_tokens,
                                output_tokens=compaction_result.output_tokens,
                            )
                            or 0.0
                        )
                        token_tracker.record_compaction(
                            input_tokens=compaction_result.input_tokens,
                            output_tokens=compaction_result.output_tokens,
                            cost_usd=compaction_cost,
                        )

                        if traj is not None:
                            traj.new_step()
                            traj.tool_result(
                                "compaction",
                                stdout=summary[:500],
                                metadata={
                                    "compaction": {
                                        "number": compaction_count + 1,
                                        "pre_messages": len(conversation),
                                        "summary_chars": len(summary),
                                        "model": str(compaction_model),
                                    }
                                },
                            )

                        conversation = [
                            RlmMessage(
                                role="user",
                                content=f"[Progress Summary]\n{summary}",
                            ),
                            RlmMessage(
                                role="user",
                                content=("Continue working on the task. Use RECALL() to retrieve your extracted data."),
                            ),
                        ]
                        token_tracker.reset_for_compaction()
                        scaffolding.mark_compacted()

                        logger.info(
                            "Compaction #%d: %d chars summary, model=%s",
                            compaction_count,
                            len(summary),
                            compaction_model,
                        )

                        compacted_this_pass = True
                        break  # break inner loop, restart outer loop

                    # Hard ceiling check
                    if token_tracker.hit_hard_ceiling(
                        turn_metrics.call_input_tokens,
                        ec.hard_ceiling_pct,
                    ):
                        logger.warning(
                            "Hard ceiling hit: %d tokens (%.0f%% of %d)",
                            turn_metrics.call_input_tokens,
                            ec.hard_ceiling_pct * 100,
                            ec.context_limit,
                        )
                        self._close_trajectory(traj)
                        return self._build_result(
                            request=request,
                            transcript=transcript,
                            status=AgentOutputStatus.PARTIAL,
                            failure_kind=AdapterFailureKind.TURN_LIMIT_REACHED,
                            error_message="Hard ceiling on context size reached.",
                            raw_output_text=response.output_text or None,
                            usage_input=total_input_tokens,
                            usage_output=total_output_tokens,
                        )

                    continue  # next iteration

                # --- text-parsing path (backward compat with ReplayRlmClient) ---
                # Record assistant message in transcript
                transcript.append(
                    TranscriptEntry(
                        role=TranscriptRole.ASSISTANT,
                        content=response.output_text,
                        usage=TokenUsage(
                            input_tokens=response.input_tokens,
                            output_tokens=response.output_tokens,
                        ),
                    )
                )

                # Parse code blocks, execute FIRST only (tool_use stop)
                code_blocks = parse_code_blocks(response.output_text)
                iteration = guardrails.iteration_count

                if code_blocks:
                    code = code_blocks[0]
                    exec_result = repl.execute(code)
                    repl.restore_protected(scaffolds)

                    # Truncate response to first block — simulates tool_use
                    # stop behaviour so the model re-plans after seeing results.
                    effective_response = truncate_after_first_block(response.output_text)
                    if len(code_blocks) > 1:
                        logger.info(
                            "Truncated %d extra code blocks from response (first-block-only execution)",
                            len(code_blocks) - 1,
                        )

                    if exec_result.error:
                        error_tracker.record(
                            level=ErrorLevel.REPL,
                            iteration=iteration,
                            error=exec_result.error,
                            code_attempted=code,
                        )
                        logger.debug(
                            "REPL error at iteration %d: %s",
                            iteration,
                            exec_result.error.strip().split("\n")[-1],
                        )

                    # Track variable changes
                    current_vars = set(repl.list_variables().keys())
                    all_new = current_vars - prev_var_names
                    # Filter out single-char loop variables (e.g. `for d in data`)
                    new_vars = sorted(v for v in all_new if len(v) > 1)
                    removed_vars = sorted(prev_var_names - current_vars)
                    prev_var_names = current_vars
                    var_diff = {"new": new_vars, "removed": removed_vars}

                    # Trajectory writing
                    if traj is not None:
                        traj.new_step()
                        traj.tool_call("repl", code)
                        step_meta = self._build_step_metadata(
                            repl=repl,
                            scratchpad=scratchpad,
                            turn_metrics_tokens={
                                "call_input": turn_metrics.call_input_tokens,
                                "grand_total": turn_metrics.grand_total_tokens,
                            },
                            var_diff=var_diff,
                        )
                        stdout = exec_result.error or exec_result.stdout or "(no output)"
                        traj.tool_result("repl", stdout=stdout, metadata=step_meta)

                    # --- Progress logging ---
                    code_preview = _format_code_preview(code)
                    template_info = ""
                    if self._template:
                        ts = self._template.get_status()
                        template_info = f" [{ts.completed_sections}/{ts.total_sections} sections]"
                    cost_info = f"${guardrails.total_cost_usd:.3f}" if guardrails.total_cost_usd else ""
                    token_info = f"{turn_metrics.call_input_tokens:,}in/{response.output_tokens:,}out"
                    var_info = f" +{new_vars}" if new_vars else ""
                    err_flag = " ERR" if exec_result.error else ""
                    self._emit(
                        f"turn {iteration}",
                        f"{code_preview} ({token_info} {cost_info}{template_info}{var_info}{err_flag})",
                    )

                    # Record REPL execution + variable snapshot in transcript
                    repl_output = exec_result.error or exec_result.stdout or "(no output)"
                    var_snapshot = repl.snapshot_variables()
                    if var_snapshot:
                        repl_output += "\n--- variables ---\n" + json.dumps(var_snapshot, indent=2, default=str)
                    transcript.append(
                        TranscriptEntry(
                            role=TranscriptRole.TOOL,
                            content=repl_output,
                            event=TranscriptEvent.TOOL_RESULT,
                            tool_name="repl",
                        )
                    )
                else:
                    exec_result = None
                    effective_response = response.output_text
                    text_preview = response.output_text.strip()[:80].replace("\n", " ")
                    self._emit(f"turn {iteration}", f"(text) {text_preview}")

                # --- Check FINAL marker — use effective (truncated) response ---
                is_final = repl.final_called or _FINAL_MARKER in effective_response or response.done

                # Early return interception: if the agent tries to finish on
                # the very first iteration without executing any code, force
                # a verification step. Agents that ran code (including
                # FINAL_VAR) did real work and are allowed through.
                if is_final and iteration == 1 and not code_blocks:
                    logger.info("Early return intercepted at iteration 0 — forcing verification")
                    is_final = False
                    repl.final_called = False
                    conversation.append(
                        RlmMessage(role="assistant", content=response.output_text),
                    )
                    conversation.append(
                        RlmMessage(
                            role="user",
                            content=(
                                "[Early return intercepted] You returned on the first "
                                "iteration without doing any work in the REPL. Verify "
                                "your answer is correct by reading the task, extracting "
                                "the relevant data, and checking your result before "
                                "calling FINAL_VAR()."
                            ),
                        ),
                    )
                    continue

                if is_final:
                    self._emit(
                        "done",
                        f"{iteration} turns, {total_input_tokens + total_output_tokens:,} tokens, "
                        f"${guardrails.total_cost_usd:.3f}",
                    )
                    status = AgentOutputStatus.COMPLETED if response.output_text else AgentOutputStatus.EMPTY
                    self._close_trajectory(traj)
                    return self._build_result(
                        request=request,
                        transcript=transcript,
                        status=status,
                        failure_kind=(None if response.output_text else AdapterFailureKind.MISSING_OUTPUT),
                        raw_output_text=response.output_text or None,
                        usage_input=total_input_tokens,
                        usage_output=total_output_tokens,
                    )

                # --- Scaffolding progress tracking ---
                if self._template:
                    completed = self._template.get_status().completed_sections
                    scaffolding.record_progress(completed)

                # --- Compaction check (per-call context) ---
                if token_tracker.needs_compaction(
                    turn_metrics.call_input_tokens,
                    ec.compaction_threshold_pct,
                ):
                    compaction_model = ec.compaction_model or self._model_name
                    compaction_client = self._compaction_client or self._client
                    compaction_result = compact(
                        client=compaction_client,
                        model=compaction_model,
                        repl=repl,
                        scratchpad=scratchpad,
                        template=self._template,
                        params=self.resolve_state_persistence_params(),
                    )
                    summary = compaction_result.summary
                    compaction_count += 1
                    self._emit(
                        "compaction",
                        f"#{compaction_count} — {len(summary):,} char summary, "
                        f"{compaction_result.input_tokens:,}in/{compaction_result.output_tokens:,}out",
                    )

                    # Track compaction tokens and cost
                    compaction_cost = (
                        estimate_cost_usd(
                            compaction_model,
                            input_tokens=compaction_result.input_tokens,
                            output_tokens=compaction_result.output_tokens,
                        )
                        or 0.0
                    )
                    token_tracker.record_compaction(
                        input_tokens=compaction_result.input_tokens,
                        output_tokens=compaction_result.output_tokens,
                        cost_usd=compaction_cost,
                    )

                    # Trajectory: compaction event
                    if traj is not None:
                        traj.new_step()
                        traj.tool_result(
                            "compaction",
                            stdout=summary[:500],
                            metadata={
                                "compaction": {
                                    "number": compaction_count + 1,
                                    "pre_messages": len(conversation),
                                    "summary_chars": len(summary),
                                    "model": str(compaction_model),
                                }
                            },
                        )

                    # Reset conversation to compacted summary
                    conversation = [
                        RlmMessage(
                            role="user",
                            content=f"[Progress Summary]\n{summary}",
                        ),
                        RlmMessage(
                            role="user",
                            content=("Continue working on the task. Use RECALL() to retrieve your extracted data."),
                        ),
                    ]
                    token_tracker.reset_for_compaction()
                    scaffolding.mark_compacted()

                    logger.info(
                        "Compaction #%d: %d chars summary, model=%s",
                        compaction_count,
                        len(summary),
                        compaction_model,
                    )

                    compacted_this_pass = True
                    break  # break inner loop, restart outer loop

                # --- Hard ceiling check ---
                if token_tracker.hit_hard_ceiling(
                    turn_metrics.call_input_tokens,
                    ec.hard_ceiling_pct,
                ):
                    logger.warning(
                        "Hard ceiling hit: %d tokens (%.0f%% of %d)",
                        turn_metrics.call_input_tokens,
                        ec.hard_ceiling_pct * 100,
                        ec.context_limit,
                    )
                    self._close_trajectory(traj)
                    return self._build_result(
                        request=request,
                        transcript=transcript,
                        status=AgentOutputStatus.PARTIAL,
                        failure_kind=AdapterFailureKind.TURN_LIMIT_REACHED,
                        error_message="Hard ceiling on context size reached.",
                        raw_output_text=response.output_text or None,
                        usage_input=total_input_tokens,
                        usage_output=total_output_tokens,
                    )

                # --- Format metadata with scaffolding footer ---
                template_status = self._template.get_status() if self._template else None
                footer = scaffolding.build_footer(
                    template_status=template_status,
                    scratchpad_keys=scratchpad.keys if scratchpad else [],
                )
                metadata = format_iteration_metadata(
                    result=exec_result,
                    variables=repl.list_variables(),
                    iteration=iteration,
                    token_budget_pct=guardrails.check().budget_consumed_pct,
                    template_status=template_status,
                )
                if footer:
                    metadata += footer

                conversation.append(
                    RlmMessage(role="assistant", content=effective_response),
                )
                conversation.append(RlmMessage(role="user", content=metadata))

            if not compacted_this_pass:
                break  # inner loop ended without compaction = done

    def adapter_name(self) -> str:
        return self._adapter_name

    def resolved_model(self) -> str:
        return self._model_name

    # -- Private helpers --------------------------------------------------------

    @staticmethod
    def _close_trajectory(traj: Any | None) -> None:
        """Close the trajectory writer if present."""
        if traj is not None:
            traj.close()

    def _build_step_metadata(
        self,
        *,
        repl: ReplEnvironment,
        scratchpad: Scratchpad | None,
        turn_metrics_tokens: dict[str, int],
        var_diff: dict[str, list[str]],
    ) -> dict[str, Any]:
        """Build per-step metadata for trajectory entries."""
        meta: dict[str, Any] = {
            "var_diff": var_diff,
            "scratchpad_keys": scratchpad.keys if scratchpad else [],
        }

        if self._template:
            status = self._template.get_status()
            meta["template_progress"] = {
                "completed": status.completed_sections,
                "total": status.total_sections,
                "filled": status.completed,
                "unlocked": status.unlocked,
            }

        meta["variables"] = _build_var_summary(repl)
        meta["tokens"] = turn_metrics_tokens
        return meta

    def _build_result(
        self,
        *,
        request: AdapterRequest,
        transcript: list[TranscriptEntry],
        status: AgentOutputStatus,
        failure_kind: AdapterFailureKind | None = None,
        error_message: str | None = None,
        raw_output_text: str | None = None,
        usage_input: int = 0,
        usage_output: int = 0,
    ) -> AdapterResult:
        configuration: dict[str, Any] = dict(request.configuration)
        return AdapterResult(
            adapter_name=self._adapter_name,
            resolved_model=self._model_name,
            configuration_record=record_effective_configuration(
                resolved_model=self._model_name,
                configuration=configuration,
            ),
            agent_output=AgentOutput(
                status=status,
                output_path=request.output_path,
                output_format=request.output_format,
                error_message=error_message,
            ),
            transcript=transcript,
            failure_kind=failure_kind,
            raw_output_text=raw_output_text,
            provider_error=error_message,
            usage_input_tokens=usage_input,
            usage_output_tokens=usage_output,
        )
