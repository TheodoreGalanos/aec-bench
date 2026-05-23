# ABOUTME: Planning-phase dispatch test for agentic compose-mode.
# ABOUTME: Verifies one upfront LLM turn seeds compose_scratchpad before compose sections render.

import json

from aec_bench.adapters.lambda_rlm.config import (
    BackBriefConfig,
    ComposeConfig,
    LambdaRlmConfig,
    PlanningPhaseConfig,
    ScopeEvolutionConfig,
    TemplateMeta,
)
from aec_bench.adapters.lambda_rlm.executor import PlanExecutor
from aec_bench.adapters.lambda_rlm.state import (
    CompositionOp,
    ExecutionPlan,
    SectionPlan,
)
from aec_bench.adapters.rlm.client import ReplayRlmClient, RlmCompletionResponse
from aec_bench.adapters.rlm.template import ReportTemplate
from aec_bench.contracts.repl import DependencyTreeSchema, OutputField, TreeSection
from aec_bench.contracts.report_template import FillBlock


def _agentic_config(enabled: bool = True) -> LambdaRlmConfig:
    return LambdaRlmConfig(
        compose=ComposeConfig(mode="agentic"),
        planning_phase=PlanningPhaseConfig(
            enabled=enabled,
            extract_slots=("project_name", "site"),
            sources=("email_thread",),
        ),
    )


def _compose_template() -> ReportTemplate:
    schema = DependencyTreeSchema(
        sections=(
            TreeSection(
                id="intro",
                title="Intro",
                fields={"text": OutputField(name="text", dtype="str", description="")},
                depends_on=(),
                generation_mode="compose",
                blocks=(FillBlock(ref="intro.header", sources=("email_thread",)),),
            ),
        ),
    )
    return ReportTemplate(schema)


def _empty_plan(section_id: str) -> ExecutionPlan:
    return ExecutionPlan(
        section_order=[section_id],
        section_plans={
            section_id: SectionPlan(
                section_id=section_id,
                generation_mode="compose",
                sources=[],
                leaf_ops=[],
                reduce_ops=[],
                composition_op=CompositionOp.CONCATENATE,
                estimated_leaf_calls=0,
                estimated_reduce_calls=0,
            ),
        },
        skipped_sections=[],
    )


def test_planning_phase_runs_once_before_compose_and_seeds_scratchpad():
    """Agentic mode with planning enabled should issue exactly one
    planning-phase LLM call first, then render the compose section with
    the seeded scratchpad."""
    client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text=json.dumps(
                    {
                        "project_name": "North Plant Casein Air Heater",
                        "site": "North Plant",
                    }
                ),
                input_tokens=200,
                output_tokens=40,
            ),
        ]
    )
    boilerplate = {
        "intro": {
            "header": "Project {{project_name}} at {{site}}.",
        },
    }
    executor = PlanExecutor(
        client=client,
        model="m",
        template=_compose_template(),
        source_docs={"email_thread": "North Plant is a casein air heater project."},
        config=_agentic_config(),
        boilerplate_fragments=boilerplate,
    )
    state = executor.execute(_empty_plan("intro"))
    assert state.compose_scratchpad == {
        "project_name": "North Plant Casein Air Heater",
        "site": "North Plant",
    }
    assert state.sections["intro"] == "Project North Plant Casein Air Heater at North Plant."
    assert state.llm_calls == 1  # only the planning call


def test_planning_phase_disabled_skips_upfront_turn():
    """When planning_phase.enabled is False, the executor should not
    make an upfront call. The compose section falls back to per-block
    LLM resolution."""
    client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text=json.dumps(
                    {
                        "project_name": "North Plant",
                        "site": "North Plant",
                    }
                ),
                input_tokens=80,
                output_tokens=20,
            ),
        ]
    )
    boilerplate = {"intro": {"header": "{{project_name}} at {{site}}."}}
    cfg = _agentic_config(enabled=False)
    executor = PlanExecutor(
        client=client,
        model="m",
        template=_compose_template(),
        source_docs={"email_thread": "x"},
        config=cfg,
        boilerplate_fragments=boilerplate,
    )
    state = executor.execute(_empty_plan("intro"))
    # In agentic mode the slot resolver writes back resolved values even
    # without a planning phase — the scratchpad is not empty.
    # The key invariant is that no *extra* planning call was made.
    assert state.llm_calls == 1


def test_planning_phase_noop_in_orchestrated_mode():
    """Orchestrated mode should never trigger the planning phase even if
    planning_phase.enabled is True (orchestrated ignores it)."""
    client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text=json.dumps({"project_name": "North Plant", "site": "North Plant"}),
                input_tokens=80,
                output_tokens=20,
            ),
        ]
    )
    boilerplate = {"intro": {"header": "{{project_name}} at {{site}}."}}
    cfg = LambdaRlmConfig(
        compose=ComposeConfig(mode="orchestrated"),
        planning_phase=PlanningPhaseConfig(
            enabled=True,  # should be ignored in orchestrated mode
            extract_slots=("project_name", "site"),
            sources=("email_thread",),
        ),
    )
    executor = PlanExecutor(
        client=client,
        model="m",
        template=_compose_template(),
        source_docs={"email_thread": "x"},
        config=cfg,
        boilerplate_fragments=boilerplate,
    )
    state = executor.execute(_empty_plan("intro"))
    assert state.compose_scratchpad == {}
    # Only the FillBlock's LLM call; no planning call
    assert state.llm_calls == 1


def test_planning_phase_handles_malformed_json_response():
    """If the LLM returns non-JSON text for the planning phase, the
    scratchpad stays empty and the run continues gracefully (the F-block
    then makes its own LLM call to resolve slots)."""
    client = ReplayRlmClient(
        responses=[
            # Planning phase — malformed response
            RlmCompletionResponse(
                output_text="Sorry, I cannot determine the project details.",
                input_tokens=50,
                output_tokens=15,
            ),
            # F-block — proper JSON response (falls back to per-block resolution)
            RlmCompletionResponse(
                output_text=json.dumps({"project_name": "North Plant", "site": "North Plant"}),
                input_tokens=60,
                output_tokens=20,
            ),
        ]
    )
    boilerplate = {"intro": {"header": "{{project_name}} at {{site}}."}}
    executor = PlanExecutor(
        client=client,
        model="m",
        template=_compose_template(),
        source_docs={"email_thread": "x"},
        config=_agentic_config(),
        boilerplate_fragments=boilerplate,
    )
    state = executor.execute(_empty_plan("intro"))
    # Planning call happened (llm_calls counts both turns)
    assert state.llm_calls == 2
    # Scratchpad populated by F-block write-back, not the malformed planning response
    assert state.compose_scratchpad == {"project_name": "North Plant", "site": "North Plant"}
    assert state.sections["intro"] == "North Plant at North Plant."


def test_planning_phase_noop_when_extract_slots_empty():
    """When extract_slots is empty, the planning phase should early-return
    without any LLM call — even if mode=='agentic' and enabled==True."""
    client = ReplayRlmClient(
        responses=[
            # Only the F-block response — no planning call should occur
            RlmCompletionResponse(
                output_text=json.dumps({"project_name": "North Plant", "site": "North Plant"}),
                input_tokens=60,
                output_tokens=20,
            ),
        ]
    )
    boilerplate = {"intro": {"header": "{{project_name}} at {{site}}."}}
    cfg = LambdaRlmConfig(
        compose=ComposeConfig(mode="agentic"),
        planning_phase=PlanningPhaseConfig(
            enabled=True,  # enabled...
            extract_slots=(),  # ...but no slots to extract
            sources=("email_thread",),
        ),
    )
    executor = PlanExecutor(
        client=client,
        model="m",
        template=_compose_template(),
        source_docs={"email_thread": "x"},
        config=cfg,
        boilerplate_fragments=boilerplate,
    )
    state = executor.execute(_empty_plan("intro"))
    # Only the F-block call; planning phase early-returned with no LLM involvement
    assert state.llm_calls == 1


def test_back_brief_phase_populates_scratchpad_under_reserved_key():
    """Back-brief pass writes per-topic digest to compose_scratchpad['_back_brief']."""
    slot_response = RlmCompletionResponse(
        output_text=json.dumps({"client": "Example Dairy"}),
        input_tokens=50,
        output_tokens=10,
    )
    digest = {
        "services": "Patterns: A, B",
        "exclusions": "Carve-outs: 1, 2",
    }
    back_brief_response = RlmCompletionResponse(
        output_text=json.dumps(digest),
        input_tokens=200,
        output_tokens=40,
    )
    client = ReplayRlmClient(responses=[slot_response, back_brief_response])

    cfg = LambdaRlmConfig(
        compose=ComposeConfig(mode="agentic"),
        planning_phase=PlanningPhaseConfig(
            enabled=True,
            extract_slots=("client",),
            sources=("email_thread",),
            back_brief=BackBriefConfig(
                enabled=True,
                sources=("references/alpha", "references/beta"),
                topics=("services", "exclusions"),
            ),
        ),
    )

    boilerplate = {"intro": {"header": "{{client}} project."}}
    executor = PlanExecutor(
        client=client,
        model="m",
        template=_compose_template(),
        source_docs={
            "email_thread": "Project North Plant, client Example Dairy.",
            "references/alpha": "# Services\n- Pattern A\n# Exclusions\n- Carve-out 1",
            "references/beta": "# Services\n- Pattern B\n# Exclusions\n- Carve-out 2",
        },
        config=cfg,
        boilerplate_fragments=boilerplate,
    )
    state = executor.execute(_empty_plan("intro"))

    assert state.compose_scratchpad["client"] == "Example Dairy"
    assert state.compose_scratchpad["_back_brief"] == digest


def test_back_brief_phase_noop_when_disabled():
    """When back_brief.enabled = False, no back-brief LLM call is made."""
    slot_response = RlmCompletionResponse(
        output_text=json.dumps({"client": "Example Dairy"}),
        input_tokens=50,
        output_tokens=10,
    )
    client = ReplayRlmClient(responses=[slot_response])

    cfg = LambdaRlmConfig(
        compose=ComposeConfig(mode="agentic"),
        planning_phase=PlanningPhaseConfig(
            enabled=True,
            extract_slots=("client",),
            sources=("email_thread",),
            back_brief=BackBriefConfig(enabled=False),
        ),
    )

    boilerplate = {"intro": {"header": "{{client}} project."}}
    executor = PlanExecutor(
        client=client,
        model="m",
        template=_compose_template(),
        source_docs={"email_thread": "client Example Dairy"},
        config=cfg,
        boilerplate_fragments=boilerplate,
    )
    state = executor.execute(_empty_plan("intro"))

    # Exactly 1 call: slot extraction only, no back-brief call
    assert state.llm_calls == 1
    assert "_back_brief" not in state.compose_scratchpad


def test_back_brief_phase_noop_in_orchestrated_mode():
    """When compose.mode='orchestrated', back-brief is a no-op even if enabled."""
    # Orchestrated mode: planning is already a no-op, so only 1 call (FillBlock)
    client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text=json.dumps({"project_name": "North Plant", "site": "North Plant"}),
                input_tokens=80,
                output_tokens=20,
            ),
        ]
    )

    cfg = LambdaRlmConfig(
        compose=ComposeConfig(mode="orchestrated"),
        planning_phase=PlanningPhaseConfig(
            enabled=True,
            extract_slots=("client",),
            sources=("email_thread",),
            back_brief=BackBriefConfig(
                enabled=True,
                sources=("references/alpha",),
                topics=("services",),
            ),
        ),
    )

    boilerplate = {"intro": {"header": "{{project_name}} at {{site}}."}}
    executor = PlanExecutor(
        client=client,
        model="m",
        template=_compose_template(),
        source_docs={
            "email_thread": "x",
            "references/alpha": "# Services\n- Pattern A",
        },
        config=cfg,
        boilerplate_fragments=boilerplate,
    )
    state = executor.execute(_empty_plan("intro"))

    # Orchestrated: planning + back-brief are both no-ops; only the FillBlock call runs
    assert "_back_brief" not in state.compose_scratchpad
    assert state.llm_calls == 1


def test_back_brief_phase_handles_malformed_json():
    """When back-brief LLM returns unparseable JSON, _back_brief is absent or empty (no crash)."""
    slot_response = RlmCompletionResponse(
        output_text=json.dumps({"client": "Example Dairy"}),
        input_tokens=50,
        output_tokens=10,
    )
    bad_response = RlmCompletionResponse(
        output_text="not json at all",
        input_tokens=80,
        output_tokens=10,
    )
    client = ReplayRlmClient(responses=[slot_response, bad_response])

    cfg = LambdaRlmConfig(
        compose=ComposeConfig(mode="agentic"),
        planning_phase=PlanningPhaseConfig(
            enabled=True,
            extract_slots=("client",),
            sources=("email_thread",),
            back_brief=BackBriefConfig(
                enabled=True,
                sources=("references/alpha",),
                topics=("services", "exclusions"),
            ),
        ),
    )

    boilerplate = {"intro": {"header": "{{client}} project."}}
    executor = PlanExecutor(
        client=client,
        model="m",
        template=_compose_template(),
        source_docs={
            "email_thread": "client Example Dairy",
            "references/alpha": "# Services\n- Pattern A",
        },
        config=cfg,
        boilerplate_fragments=boilerplate,
    )
    state = executor.execute(_empty_plan("intro"))

    # Phase must complete without raising; _back_brief is absent or empty
    back_brief = state.compose_scratchpad.get("_back_brief")
    assert back_brief is None or back_brief == {}


def test_planning_prompt_uses_template_meta_guidance_when_provided():
    """TemplateMeta.planning_guidance is appended to the planning system prompt."""
    response = RlmCompletionResponse(
        output_text=json.dumps({"client": "Example Dairy"}),
        input_tokens=50,
        output_tokens=10,
    )
    captured: list[str] = []

    class CapturingClient:
        def generate(self, *, model, messages, system_prompt):
            captured.append(system_prompt)
            return response

    cfg = LambdaRlmConfig(
        compose=ComposeConfig(mode="agentic"),
        planning_phase=PlanningPhaseConfig(
            enabled=True,
            extract_slots=("client",),
            sources=("email_thread",),
        ),
    )
    boilerplate = {"intro": {"header": "{{client}} project."}}
    executor = PlanExecutor(
        client=CapturingClient(),
        model="m",
        template=_compose_template(),
        source_docs={"email_thread": "client Example Dairy"},
        config=cfg,
        boilerplate_fragments=boilerplate,
        template_meta=TemplateMeta(
            planning_guidance="client_pm is Example Dairy Engineering PM",
        ),
    )
    executor.execute(_empty_plan("intro"))
    assert any("client_pm is Example Dairy Engineering PM" in s for s in captured)


def test_scope_evolution_phase_populates_scratchpad_under_reserved_key():
    """Scope-evolution pass writes a plain-text summary to _scope_evolution."""
    slot_response = RlmCompletionResponse(
        output_text=json.dumps({"client": "Example Dairy"}),
        input_tokens=50,
        output_tokens=10,
    )
    scope_response = RlmCompletionResponse(
        output_text=(
            "INITIAL: Mark asked for business case + gating support. "
            "NARROWING: Mark reduced to options assessment only. "
            "FINAL: Options Assessment Report."
        ),
        input_tokens=120,
        output_tokens=30,
    )
    client = ReplayRlmClient(responses=[slot_response, scope_response])

    cfg = LambdaRlmConfig(
        compose=ComposeConfig(mode="agentic"),
        planning_phase=PlanningPhaseConfig(
            enabled=True,
            extract_slots=("client",),
            sources=("email_thread",),
            scope_evolution=ScopeEvolutionConfig(
                enabled=True,
                sources=("email_thread",),
            ),
        ),
    )

    boilerplate = {"intro": {"header": "{{client}} project."}}
    executor = PlanExecutor(
        client=client,
        model="m",
        template=_compose_template(),
        source_docs={"email_thread": "Mark: business case + gating. Mark: actually just options assessment."},
        config=cfg,
        boilerplate_fragments=boilerplate,
    )
    state = executor.execute(_empty_plan("intro"))

    digest = state.compose_scratchpad.get("_scope_evolution")
    assert isinstance(digest, str)
    assert "FINAL" in digest


def test_scope_evolution_phase_noop_when_disabled():
    """When scope_evolution.enabled = False, no scope-evolution LLM call is made."""
    slot_response = RlmCompletionResponse(
        output_text=json.dumps({"client": "Example Dairy"}),
        input_tokens=50,
        output_tokens=10,
    )
    client = ReplayRlmClient(responses=[slot_response])

    cfg = LambdaRlmConfig(
        compose=ComposeConfig(mode="agentic"),
        planning_phase=PlanningPhaseConfig(
            enabled=True,
            extract_slots=("client",),
            sources=("email_thread",),
            scope_evolution=ScopeEvolutionConfig(enabled=False),
        ),
    )
    boilerplate = {"intro": {"header": "{{client}} project."}}
    executor = PlanExecutor(
        client=client,
        model="m",
        template=_compose_template(),
        source_docs={"email_thread": "client Example Dairy"},
        config=cfg,
        boilerplate_fragments=boilerplate,
    )
    state = executor.execute(_empty_plan("intro"))

    assert state.llm_calls == 1
    assert "_scope_evolution" not in state.compose_scratchpad


def test_scope_evolution_phase_noop_in_orchestrated_mode():
    """Orchestrated mode skips scope-evolution even if enabled."""
    client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text=json.dumps({"project_name": "North Plant", "site": "North Plant"}),
                input_tokens=80,
                output_tokens=20,
            ),
        ]
    )
    cfg = LambdaRlmConfig(
        compose=ComposeConfig(mode="orchestrated"),
        planning_phase=PlanningPhaseConfig(
            enabled=True,
            extract_slots=("project_name", "site"),
            sources=("email_thread",),
            scope_evolution=ScopeEvolutionConfig(
                enabled=True,
                sources=("email_thread",),
            ),
        ),
    )
    boilerplate = {"intro": {"header": "{{project_name}} at {{site}}."}}
    executor = PlanExecutor(
        client=client,
        model="m",
        template=_compose_template(),
        source_docs={"email_thread": "Mark: project at North Plant."},
        config=cfg,
        boilerplate_fragments=boilerplate,
    )
    state = executor.execute(_empty_plan("intro"))

    assert "_scope_evolution" not in state.compose_scratchpad


def test_scope_evolution_skipped_when_no_source_content():
    """When declared sources resolve to empty, pass skips without LLM call."""
    slot_response = RlmCompletionResponse(
        output_text=json.dumps({"client": "Example Dairy"}),
        input_tokens=50,
        output_tokens=10,
    )
    client = ReplayRlmClient(responses=[slot_response])

    cfg = LambdaRlmConfig(
        compose=ComposeConfig(mode="agentic"),
        planning_phase=PlanningPhaseConfig(
            enabled=True,
            extract_slots=("client",),
            sources=("email_thread",),
            scope_evolution=ScopeEvolutionConfig(
                enabled=True,
                sources=("nonexistent_source",),
            ),
        ),
    )
    boilerplate = {"intro": {"header": "{{client}} project."}}
    executor = PlanExecutor(
        client=client,
        model="m",
        template=_compose_template(),
        source_docs={"email_thread": "client Example Dairy"},
        config=cfg,
        boilerplate_fragments=boilerplate,
    )
    state = executor.execute(_empty_plan("intro"))

    assert state.llm_calls == 1
    assert "_scope_evolution" not in state.compose_scratchpad
