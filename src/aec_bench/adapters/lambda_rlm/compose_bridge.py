# ABOUTME: Lambda-rlm bridge to the compose-mode renderer — slot + block LLM resolvers.
# ABOUTME: Wires SlotResolver / BlockGenerator Protocols onto the existing RlmClient.

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox, parse_anchor_ref
from aec_bench.adapters.lambda_rlm.task_handlers import (
    ProsePromptContext,
    SlotPromptContext,
    get_prose_handler,
    get_slot_handler,
)

if TYPE_CHECKING:
    from aec_bench.adapters.lambda_rlm.sandbox_tools import SandboxToolHarness  # noqa: F401

from aec_bench.adapters.rlm.client import RlmClient, RlmMessage
from aec_bench.contracts.report_template import (
    Block,
    BlockTask,
    BoilerplateFragment,
    CompositionTrace,
)
from aec_bench.templates.report.composer import render_section

SourceResolver = Callable[[str], str]

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

_SLOT_SYSTEM_PROMPT_DEFAULT = (
    "You fill named slots in boilerplate fragments using only facts present "
    "in the provided source documents. Reply with a single JSON object whose "
    "keys are the requested slot names and whose values are short phrases "
    "drawn from the sources. Do not invent values."
)

_GENERATE_SYSTEM_PROMPT_BODY = (
    "You write project-specific paragraphs for an engineering Scope of Works "
    "using only facts present in the provided source documents. "
    "\n\n"
    "Every factual claim — certifications, standards, accreditations, dates, "
    "dollar amounts, rates, organisational facts, personnel titles, system "
    "capabilities — MUST be traceable to an explicit source (primary source "
    "documents, boilerplate fragments, or the scratchpad's slot values). "
    "DO NOT introduce claims from your own general knowledge, even when you "
    "believe them to be true. Common world-knowledge leaks to avoid: ISO or "
    "other certification numbers for a party that no source cites; company "
    "addresses, registration numbers, or bank details; software-version or "
    "vendor facts; professional-body memberships. If a fact is not evidenced "
    "in a cited source, OMIT it — do not infer, do not fill in, do not add "
    "plausible-sounding detail to round out a paragraph. "
    "\n\n"
    "If the scratchpad includes back_brief content, treat it strictly as a "
    "PHRASING, CLAUSE, and FORMATTING reference. NEVER import from back_brief "
    "any scope item, deliverable, exclusion, personnel, organisation, dollar "
    "amount, rate, date, standard, certification, or other project-specific "
    "fact — those belong to other engagements. Scope authority rests solely "
    "with the primary source documents (e.g. the email thread or instruction). "
    "If a fact is not evidenced in those primary sources, OMIT it. "
    "\n\n"
    "Write only text that would appear in the final signed document. Do NOT "
    "write drafter notes, editorial meta-commentary, or explanations of what "
    "is missing or why. Forbidden register: 'at the time of writing', "
    "'Entry cannot be finalised', 'has been omitted', 'No reference "
    "documentation was available', 'pending confirmation', 'source is "
    "silent', 'most probable identity is', 'most likely identity', "
    "'identified as likely', 'were not specified', 'were not stated', "
    "'no LinkedIn or other public profile', 'public profile was located', "
    "any URL pointing to linkedin.com or other research-trail sources. "
    "Missing information is represented by a bare [TBC] inline — "
    "not by narration around the [TBC], and not by speculation about who or "
    "what the missing item *might* be. Not-applicable sections read "
    "'Not applicable.' alone. "
    "\n"
    "  DO: 'Richard [surname TBC]' \n"
    "  DON'T: 'Richard''s surname is not stated in the thread; pending "
    "confirmation it is recorded here as [TBC].' \n"
    "  DO: 'Staff-hours breakdown per role: [TBC].' \n"
    "  DON'T: 'No specific hours breakdown per role was provided in the "
    "email thread. Accordingly, a staff-hours table cannot be included and "
    "has been omitted.' \n"
    "  DO: 'Project Lead: Richard [surname TBC], ExampleCo.' \n"
    "  DON'T: 'Project Lead: Richard, ExampleCo (most probable identity is "
    "Richard Smith, https://linkedin.com/in/...).' \n"
    "  DO: 'Programme: workshop week of [date TBC]; report two weeks "
    "thereafter.' \n"
    "  DON'T: 'Programme: dates marked [TBD] were not specified in the "
    "email thread.' \n"
    "\n"
    "Keep the prose concise and in formal "
)
_GENERATE_SYSTEM_PROMPT_DEFAULT_VOICE = "Formal contract voice."


def _build_slot_system_prompt(domain_override: str | None) -> str:
    if not domain_override:
        return _SLOT_SYSTEM_PROMPT_DEFAULT
    return _SLOT_SYSTEM_PROMPT_DEFAULT + f" Domain context: {domain_override}."


def _build_generate_system_prompt(voice_override: str | None) -> str:
    voice_clause = voice_override + "." if voice_override else _GENERATE_SYSTEM_PROMPT_DEFAULT_VOICE
    return _GENERATE_SYSTEM_PROMPT_BODY + voice_clause


@dataclass(frozen=True)
class ComposeStats:
    """Aggregate LLM usage from rendering one compose-mode section."""

    calls: int
    input_tokens: int
    output_tokens: int


def _extract_json_object(text: str) -> dict[str, str]:
    """Parse a JSON object from *text*, tolerating leading/trailing prose."""
    text = text.strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_OBJECT_RE.search(text)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(k): str(v) for k, v in parsed.items()}


def _format_sources(
    sources: Sequence[str],
    source_resolver: SourceResolver,
    back_brief: Mapping[str, str] | None = None,
) -> str:
    """Render source labels + their resolved content as a prompt block.

    Resolution order per label:
      1. If label looks like `references/*:<topic>` and `back_brief`
         contains a non-empty entry for `<topic>`, use that digest.
      2. Otherwise fall through to `source_resolver(label)`.

    Empty resolutions are dropped silently (unchanged behaviour).
    """
    parts = []
    for label in sources:
        content = ""
        if back_brief is not None and label.startswith("references/*:"):
            topic = label.split(":", 1)[1]
            content = back_brief.get(topic, "")
        if not content:
            content = source_resolver(label)
        if not content:
            continue
        parts.append(f"### Source: {label}\n{content}")
    return "\n\n".join(parts) if parts else "(no source content available)"


def _format_sandbox_sources(
    sources: Sequence[str],
    sandbox: DocumentSandbox,
    back_brief: Mapping[str, str] | None = None,
) -> str:
    """Render anchored source slices from *sandbox* as a prompt block.

    Resolution order per ref:
      1. If ref looks like ``references/*:<topic>`` and *back_brief* contains
         a non-empty entry for ``<topic>``, use that digest. Mirrors the
         legacy ``_format_sources`` behaviour so the back-brief topic-reference
         syntax keeps working when the sandbox path is enabled.
      2. Otherwise parse via :func:`parse_anchor_ref` and fetch the slice
         from the sandbox.

    Refs whose label is not registered in the sandbox, or whose anchor is
    missing on the document, are silently skipped (matches the legacy path).
    Refs that fail parsing entirely are also skipped silently — this keeps
    bespoke template syntaxes (e.g. ``references/*:topic``) from crashing
    the run when the sandbox is enabled.
    """
    parts: list[str] = []
    for ref in sources:
        # Back-brief topic reference takes precedence — the topic content
        # lives in the planning-phase scratchpad, not in the sandbox.
        if back_brief is not None and ref.startswith("references/*:"):
            topic = ref.split(":", 1)[1]
            content = back_brief.get(topic, "")
            if content:
                parts.append(f"### Source: {ref}\n{content}")
            continue

        try:
            label, anchor = parse_anchor_ref(ref)
        except ValueError:
            # Unparseable refs (template-specific syntaxes the sandbox doesn't
            # know about) are skipped rather than crashing the run.
            continue
        try:
            sl = sandbox.slice(label, anchor)
        except KeyError:
            continue
        anchor_label = anchor if anchor is not None else "whole"
        parts.append(f"### Source: {label} (anchor: {anchor_label})\n{sl.text}")
    return "\n\n".join(parts) if parts else "(no source content available)"


class LambdaRlmSlotResolver:
    """SlotResolver implementation backed by an RlmClient.

    When *scratchpad* is provided, slots already present there are returned
    without an LLM call, and LLM-resolved values are written back so later
    blocks can resolve via zero-LLM lookups. When *scratchpad* is None,
    every slot goes through the LLM.

    When *sandbox* is provided, each source reference is resolved to a
    document slice via DocumentSandbox.slice() and the slice text is embedded
    in the prompt. When *sandbox* is None, the legacy *source_resolver*
    callable path runs unchanged.
    """

    def __init__(
        self,
        *,
        client: RlmClient,
        model: str,
        source_resolver: SourceResolver,
        scratchpad: dict[str, str | dict[str, str]] | None = None,
        voice_override: str | None = None,
        domain_override: str | None = None,
        sandbox: DocumentSandbox | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._source_resolver = source_resolver
        self._scratchpad = scratchpad
        self._voice_override = voice_override
        self._domain_override = domain_override
        self._sandbox = sandbox
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.last_slot_provenance: dict[str, tuple[str, ...]] = {}

    def resolve(
        self,
        fragment: BoilerplateFragment,
        sources: Sequence[str],
        task: BlockTask = BlockTask.EXTRACT_FACT,
    ) -> Mapping[str, str]:
        self.last_slot_provenance = {}

        resolved: dict[str, str] = {}
        remaining: list[str] = []
        for slot in fragment.slots:
            if self._scratchpad is not None and slot in self._scratchpad:
                resolved[slot] = self._scratchpad[slot]
                # Scratchpad hits: no source consulted this call
                self.last_slot_provenance[slot] = ()
            else:
                remaining.append(slot)

        if not remaining:
            return resolved

        # Pull back-brief once; both paths route through it for
        # `references/*:<topic>` lookups.
        back_brief: Mapping[str, str] | None = None
        if self._scratchpad is not None:
            bb = self._scratchpad.get("_back_brief")
            if isinstance(bb, dict):
                back_brief = bb

        if self._sandbox is not None:
            sources_block = _format_sandbox_sources(
                sources,
                self._sandbox,
                back_brief=back_brief,
            )
        else:
            sources_block = _format_sources(
                sources,
                self._source_resolver,
                back_brief=back_brief,
            )

        handler = get_slot_handler(task)
        prompt = handler.build_prompt(
            SlotPromptContext(
                fragment=fragment,
                remaining_slots=tuple(remaining),
                sources_block=sources_block,
            ),
        )
        response = self._client.generate(
            model=self._model,
            messages=[RlmMessage(role="user", content=prompt)],
            system_prompt=_build_slot_system_prompt(self._domain_override),
        )
        self.calls += 1
        self.input_tokens += response.input_tokens
        self.output_tokens += response.output_tokens
        from_llm = handler.parse(response.output_text)
        resolved.update(from_llm)

        # Record provenance for every LLM-resolved slot
        sources_tuple = tuple(sources)
        for slot in from_llm:
            self.last_slot_provenance[slot] = sources_tuple

        if self._scratchpad is not None:
            for slot, value in from_llm.items():
                self._scratchpad[slot] = value

        return resolved


class LambdaRlmBlockGenerator:
    """BlockGenerator implementation backed by an RlmClient.

    When *scratchpad* is non-empty, its contents are injected into the
    prompt as a 'Known facts' block — the LLM can back-brief from slots
    already populated in the planning phase without re-extracting.

    When *sandbox* is provided, each source reference is resolved to a
    document slice via DocumentSandbox.slice() and the slice text is embedded
    in the prompt. When *sandbox* is None, the legacy *source_resolver*
    callable path runs unchanged.
    """

    def __init__(
        self,
        *,
        client: RlmClient,
        model: str,
        source_resolver: SourceResolver,
        scratchpad: dict[str, str | dict[str, str]] | None = None,
        voice_override: str | None = None,
        domain_override: str | None = None,
        sandbox: DocumentSandbox | None = None,
        tool_harness: SandboxToolHarness | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._source_resolver = source_resolver
        self._scratchpad = scratchpad
        self._voice_override = voice_override
        self._domain_override = domain_override
        self._sandbox = sandbox
        self._tool_harness = tool_harness
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.last_provenance: tuple[str, ...] = ()
        self.last_declared_provenance: tuple[str, ...] = ()
        self.last_fetched_provenance: tuple[str, ...] = ()
        self.last_prompt: str = ""

    def generate(
        self,
        prompt: str,
        sources: Sequence[str],
        task: BlockTask = BlockTask.SYNTHESISE_NARRATIVE,
    ) -> str:
        self.last_provenance = ()
        self.last_declared_provenance = tuple(sources)
        self.last_fetched_provenance = ()
        self.last_prompt = ""

        if self._tool_harness is not None and self._tool_harness.enabled:
            self._tool_harness.reset_block_counter()
            fetched_before = len(self._tool_harness.fetched_anchors())
        else:
            fetched_before = 0

        back_brief = None
        scope_evolution = None
        if self._scratchpad is not None:
            bb = self._scratchpad.get("_back_brief")
            if isinstance(bb, dict):
                back_brief = bb
            se = self._scratchpad.get("_scope_evolution")
            if isinstance(se, str) and se:
                scope_evolution = se

        if self._sandbox is not None:
            sources_block = _format_sandbox_sources(
                sources,
                self._sandbox,
                back_brief=back_brief,
            )
        else:
            sources_block = _format_sources(
                sources,
                self._source_resolver,
                back_brief=back_brief,
            )

        known_facts = self._format_known_facts() or None

        handler = get_prose_handler(task)
        full_prompt = handler.build_prompt(
            ProsePromptContext(
                user_prompt=prompt,
                sources_block=sources_block,
                known_facts=known_facts,
                scope_evolution=scope_evolution,
            ),
        )

        self.last_prompt = full_prompt

        response = self._client.generate(
            model=self._model,
            messages=[RlmMessage(role="user", content=full_prompt)],
            system_prompt=_build_generate_system_prompt(self._voice_override),
        )
        self.calls += 1
        self.input_tokens += response.input_tokens
        self.output_tokens += response.output_tokens

        if self._tool_harness is not None and self._tool_harness.enabled:
            all_fetched = self._tool_harness.fetched_anchors()
            self.last_fetched_provenance = all_fetched[fetched_before:]
        self.last_provenance = self.last_declared_provenance + self.last_fetched_provenance

        return handler.parse(response.output_text)

    def _format_known_facts(self) -> str:
        # None and {} are equivalent here — unlike the resolver, the generator
        # has no write-back path, so there's no reason to distinguish them.
        # Scratchpad values are assumed to be short single-line strings
        # (slot values like "North Plant", "Sarah Lee"); newlines in values would
        # produce ambiguous continuation lines but are not expected in practice.
        # Reserved keys `_back_brief` and `_scope_evolution` are filtered
        # out — they are surfaced through their own prompt sections, not
        # as flat slot facts.
        if not self._scratchpad:
            return ""
        return "\n".join(
            f"- {k}: {v}" for k, v in self._scratchpad.items() if k not in ("_back_brief", "_scope_evolution")
        )


def render_compose_section(
    *,
    blocks: Sequence[Block],
    fragments: Mapping[str, Any],
    client: RlmClient,
    model: str,
    source_resolver: SourceResolver,
    scratchpad: dict[str, str | dict[str, str]] | None = None,
    voice_override: str | None = None,
    domain_override: str | None = None,
    sandbox: DocumentSandbox | None = None,
    tool_harness: SandboxToolHarness | None = None,
) -> tuple[str, CompositionTrace, ComposeStats]:
    """Render a compose-mode section using lambda-rlm's LLM client.

    Returns the assembled text, the per-block :class:`CompositionTrace`, and
    aggregate token / call stats so the executor can fold them into PlanState
    before persisting the trial record.

    When *scratchpad* is provided, slot and generation prompts become
    scratchpad-aware (see LambdaRlmSlotResolver / LambdaRlmBlockGenerator) —
    the same dict is passed to both collaborators so F-block write-backs
    are visible to subsequent G blocks within a single section render.

    When *sandbox* is provided, source references are resolved to anchored
    document slices via DocumentSandbox rather than the fallback source_resolver
    callable. When *tool_harness* is also provided (and enabled), the block
    generator can perform tool-use calls against the sandbox.
    """
    slot_resolver = LambdaRlmSlotResolver(
        client=client,
        model=model,
        source_resolver=source_resolver,
        scratchpad=scratchpad,
        voice_override=voice_override,
        domain_override=domain_override,
        sandbox=sandbox,
    )
    block_generator = LambdaRlmBlockGenerator(
        client=client,
        model=model,
        source_resolver=source_resolver,
        scratchpad=scratchpad,
        voice_override=voice_override,
        domain_override=domain_override,
        sandbox=sandbox,
        tool_harness=tool_harness,
    )

    content, trace = render_section(
        blocks=blocks,
        fragments=fragments,
        slot_resolver=slot_resolver,
        block_generator=block_generator,
    )

    stats = ComposeStats(
        calls=slot_resolver.calls + block_generator.calls,
        input_tokens=slot_resolver.input_tokens + block_generator.input_tokens,
        output_tokens=slot_resolver.output_tokens + block_generator.output_tokens,
    )
    return content, trace, stats


__all__ = [
    "ComposeStats",
    "LambdaRlmBlockGenerator",
    "LambdaRlmSlotResolver",
    "render_compose_section",
]
