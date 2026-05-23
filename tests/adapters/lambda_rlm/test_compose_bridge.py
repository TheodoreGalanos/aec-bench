# ABOUTME: Tests the lambda-rlm bridge to the compose-mode renderer.
# ABOUTME: Verifies SlotResolver + BlockGenerator implementations using the replay LLM client.


from aec_bench.adapters.lambda_rlm.compose_bridge import (
    LambdaRlmBlockGenerator,
    LambdaRlmSlotResolver,
    _format_sources,
    render_compose_section,
)
from aec_bench.adapters.rlm.client import ReplayRlmClient, RlmCompletionResponse
from aec_bench.contracts.report_template import (
    BlockGenerator,
    BoilerplateFragment,
    FillBlock,
    GeneratedBlock,
    SlotResolver,
    VerbatimBlock,
)


def _response(text: str, *, in_tok: int = 100, out_tok: int = 50) -> RlmCompletionResponse:
    return RlmCompletionResponse(
        output_text=text,
        input_tokens=in_tok,
        output_tokens=out_tok,
    )


def _stub_source_resolver(mapping):
    def resolve(label: str) -> str:
        return mapping.get(label, "")

    return resolve


# ─── LambdaRlmSlotResolver ─────────────────────────────────────────────────────


def test_slot_resolver_satisfies_protocol():
    resolver = LambdaRlmSlotResolver(
        client=ReplayRlmClient([]),
        model="m",
        source_resolver=_stub_source_resolver({}),
    )
    assert isinstance(resolver, SlotResolver)


def test_slot_resolver_parses_json_response_into_slot_map():
    client = ReplayRlmClient([_response('{"base_access_point": "Pass Office Gate 3"}')])
    resolver = LambdaRlmSlotResolver(
        client=client,
        model="m",
        source_resolver=_stub_source_resolver({"brief:site": "the Pass Office Gate 3 entry"}),
    )
    fragment = BoilerplateFragment(
        text="Access via the {{base_access_point}}.",
        slots=("base_access_point",),
    )
    result = resolver.resolve(fragment, ("brief:site",))
    assert result == {"base_access_point": "Pass Office Gate 3"}


def test_slot_resolver_returns_empty_dict_on_malformed_json():
    """Composer will then raise UnresolvedSlotError naming every slot."""
    client = ReplayRlmClient([_response("not json at all")])
    resolver = LambdaRlmSlotResolver(
        client=client,
        model="m",
        source_resolver=_stub_source_resolver({}),
    )
    fragment = BoilerplateFragment(text="{{x}}", slots=("x",))
    assert resolver.resolve(fragment, ()) == {}


def test_slot_resolver_extracts_json_object_embedded_in_prose():
    """Models often wrap JSON in explanation; resolver should still find the object."""
    client = ReplayRlmClient([_response('Here you go: {"a": "1", "b": "2"}\nhope this helps')])
    resolver = LambdaRlmSlotResolver(
        client=client,
        model="m",
        source_resolver=_stub_source_resolver({}),
    )
    fragment = BoilerplateFragment(text="{{a}} and {{b}}", slots=("a", "b"))
    assert resolver.resolve(fragment, ()) == {"a": "1", "b": "2"}


def test_slot_resolver_accumulates_token_usage():
    client = ReplayRlmClient(
        [
            _response('{"x": "v"}', in_tok=300, out_tok=10),
            _response('{"y": "v"}', in_tok=200, out_tok=20),
        ],
    )
    resolver = LambdaRlmSlotResolver(
        client=client,
        model="m",
        source_resolver=_stub_source_resolver({}),
    )
    resolver.resolve(BoilerplateFragment(text="{{x}}", slots=("x",)), ())
    resolver.resolve(BoilerplateFragment(text="{{y}}", slots=("y",)), ())
    assert resolver.input_tokens == 500
    assert resolver.output_tokens == 30
    assert resolver.calls == 2


def test_slot_resolver_passes_source_text_to_the_model():
    """The resolved source content must appear in the user prompt for the LLM."""
    captured: list[str] = []

    class CapturingClient:
        def generate(self, *, model, messages, system_prompt, temperature=None):
            captured.append(messages[-1].content)
            return _response('{"x": "v"}')

    resolver = LambdaRlmSlotResolver(
        client=CapturingClient(),
        model="m",
        source_resolver=_stub_source_resolver({"brief:site": "SITE-CONTENT-MARKER"}),
    )
    resolver.resolve(BoilerplateFragment(text="{{x}}", slots=("x",)), ("brief:site",))
    assert "SITE-CONTENT-MARKER" in captured[0]


# ─── LambdaRlmBlockGenerator ───────────────────────────────────────────────────


def test_block_generator_satisfies_protocol():
    generator = LambdaRlmBlockGenerator(
        client=ReplayRlmClient([]),
        model="m",
        source_resolver=_stub_source_resolver({}),
    )
    assert isinstance(generator, BlockGenerator)


def test_block_generator_returns_response_text():
    client = ReplayRlmClient([_response("Constraint: night work prohibited.")])
    generator = LambdaRlmBlockGenerator(
        client=client,
        model="m",
        source_resolver=_stub_source_resolver({}),
    )
    out = generator.generate("Write base-specific constraints.", ())
    assert out == "Constraint: night work prohibited."


def test_block_generator_includes_resolved_sources_in_prompt():
    captured: list[str] = []

    class CapturingClient:
        def generate(self, *, model, messages, system_prompt, temperature=None):
            captured.append(messages[-1].content)
            return _response("ok")

    generator = LambdaRlmBlockGenerator(
        client=CapturingClient(),
        model="m",
        source_resolver=_stub_source_resolver({"brief:notes": "NOTES-CONTENT"}),
    )
    generator.generate("Write a thing.", ("brief:notes",))
    prompt = captured[0]
    assert "Write a thing." in prompt
    assert "NOTES-CONTENT" in prompt


def test_block_generator_accumulates_token_usage():
    client = ReplayRlmClient(
        [
            _response("a", in_tok=10, out_tok=1),
            _response("b", in_tok=20, out_tok=2),
        ],
    )
    generator = LambdaRlmBlockGenerator(
        client=client,
        model="m",
        source_resolver=_stub_source_resolver({}),
    )
    generator.generate("p1", ())
    generator.generate("p2", ())
    assert generator.input_tokens == 30
    assert generator.output_tokens == 3
    assert generator.calls == 2


# ─── render_compose_section ────────────────────────────────────────────────────


def test_render_compose_section_assembles_hybrid_content_end_to_end():
    fragments = {
        "the_site": {
            "condition": {"preamble": "Site remains operational."},
            "access": {
                "access_route": "Access via the {{access_point}}.",
            },
        },
    }
    blocks = [
        VerbatimBlock(ref="the_site.condition.preamble"),
        FillBlock(ref="the_site.access.access_route", sources=("brief:site",)),
        GeneratedBlock(prompt="Note any constraints.", sources=("brief:notes",)),
    ]
    client = ReplayRlmClient(
        [
            _response('{"access_point": "Pass Office"}'),
            _response("Constraint: night work prohibited."),
        ],
    )

    content, trace, stats = render_compose_section(
        blocks=blocks,
        fragments=fragments,
        client=client,
        model="m",
        source_resolver=_stub_source_resolver(
            {"brief:site": "site info", "brief:notes": "notes content"},
        ),
    )

    assert content == ("Site remains operational.\n\nAccess via the Pass Office.\n\nConstraint: night work prohibited.")
    assert stats.calls == 2  # one slot-resolver call + one generator call
    assert stats.input_tokens > 0
    assert stats.output_tokens > 0
    assert len(trace) == 3
    assert trace[0].block_type == "verbatim"
    assert trace[1].block_type == "fill"
    assert trace[1].resolved_slots == {"access_point": "Pass Office"}
    assert trace[2].block_type == "generated"
    # Offset invariant: slicing the assembled content by trace offsets recovers
    # each block's exact text.
    for entry in trace:
        assert content[entry.start_offset : entry.end_offset] == entry.text


def test_render_compose_section_with_only_verbatim_blocks_makes_no_llm_calls():
    fragments = {"x": "static text", "y": "more static text"}
    blocks = [VerbatimBlock(ref="x"), VerbatimBlock(ref="y")]

    content, trace, stats = render_compose_section(
        blocks=blocks,
        fragments=fragments,
        client=ReplayRlmClient([]),
        model="m",
        source_resolver=_stub_source_resolver({}),
    )

    assert content == "static text\n\nmore static text"
    assert stats.calls == 0
    assert stats.input_tokens == 0
    assert stats.output_tokens == 0
    assert [t.block_type for t in trace] == ["verbatim", "verbatim"]


# ─── LambdaRlmSlotResolver scratchpad ─────────────────────────────────────────


def test_slot_resolver_reads_from_scratchpad_without_llm_call():
    """Slots already in scratchpad should resolve without any LLM call."""
    client = ReplayRlmClient([])  # would raise IndexError if touched
    scratchpad = {"project_name": "North Plant", "site": "North Plant Site"}
    resolver = LambdaRlmSlotResolver(
        client=client,
        model="m",
        source_resolver=_stub_source_resolver({}),
        scratchpad=scratchpad,
    )
    fragment = BoilerplateFragment(
        text="Project: {{project_name}} at {{site}}",
        slots=("project_name", "site"),
    )
    result = resolver.resolve(fragment, ("email_thread",))
    assert result == {"project_name": "North Plant", "site": "North Plant Site"}
    assert resolver.calls == 0


def test_slot_resolver_partial_scratchpad_hit_llm_fills_remainder():
    """If some slots are in scratchpad and some aren't, only the missing
    ones are requested from the LLM — the LLM prompt should not list the
    already-known slots."""
    client = ReplayRlmClient(
        [_response('{"supplier_pm": "Sarah Lee"}')],
    )
    scratchpad = {"project_name": "North Plant"}
    resolver = LambdaRlmSlotResolver(
        client=client,
        model="m",
        source_resolver=_stub_source_resolver({"email_thread": "PM is Sarah Lee"}),
        scratchpad=scratchpad,
    )
    fragment = BoilerplateFragment(
        text="{{project_name}} led by {{supplier_pm}}",
        slots=("project_name", "supplier_pm"),
    )
    result = resolver.resolve(fragment, ("email_thread",))
    assert result == {"project_name": "North Plant", "supplier_pm": "Sarah Lee"}
    assert resolver.calls == 1
    # Write-back in partial-hit path: the newly-resolved slot should be persisted.
    assert scratchpad == {"project_name": "North Plant", "supplier_pm": "Sarah Lee"}


def test_slot_resolver_writes_back_to_scratchpad():
    """Values resolved by the LLM should be written back so subsequent
    blocks can read them without a second LLM call."""
    client = ReplayRlmClient(
        [_response('{"fee_total": "NZ$120,000"}')],
    )
    scratchpad: dict[str, str] = {}
    resolver = LambdaRlmSlotResolver(
        client=client,
        model="m",
        source_resolver=_stub_source_resolver({"email_thread": "fee $120k"}),
        scratchpad=scratchpad,
    )
    fragment = BoilerplateFragment(
        text="Fee: {{fee_total}}",
        slots=("fee_total",),
    )
    resolver.resolve(fragment, ("email_thread",))
    assert scratchpad == {"fee_total": "NZ$120,000"}


def test_slot_resolver_without_scratchpad_is_back_compat():
    """When no scratchpad is provided, behaviour matches the orchestrated path."""
    client = ReplayRlmClient(
        [_response('{"x": "1"}')],
    )
    resolver = LambdaRlmSlotResolver(
        client=client,
        model="m",
        source_resolver=_stub_source_resolver({"email_thread": "x=1"}),
    )
    fragment = BoilerplateFragment(text="{{x}}", slots=("x",))
    result = resolver.resolve(fragment, ("email_thread",))
    assert result == {"x": "1"}
    assert resolver.calls == 1


# ─── LambdaRlmBlockGenerator scratchpad ───────────────────────────────────────


def test_block_generator_injects_scratchpad_as_known_facts():
    """When a scratchpad is present, the generator should include its
    contents as 'Known facts' context so the LLM can back-brief from
    slots already extracted in the planning phase."""
    captured_prompt: list[str] = []

    class _CapturingClient:
        def generate(self, *, model, messages, system_prompt):
            captured_prompt.append(messages[0].content)
            return RlmCompletionResponse(
                output_text="(a) Prepare options assessment.",
                input_tokens=100,
                output_tokens=20,
            )

    scratchpad = {
        "project_name": "North Plant Casein Air Heater",
        "site": "North Plant",
        "supplier_pm": "Sarah Lee",
    }
    gen = LambdaRlmBlockGenerator(
        client=_CapturingClient(),
        model="m",
        source_resolver=_stub_source_resolver({"email_thread": "details..."}),
        scratchpad=scratchpad,
    )
    out = gen.generate("Write the services list.", ("email_thread",))
    assert out == "(a) Prepare options assessment."

    prompt = captured_prompt[0]
    assert "Known facts" in prompt
    assert "project_name: North Plant Casein Air Heater" in prompt
    assert "site: North Plant" in prompt
    assert "supplier_pm: Sarah Lee" in prompt


def test_block_generator_without_scratchpad_is_back_compat():
    """With no scratchpad, the prompt should not contain a Known-facts block."""
    captured: list[str] = []

    class _CapturingClient:
        def generate(self, *, model, messages, system_prompt):
            captured.append(messages[0].content)
            return RlmCompletionResponse(output_text="text", input_tokens=1, output_tokens=1)

    gen = LambdaRlmBlockGenerator(
        client=_CapturingClient(),
        model="m",
        source_resolver=_stub_source_resolver({"email_thread": "details"}),
    )
    gen.generate("Prompt.", ("email_thread",))
    assert "Known facts" not in captured[0]


def test_block_generator_skips_known_facts_when_scratchpad_empty():
    captured: list[str] = []

    class _CapturingClient:
        def generate(self, *, model, messages, system_prompt):
            captured.append(messages[0].content)
            return RlmCompletionResponse(output_text="text", input_tokens=1, output_tokens=1)

    gen = LambdaRlmBlockGenerator(
        client=_CapturingClient(),
        model="m",
        source_resolver=_stub_source_resolver({"email_thread": "details"}),
        scratchpad={},
    )
    gen.generate("Prompt.", ("email_thread",))
    assert "Known facts" not in captured[0]


# ─── render_compose_section scratchpad ────────────────────────────────────────


def test_render_compose_section_accepts_and_propagates_scratchpad():
    """When a scratchpad is passed, both the slot resolver and block
    generator should receive it, and slot lookups that hit the scratchpad
    should avoid LLM calls."""
    client = ReplayRlmClient(
        [
            _response("Generated prose."),  # one LLM call for the G block only
        ]
    )
    fragments = {
        "intro": {
            "header": "The project is {{project_name}} at {{site}}.",
        },
    }
    blocks = (
        FillBlock(ref="intro.header", sources=("email_thread",)),
        GeneratedBlock(prompt="Write an overview.", sources=("email_thread",)),
    )
    scratchpad = {"project_name": "North Plant", "site": "North Plant Site"}
    text, trace, stats = render_compose_section(
        blocks=blocks,
        fragments=fragments,
        client=client,
        model="m",
        source_resolver=_stub_source_resolver({"email_thread": "details"}),
        scratchpad=scratchpad,
    )
    assert "The project is North Plant at North Plant Site." in text
    assert "Generated prose." in text
    # Attribution proof: only one _response is queued, so if the F block
    # had made an LLM call the G block's generate() would raise IndexError
    # on an empty ReplayRlmClient. The test only reaches this point if the
    # F block was resolved from scratchpad (0 calls) and the G block made
    # exactly 1 call.
    assert stats.calls == 1
    # Safety check: the rendered text must contain both scratchpad values
    # (proving F-block resolution succeeded with no LLM involvement).
    assert "North Plant" in text and "North Plant Site" in text


# ─── _format_sources with back_brief ──────────────────────────────────────


def test_format_sources_returns_back_brief_for_glob_label():
    back_brief = {"services": "Pattern A; Pattern B"}

    def resolver(_label):
        return ""

    out = _format_sources(
        ["email_thread", "references/*:services"],
        resolver,
        back_brief=back_brief,
    )
    assert "Pattern A; Pattern B" in out
    assert "references/*:services" in out


def test_format_sources_falls_back_when_back_brief_missing_topic():
    back_brief = {"services": "Pattern A"}

    def resolver(label):
        return "EMAIL" if label == "email_thread" else ""

    out = _format_sources(
        ["email_thread", "references/*:nonexistent"],
        resolver,
        back_brief=back_brief,
    )
    assert "EMAIL" in out
    assert "references/*:nonexistent" not in out  # dropped (resolver returned empty)


def test_format_sources_back_brief_none_preserves_current_behaviour():
    def resolver(label):
        return "EMAIL" if label == "email_thread" else ""

    out = _format_sources(
        ["email_thread", "references/*:services"],
        resolver,
        back_brief=None,
    )
    assert "EMAIL" in out
    assert "references/*:services" not in out  # silent miss, unchanged


# ─── Task 4: SlotResolver and BlockGenerator back_brief threading ───────────


def test_block_generator_passes_back_brief_from_scratchpad():
    """When the scratchpad contains _back_brief, generated blocks see the digest in the prompt."""
    scratchpad = {
        "client": "Example Dairy",
        "_back_brief": {"services": "Pattern A; Pattern B"},
    }
    captured_prompts: list[str] = []

    class FakeClient:
        def generate(self, *, model, messages, system_prompt):
            captured_prompts.append(messages[0].content)
            return RlmCompletionResponse(output_text="OUT", input_tokens=10, output_tokens=5)

    gen = LambdaRlmBlockGenerator(
        client=FakeClient(),
        model="x",
        source_resolver=lambda label: "EMAIL" if label == "email_thread" else "",
        scratchpad=scratchpad,
    )
    gen.generate("Write something.", ["email_thread", "references/*:services"])

    # The digest appears in the source block, and the string slot appears in
    # the known-facts block. The reserved _back_brief key does NOT leak as a
    # Python dict repr.
    assert "Pattern A; Pattern B" in captured_prompts[0]
    assert "EMAIL" in captured_prompts[0]
    assert "client: Example Dairy" in captured_prompts[0]
    assert "_back_brief" not in captured_prompts[0]
    assert "{'services'" not in captured_prompts[0]  # no dict repr leak


def test_slot_resolver_passes_back_brief_from_scratchpad():
    """When fragment has slots and a references/*:topic source, digest is in prompt."""
    scratchpad = {
        "_back_brief": {"key_personnel": "ExampleCo TD; Example Dairy Engineering PM"},
    }
    captured_prompts: list[str] = []

    class FakeClient:
        def generate(self, *, model, messages, system_prompt):
            captured_prompts.append(messages[0].content)
            return RlmCompletionResponse(output_text='{"role": "TD"}', input_tokens=10, output_tokens=5)

    resolver = LambdaRlmSlotResolver(
        client=FakeClient(),
        model="x",
        source_resolver=lambda label: "" if label.startswith("references/*") else "EMAIL",
        scratchpad=scratchpad,
    )
    fragment = BoilerplateFragment(text="The {{role}}.", slots=("role",))
    resolver.resolve(fragment, ["email_thread", "references/*:key_personnel"])
    assert "ExampleCo TD; Example Dairy Engineering PM" in captured_prompts[0]


def test_block_generator_filters_back_brief_from_known_facts():
    """_format_known_facts must not emit '_back_brief: {...}' as a fact."""
    scratchpad = {
        "client": "Example Dairy",
        "supplier_pm": "Glen Bodger",
        "_back_brief": {"services": "pat"},
    }
    captured_prompts: list[str] = []

    class FakeClient:
        def generate(self, *, model, messages, system_prompt):
            captured_prompts.append(messages[0].content)
            return RlmCompletionResponse(output_text="OUT", input_tokens=1, output_tokens=1)

    gen = LambdaRlmBlockGenerator(
        client=FakeClient(),
        model="x",
        source_resolver=lambda _label: "S",
        scratchpad=scratchpad,
    )
    gen.generate("Write.", ["email_thread"])

    prompt = captured_prompts[0]
    assert "client: Example Dairy" in prompt
    assert "supplier_pm: Glen Bodger" in prompt
    assert "_back_brief" not in prompt
    assert "{'services'" not in prompt


# ─── voice_override / domain_override threading ────────────────────────────────


def test_block_generator_uses_voice_override_when_provided():
    captured: list[str] = []

    class FakeClient:
        def generate(self, *, model, messages, system_prompt):
            captured.append(system_prompt)
            return RlmCompletionResponse(output_text="OUT", input_tokens=1, output_tokens=1)

    gen = LambdaRlmBlockGenerator(
        client=FakeClient(),
        model="x",
        source_resolver=lambda _label: "S",
        voice_override="plain Australian engineering register",
    )
    gen.generate("Write something.", ["email_thread"])
    assert "plain Australian engineering register" in captured[0]
    assert "Formal contract voice" not in captured[0]


def test_block_generator_default_voice_when_no_override():
    captured: list[str] = []

    class FakeClient:
        def generate(self, *, model, messages, system_prompt):
            captured.append(system_prompt)
            return RlmCompletionResponse(output_text="OUT", input_tokens=1, output_tokens=1)

    gen = LambdaRlmBlockGenerator(client=FakeClient(), model="x", source_resolver=lambda _label: "S")
    gen.generate("Write something.", ["email_thread"])
    assert "Formal contract voice" in captured[0]


def test_slot_resolver_uses_domain_override_when_provided():
    captured: list[str] = []

    class FakeClient:
        def generate(self, *, model, messages, system_prompt):
            captured.append(system_prompt)
            return RlmCompletionResponse(output_text='{"x": "y"}', input_tokens=1, output_tokens=1)

    resolver = LambdaRlmSlotResolver(
        client=FakeClient(),
        model="x",
        source_resolver=lambda _label: "S",
        domain_override="Example Dairy dairy engagement",
    )
    fragment = BoilerplateFragment(text="The {{x}}.", slots=("x",))
    resolver.resolve(fragment, ["email_thread"])
    assert "Example Dairy dairy engagement" in captured[0]


def test_block_generator_surfaces_scope_evolution_in_prompt():
    """When scratchpad has _scope_evolution, it appears in the prompt under
    an Authoritative-scope-summary heading — not as a flat known fact."""
    captured: list[str] = []

    class CapturingClient:
        def generate(self, *, model, messages, system_prompt):
            captured.append(messages[-1].content)
            return RlmCompletionResponse(output_text="OK", input_tokens=1, output_tokens=1)

    scratchpad: dict[str, str | dict[str, str]] = {
        "client": "Example Dairy",
        "_scope_evolution": (
            "INITIAL: business case + gating. "
            "NARROWING: reduced to options assessment. "
            "FINAL: Options Assessment Report only."
        ),
    }
    gen = LambdaRlmBlockGenerator(
        client=CapturingClient(),
        model="m",
        source_resolver=lambda _label: "SOURCE",
        scratchpad=scratchpad,
    )
    gen.generate("Write services.", ("email_thread",))

    prompt = captured[0]
    # Scope-evolution surfaces under its own heading, not as a flat fact
    assert "Scope summary (from planning phase" in prompt
    assert "FINAL: Options Assessment Report only" in prompt
    # Slot facts still appear, without the scope-evolution entry leaking in
    assert "- client: Example Dairy" in prompt
    assert "- _scope_evolution:" not in prompt


def test_block_generator_skips_scope_evolution_when_absent():
    """When _scope_evolution is not in scratchpad, the heading is not added."""
    captured: list[str] = []

    class CapturingClient:
        def generate(self, *, model, messages, system_prompt):
            captured.append(messages[-1].content)
            return RlmCompletionResponse(output_text="OK", input_tokens=1, output_tokens=1)

    gen = LambdaRlmBlockGenerator(
        client=CapturingClient(),
        model="m",
        source_resolver=lambda _label: "SOURCE",
        scratchpad={"client": "Example Dairy"},
    )
    gen.generate("Write.", ("email_thread",))
    assert "Scope summary (from planning phase" not in captured[0]


# ─── Task 10: LambdaRlmSlotResolver sandbox path ──────────────────────────────


def test_slot_resolver_fetches_slice_via_sandbox(monkeypatch):
    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox
    from aec_bench.contracts.report_template import BoilerplateFragment

    sandbox = DocumentSandbox.from_documents(
        {"brief.md": "# T\n\n## Scope\nExampleCo will deliver options."},
        extractor_overrides={},
    )
    fragment = BoilerplateFragment(text="The scope is {{summary}}.", slots=("summary",))

    captured: dict[str, str] = {}

    class _FakeResp:
        output_text = '{"summary": "options assessment"}'
        input_tokens = 1
        output_tokens = 1

    class _FakeClient:
        def generate(self, *, model, messages, system_prompt):
            captured["prompt"] = messages[0].content
            captured["system"] = system_prompt
            return _FakeResp()

    resolver = LambdaRlmSlotResolver(
        client=_FakeClient(),
        model="m",
        source_resolver=lambda label: "",
        sandbox=sandbox,
    )
    resolved = resolver.resolve(fragment, sources=("brief.md#scope",))
    assert resolved == {"summary": "options assessment"}
    assert resolver.last_slot_provenance == {"summary": ("brief.md#scope",)}
    assert "Source: brief.md (anchor: #scope)" in captured["prompt"]
    assert "ExampleCo will deliver options." in captured["prompt"]


def test_slot_resolver_bare_label_resolves_whole_doc():
    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox
    from aec_bench.contracts.report_template import BoilerplateFragment

    sandbox = DocumentSandbox.from_documents(
        {"exemplar.md": "Whole exemplar text"},
        extractor_overrides={},
    )
    fragment = BoilerplateFragment(text="{{x}}", slots=("x",))

    class _Resp:
        output_text = '{"x": "y"}'
        input_tokens = 1
        output_tokens = 1

    class _Client:
        def generate(self, **kw):
            return _Resp()

    resolver = LambdaRlmSlotResolver(
        client=_Client(),
        model="m",
        source_resolver=lambda label: "",
        sandbox=sandbox,
    )
    resolver.resolve(fragment, sources=("exemplar.md",))
    assert resolver.last_slot_provenance == {"x": ("exemplar.md",)}


def test_slot_resolver_without_sandbox_preserves_today_behaviour():
    """Back-compat: when sandbox=None, source_resolver path runs unchanged."""
    fragment = BoilerplateFragment(text="{{x}}", slots=("x",))

    class _Resp:
        output_text = '{"x": "y"}'
        input_tokens = 1
        output_tokens = 1

    captured: dict[str, str] = {}

    class _Client:
        def generate(self, *, model, messages, system_prompt):
            captured["prompt"] = messages[0].content
            return _Resp()

    resolver = LambdaRlmSlotResolver(
        client=_Client(),
        model="m",
        source_resolver=lambda label: f"WHOLE_DOC_{label}",
        sandbox=None,
    )
    resolver.resolve(fragment, sources=("brief.md",))
    # Back-compat: today's _format_sources path emits the source via source_resolver
    assert "WHOLE_DOC_brief.md" in captured["prompt"]
    # last_slot_provenance still records the declared source even without sandbox
    assert resolver.last_slot_provenance == {"x": ("brief.md",)}


# ─── Task 11: LambdaRlmBlockGenerator sandbox path ────────────────────────────


def test_block_generator_fetches_slices_via_sandbox():
    from aec_bench.adapters.lambda_rlm.compose_bridge import LambdaRlmBlockGenerator
    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

    sandbox = DocumentSandbox.from_documents(
        {"brief.md": "# T\n\n## Scope\nExampleCo will deliver options."},
        extractor_overrides={},
    )

    captured: dict[str, str] = {}

    class _Resp:
        output_text = "generated body"
        input_tokens = 1
        output_tokens = 1

    class _Client:
        def generate(self, *, model, messages, system_prompt):
            captured["prompt"] = messages[0].content
            return _Resp()

    gen = LambdaRlmBlockGenerator(
        client=_Client(),
        model="m",
        source_resolver=lambda label: "",
        sandbox=sandbox,
    )
    out = gen.generate("Write the scope.", ("brief.md#scope",))
    assert out == "generated body"
    assert gen.last_provenance == ("brief.md#scope",)
    assert gen.last_declared_provenance == ("brief.md#scope",)
    assert gen.last_fetched_provenance == ()
    assert "Source: brief.md (anchor: #scope)" in gen.last_prompt
    assert "ExampleCo will deliver options." in gen.last_prompt


def test_block_generator_without_sandbox_preserves_today_behaviour():
    """Back-compat: sandbox=None → _format_sources path unchanged."""
    from aec_bench.adapters.lambda_rlm.compose_bridge import LambdaRlmBlockGenerator

    captured: dict[str, str] = {}

    class _Resp:
        output_text = "generated body"
        input_tokens = 1
        output_tokens = 1

    class _Client:
        def generate(self, *, model, messages, system_prompt):
            captured["prompt"] = messages[0].content
            return _Resp()

    gen = LambdaRlmBlockGenerator(
        client=_Client(),
        model="m",
        source_resolver=lambda label: f"WHOLE_DOC_{label}",
        sandbox=None,
    )
    gen.generate("Write.", ("brief.md",))
    # Back-compat: prompt embeds whole-doc text from source_resolver
    assert "WHOLE_DOC_brief.md" in captured["prompt"]
    # Provenance still tracked even without sandbox
    assert gen.last_declared_provenance == ("brief.md",)
    assert gen.last_provenance == ("brief.md",)


# ─── Task 14: tool-use harness wiring ─────────────────────────────────────────


def test_block_generator_without_tool_harness_works_as_before():
    """Sanity: omitting tool_harness leaves last_fetched_provenance empty."""
    from aec_bench.adapters.lambda_rlm.compose_bridge import LambdaRlmBlockGenerator
    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

    sandbox = DocumentSandbox.from_documents(
        {"brief.md": "# T\n\n## Scope\nbody"},
        extractor_overrides={},
    )

    class _Resp:
        output_text = "ok"
        input_tokens = 1
        output_tokens = 1

    class _Client:
        def generate(self, **kw):
            return _Resp()

    gen = LambdaRlmBlockGenerator(
        client=_Client(),
        model="m",
        source_resolver=lambda label: "",
        sandbox=sandbox,
    )
    gen.generate("Write.", ("brief.md#scope",))
    assert gen.last_fetched_provenance == ()
    assert gen.last_provenance == ("brief.md#scope",)


def test_block_generator_captures_fetched_provenance_from_harness():
    """When the harness is enabled and has recorded fetches, fetched_provenance reflects it."""
    from aec_bench.adapters.lambda_rlm.compose_bridge import LambdaRlmBlockGenerator
    from aec_bench.adapters.lambda_rlm.config import ToolUseCapsConfig
    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox
    from aec_bench.adapters.lambda_rlm.sandbox_tools import SandboxToolHarness

    sandbox = DocumentSandbox.from_documents(
        {"brief.md": "# T\n\n## Scope\nbody\n\n## Schedule\ndates"},
        extractor_overrides={},
    )
    harness = SandboxToolHarness(
        sandbox=sandbox,
        enabled=True,
        caps=ToolUseCapsConfig(max_fetches_per_block=5, max_total_fetches=30),
    )

    # Simulate the model having fetched a slice via tool-use during generation.
    # In v1 this can't happen automatically (no loop driver) — but if a future
    # caller calls harness.invoke() during generate(), the provenance must surface.
    # We simulate by invoking the harness BEFORE generate() returns to verify
    # the capture wiring.

    class _Resp:
        output_text = "ok"
        input_tokens = 1
        output_tokens = 1

    invoked = {"called": False}

    class _Client:
        def generate(self, **kw):
            # Simulate the model calling get_slice during the LLM call.
            if not invoked["called"]:
                harness.invoke("get_slice", {"label": "brief.md", "anchor": "#schedule"})
                invoked["called"] = True
            return _Resp()

    gen = LambdaRlmBlockGenerator(
        client=_Client(),
        model="m",
        source_resolver=lambda label: "",
        sandbox=sandbox,
        tool_harness=harness,
    )
    gen.generate("Write.", ("brief.md#scope",))
    assert gen.last_declared_provenance == ("brief.md#scope",)
    assert gen.last_fetched_provenance == ("brief.md#schedule",)
    assert gen.last_provenance == ("brief.md#scope", "brief.md#schedule")


def test_block_generator_resets_block_counter_per_call():
    """Each generate() call starts with a fresh per-block fetch counter."""
    from aec_bench.adapters.lambda_rlm.compose_bridge import LambdaRlmBlockGenerator
    from aec_bench.adapters.lambda_rlm.config import ToolUseCapsConfig
    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox
    from aec_bench.adapters.lambda_rlm.sandbox_tools import SandboxToolHarness

    sandbox = DocumentSandbox.from_documents(
        {"brief.md": "# T\n\n## Scope\nbody"},
        extractor_overrides={},
    )
    # per-block cap of 2 means each block can fetch at most 2 slices
    harness = SandboxToolHarness(
        sandbox=sandbox,
        enabled=True,
        caps=ToolUseCapsConfig(max_fetches_per_block=2, max_total_fetches=30),
    )

    class _Resp:
        output_text = "ok"
        input_tokens = 1
        output_tokens = 1

    class _Client:
        def generate(self, **kw):
            # Each block uses its 2-fetch quota
            harness.invoke("get_slice", {"label": "brief.md", "anchor": "#scope"})
            harness.invoke("get_slice", {"label": "brief.md", "anchor": ":p1"})
            return _Resp()

    gen = LambdaRlmBlockGenerator(
        client=_Client(),
        model="m",
        source_resolver=lambda label: "",
        sandbox=sandbox,
        tool_harness=harness,
    )
    # Two consecutive blocks — both must succeed because the per-block counter
    # resets each generate() call.
    gen.generate("Block 1.", ("brief.md#scope",))
    gen.generate("Block 2.", ("brief.md#scope",))
    # Total fetches = 4 across 2 blocks; per-block cap not hit because reset
    assert len(harness.fetched_anchors()) == 4


# ─── North Plant regression: back-brief refs in the sandbox path ──────────────────


def test_format_sandbox_sources_resolves_back_brief_topic_ref():
    """`references/*:<topic>` refs route to back-brief, not parse_anchor_ref."""
    from aec_bench.adapters.lambda_rlm.compose_bridge import _format_sandbox_sources
    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

    sandbox = DocumentSandbox.from_documents(
        {"brief.md": "## Scope\nbody"},
        extractor_overrides={},
    )
    back_brief = {"services": "Pattern A; Pattern B"}
    out = _format_sandbox_sources(
        ["brief.md#scope", "references/*:services"],
        sandbox,
        back_brief=back_brief,
    )
    assert "Pattern A; Pattern B" in out
    assert "references/*:services" in out
    # The anchored ref also resolves
    assert "Source: brief.md (anchor: #scope)" in out


def test_format_sandbox_sources_skips_unparseable_refs_silently():
    """Bespoke template syntax that isn't an anchor or back-brief ref → skipped, no crash."""
    from aec_bench.adapters.lambda_rlm.compose_bridge import _format_sandbox_sources
    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

    sandbox = DocumentSandbox.from_documents(
        {"brief.md": "body"},
        extractor_overrides={},
    )
    # `references/*:services` with no back_brief, plus a real anchored ref.
    out = _format_sandbox_sources(
        ["brief.md", "references/*:services"],
        sandbox,
        back_brief=None,
    )
    # Real ref still renders; bespoke ref is silently skipped.
    assert "Source: brief.md" in out
    assert "Pattern" not in out


def test_block_generator_back_brief_ref_works_with_sandbox_enabled():
    """End-to-end: a generated block citing references/*:topic resolves via back_brief
    when sandbox is enabled. North Plant regression — surfaced 2026-04-25."""
    from aec_bench.adapters.lambda_rlm.compose_bridge import LambdaRlmBlockGenerator
    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

    sandbox = DocumentSandbox.from_documents(
        {"email_thread.md": "## Message 1 — From X\nbody"},
        extractor_overrides={},
    )
    scratchpad: dict = {
        "_back_brief": {"services": "Standard ExampleCo services pattern"},
    }

    captured_prompt: dict[str, str] = {}

    class _Resp:
        output_text = "ok"
        input_tokens = 1
        output_tokens = 1

    class _Client:
        def generate(self, *, model, messages, system_prompt):
            captured_prompt["body"] = messages[0].content
            return _Resp()

    gen = LambdaRlmBlockGenerator(
        client=_Client(),
        model="m",
        source_resolver=lambda label: "",
        scratchpad=scratchpad,
        sandbox=sandbox,
    )
    gen.generate("Write services.", ("email_thread.md", "references/*:services"))
    # Back-brief content reaches the prompt even though sandbox is enabled.
    assert "Standard ExampleCo services pattern" in captured_prompt["body"]
