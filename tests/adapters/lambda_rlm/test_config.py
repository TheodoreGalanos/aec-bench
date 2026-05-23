# ABOUTME: Tests for lambda-rlm configuration parsing.
# ABOUTME: Validates TOML config is correctly parsed into LambdaRlmConfig dataclass.

import pytest

from aec_bench.adapters.lambda_rlm.config import (
    StructureEnforcementConfig,
    parse_lambda_rlm_config,
    parse_template_meta,
)


def test_parse_minimal_config():
    toml_str = """
[template]
tier = "dependency_tree"
definition = "report_template.toml"
"""
    config = parse_lambda_rlm_config(toml_str)
    assert config.template_tier == "dependency_tree"
    assert config.template_definition == "report_template.toml"
    assert config.planner.context_window_chars == 100_000
    assert config.planner.accuracy_target == 0.80
    assert config.review.enabled is True
    assert config.token_budget == 500_000


def test_parse_full_config():
    toml_str = """
[template]
tier = "dependency_tree"
definition = "report_template.toml"

[planner]
context_window_chars = 200_000
accuracy_target = 0.90
leaf_accuracy = 0.97
compose_accuracy = 0.92
max_branching_factor = 10

[review]
enabled = true
max_retries_per_source = 2
max_supplements_per_section = 2

[guardrails]
token_budget = 750_000
"""
    config = parse_lambda_rlm_config(toml_str)
    assert config.planner.context_window_chars == 200_000
    assert config.planner.accuracy_target == 0.90
    assert config.planner.leaf_accuracy == 0.97
    assert config.planner.compose_accuracy == 0.92
    assert config.planner.max_branching_factor == 10
    assert config.review.max_retries_per_source == 2
    assert config.review.max_supplements_per_section == 2
    assert config.token_budget == 750_000


def test_parse_review_disabled():
    toml_str = """
[template]
tier = "dependency_tree"
definition = "report_template.toml"

[review]
enabled = false
"""
    config = parse_lambda_rlm_config(toml_str)
    assert config.review.enabled is False


def test_max_parallel_workers_defaults_to_four():
    toml_str = """
[template]
tier = "dependency_tree"
"""
    config = parse_lambda_rlm_config(toml_str)
    assert config.max_parallel_workers == 4


def test_parse_max_parallel_workers():
    toml_str = """
[template]
tier = "dependency_tree"

[execution]
max_parallel_workers = 8
"""
    config = parse_lambda_rlm_config(toml_str)
    assert config.max_parallel_workers == 8


class TestAdvisorConfigParsing:
    def test_no_advisor_block(self) -> None:
        toml = '[template]\ntier = "dependency_tree"\n'
        config = parse_lambda_rlm_config(toml)
        assert config.advisor is None

    def test_advisor_block_parsed(self) -> None:
        toml = """
[template]
tier = "dependency_tree"

[advisor]
model = "claude-opus-4-6"
max_uses = 3
"""
        config = parse_lambda_rlm_config(toml)
        assert config.advisor is not None
        assert config.advisor.model == "claude-opus-4-6"
        assert config.advisor.max_uses == 3

    def test_advisor_defaults(self) -> None:
        toml = """
[template]
tier = "dependency_tree"

[advisor]
model = "claude-sonnet-4-20250514"
"""
        config = parse_lambda_rlm_config(toml)
        assert config.advisor is not None
        assert config.advisor.max_uses == 5
        assert config.advisor.max_response_tokens == 500
        assert config.advisor.context_window == 10
        assert config.advisor.enabled is True

    def test_advisor_disabled(self) -> None:
        toml = """
[template]
tier = "dependency_tree"

[advisor]
model = "claude-opus-4-6"
enabled = false
"""
        config = parse_lambda_rlm_config(toml)
        assert config.advisor is not None
        assert config.advisor.enabled is False


class TestFillSectionConfig:
    """Parser tests for the [fill_section] and [fill_section.synthesis] blocks."""

    def test_default_when_omitted(self) -> None:
        toml = """
[template]
tier = "dependency_tree"
"""
        config = parse_lambda_rlm_config(toml)
        assert config.fill_section.k_candidates == 1
        assert config.fill_section.tournament_mode == "pointwise_only"
        assert config.fill_section.apply_to_sections == ()
        # Default SynthesisConfig is nested; verify its defaults flow through.
        assert config.fill_section.synthesis.synthesiser_model == "anthropic:claude-sonnet-4-6"

    def test_synthesis_mode_with_overrides(self) -> None:
        toml = """
[template]
tier = "dependency_tree"

[fill_section]
k_candidates = 4
tournament_mode = "synthesis"
apply_to_sections = ["scope_of_works", "contractor_obligations"]
temperature = 0.9

[fill_section.synthesis]
synthesiser_model = "anthropic:claude-opus-4-7"
max_input_tokens = 120000
max_output_tokens = 20000
domain_hint = "public-works scope of works"
verify_sources = false
"""
        config = parse_lambda_rlm_config(toml)
        assert config.fill_section.k_candidates == 4
        assert config.fill_section.tournament_mode == "synthesis"
        assert config.fill_section.apply_to_sections == (
            "scope_of_works",
            "contractor_obligations",
        )
        assert config.fill_section.temperature == 0.9
        s = config.fill_section.synthesis
        assert s.synthesiser_model == "anthropic:claude-opus-4-7"
        assert s.max_input_tokens == 120_000
        assert s.max_output_tokens == 20_000
        assert s.domain_hint == "public-works scope of works"
        assert s.verify_sources is False
        # Unset fields keep defaults
        assert s.fallback_on_failure is True

    def test_unknown_tournament_mode_raises(self) -> None:
        toml = """
[template]
tier = "dependency_tree"

[fill_section]
tournament_mode = "round_robin"
"""
        with pytest.raises(ValueError, match="unsupported tournament_mode"):
            parse_lambda_rlm_config(toml)


class TestFillSectionConfigRoundTrip:
    """Guard reproducibility: the config must round-trip through dict form cleanly.

    The adapter writes configuration into TrialRecord.configuration (a
    ``dict[str, Any]`` slot). If a new field is added to FillSectionConfig or
    SynthesisConfig but the snapshot path doesn't capture it, a run becomes
    unreproducible. This test catches that class of regression.
    """

    def test_fill_section_config_round_trips(self) -> None:
        from dataclasses import asdict

        from aec_bench.adapters.lambda_rlm.config import FillSectionConfig
        from aec_bench.contracts.synthesis import SynthesisConfig

        original = FillSectionConfig(
            k_candidates=4,
            temperature=0.8,
            tournament_mode="synthesis",
            apply_to_sections=("scope_of_works",),
            synthesis=SynthesisConfig(
                synthesiser_model="anthropic:claude-opus-4-7",
                max_input_tokens=120_000,
                domain_hint="legal contract",
            ),
        )
        as_dict = asdict(original)
        # Reconstruct — nested SynthesisConfig becomes a nested dict.
        rebuilt = FillSectionConfig(
            k_candidates=as_dict["k_candidates"],
            temperature=as_dict["temperature"],
            tournament_mode=as_dict["tournament_mode"],
            apply_to_sections=tuple(as_dict["apply_to_sections"]),
            synthesis=SynthesisConfig(**as_dict["synthesis"]),
        )
        assert rebuilt == original

    def test_default_fill_section_config_round_trips(self) -> None:
        from dataclasses import asdict

        from aec_bench.adapters.lambda_rlm.config import FillSectionConfig
        from aec_bench.contracts.synthesis import SynthesisConfig

        original = FillSectionConfig()
        as_dict = asdict(original)
        rebuilt = FillSectionConfig(
            k_candidates=as_dict["k_candidates"],
            temperature=as_dict["temperature"],
            tournament_mode=as_dict["tournament_mode"],
            apply_to_sections=tuple(as_dict["apply_to_sections"]),
            synthesis=SynthesisConfig(**as_dict["synthesis"]),
        )
        assert rebuilt == original


# ── Phase 1: ExtractConfig, UncertaintyConfig, ReviewConfig extensions ──


class TestExtractConfig:
    """Tests for the [extract] config block (Idea 3b)."""

    def test_defaults_when_omitted(self) -> None:
        toml = '[template]\ntier = "dependency_tree"\n'
        config = parse_lambda_rlm_config(toml)
        assert config.extract.k_candidates == 1
        assert config.extract.temperature == 0.7
        assert config.extract.keep_candidates_artifact is False

    def test_explicit_values(self) -> None:
        toml = """
[template]
tier = "dependency_tree"

[extract]
k_candidates = 5
temperature = 0.9
keep_candidates_artifact = true
"""
        config = parse_lambda_rlm_config(toml)
        assert config.extract.k_candidates == 5
        assert config.extract.temperature == 0.9
        assert config.extract.keep_candidates_artifact is True


class TestUncertaintyConfig:
    """Tests for the [uncertainty] config block (Idea 3c)."""

    def test_defaults_when_omitted(self) -> None:
        toml = '[template]\ntier = "dependency_tree"\n'
        config = parse_lambda_rlm_config(toml)
        assert config.uncertainty.lambda_ == 0.5
        assert config.uncertainty.min_confidence_eps == 0.01
        assert config.uncertainty.min_samples == 3
        assert config.uncertainty.review_joint_threshold == 1.0
        # No enabled field — scoring derived from trigger.
        assert not hasattr(config.uncertainty, "enabled")

    def test_explicit_values(self) -> None:
        toml = """
[template]
tier = "dependency_tree"

[uncertainty]
lambda = 0.8
min_confidence_eps = 0.05
min_samples = 5
review_joint_threshold = 0.5
"""
        config = parse_lambda_rlm_config(toml)
        assert config.uncertainty.lambda_ == 0.8
        assert config.uncertainty.min_confidence_eps == 0.05
        assert config.uncertainty.min_samples == 5
        assert config.uncertainty.review_joint_threshold == 0.5


class TestReviewConfigExtensions:
    """Tests for the new trigger + threshold fields on ReviewConfig."""

    def test_trigger_defaults_to_always(self) -> None:
        toml = """
[template]
tier = "dependency_tree"

[review]
enabled = true
"""
        config = parse_lambda_rlm_config(toml)
        assert config.review.trigger == "always"
        assert config.review.confidence_threshold == 0.6
        assert config.review.consistency_threshold == 0.7

    def test_trigger_explicit(self) -> None:
        toml = """
[template]
tier = "dependency_tree"

[review]
trigger = "both"
confidence_threshold = 0.5
consistency_threshold = 0.8
"""
        config = parse_lambda_rlm_config(toml)
        assert config.review.trigger == "both"
        assert config.review.confidence_threshold == 0.5
        assert config.review.consistency_threshold == 0.8

    def test_trigger_preserves_existing_fields(self) -> None:
        toml = """
[template]
tier = "dependency_tree"

[review]
enabled = false
trigger = "never"
max_retries_per_source = 3
"""
        config = parse_lambda_rlm_config(toml)
        assert config.review.enabled is False
        assert config.review.trigger == "never"
        assert config.review.max_retries_per_source == 3


class TestTopLevelKCandidates:
    """Tests for top-level k_candidates propagation to extract + fill_section."""

    def test_top_level_propagates_to_extract(self) -> None:
        toml = """
k_candidates = 3

[template]
tier = "dependency_tree"
"""
        config = parse_lambda_rlm_config(toml)
        assert config.extract.k_candidates == 3

    def test_top_level_propagates_to_fill_section(self) -> None:
        toml = """
k_candidates = 3

[template]
tier = "dependency_tree"
"""
        config = parse_lambda_rlm_config(toml)
        assert config.fill_section.k_candidates == 3

    def test_per_section_overrides_top_level(self) -> None:
        toml = """
k_candidates = 3

[template]
tier = "dependency_tree"

[extract]
k_candidates = 5

[fill_section]
k_candidates = 2
"""
        config = parse_lambda_rlm_config(toml)
        assert config.extract.k_candidates == 5
        assert config.fill_section.k_candidates == 2

    def test_template_level_k_candidates_still_supported(self) -> None:
        toml = """
[template]
tier = "dependency_tree"
k_candidates = 4
"""
        config = parse_lambda_rlm_config(toml)
        assert config.extract.k_candidates == 4
        assert config.fill_section.k_candidates == 4

    def test_absent_top_level_defaults_to_one(self) -> None:
        toml = '[template]\ntier = "dependency_tree"\n'
        config = parse_lambda_rlm_config(toml)
        assert config.extract.k_candidates == 1
        assert config.fill_section.k_candidates == 1


class TestUncertaintyScoringActive:
    """Tests that uncertainty scoring activation is derived from review.trigger."""

    def test_trigger_always_means_scoring_inactive(self) -> None:
        toml = '[template]\ntier = "dependency_tree"\n'
        config = parse_lambda_rlm_config(toml)
        assert config.uncertainty_scoring_active is False

    def test_trigger_uncertainty_means_scoring_active(self) -> None:
        toml = """
[template]
tier = "dependency_tree"

[review]
trigger = "uncertainty"
"""
        config = parse_lambda_rlm_config(toml)
        assert config.uncertainty_scoring_active is True

    def test_trigger_both_means_scoring_active(self) -> None:
        toml = """
[template]
tier = "dependency_tree"

[review]
trigger = "both"
"""
        config = parse_lambda_rlm_config(toml)
        assert config.uncertainty_scoring_active is True

    def test_trigger_consistency_means_scoring_inactive(self) -> None:
        toml = """
[template]
tier = "dependency_tree"

[review]
trigger = "consistency"
"""
        config = parse_lambda_rlm_config(toml)
        assert config.uncertainty_scoring_active is False

    def test_trigger_never_means_scoring_inactive(self) -> None:
        toml = """
[template]
tier = "dependency_tree"

[review]
trigger = "never"
"""
        config = parse_lambda_rlm_config(toml)
        assert config.uncertainty_scoring_active is False


class TestConfigValidation:
    """Tests for config validation rules."""

    def test_k_candidates_less_than_one_raises(self) -> None:
        toml = """
[template]
tier = "dependency_tree"

[extract]
k_candidates = 0
"""
        with pytest.raises(ValueError, match="k_candidates"):
            parse_lambda_rlm_config(toml)

    def test_k_gt_one_with_zero_temperature_warns(self) -> None:
        import warnings

        toml = """
[template]
tier = "dependency_tree"

[extract]
k_candidates = 3
temperature = 0.0
"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            parse_lambda_rlm_config(toml)
            assert any("temperature" in str(warning.message) for warning in w)

    def test_k_one_with_explicit_temperature_warns(self) -> None:
        import warnings

        toml = """
[template]
tier = "dependency_tree"

[extract]
k_candidates = 1
temperature = 0.9
"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            parse_lambda_rlm_config(toml)
            assert any("temperature" in str(warning.message) for warning in w)

    def test_consistency_trigger_with_k_one_warns(self) -> None:
        import warnings

        toml = """
[template]
tier = "dependency_tree"

[review]
trigger = "consistency"
"""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            parse_lambda_rlm_config(toml)
            assert any("consistency" in str(warning.message).lower() for warning in w)


def test_compose_mode_defaults_to_orchestrated():
    cfg = parse_lambda_rlm_config("")
    assert cfg.compose.mode == "orchestrated"
    assert cfg.compose.planning_phase_blocking is True


def test_compose_mode_agentic():
    toml_str = """
[compose]
mode = "agentic"
planning_phase_blocking = false
"""
    cfg = parse_lambda_rlm_config(toml_str)
    assert cfg.compose.mode == "agentic"
    assert cfg.compose.planning_phase_blocking is False


def test_compose_mode_rejects_unknown_value():
    toml_str = """
[compose]
mode = "whatever"
"""

    with pytest.raises(ValueError, match="unsupported compose mode"):
        parse_lambda_rlm_config(toml_str)


def test_planning_phase_defaults_disabled():
    cfg = parse_lambda_rlm_config("")
    assert cfg.planning_phase.enabled is False
    assert cfg.planning_phase.extract_slots == ()
    assert cfg.planning_phase.sources == ()


def test_planning_phase_from_toml():
    toml_str = """
[planning_phase]
enabled = true
extract_slots = ["project_name", "site", "client"]
sources = ["email_thread"]
"""
    cfg = parse_lambda_rlm_config(toml_str)
    assert cfg.planning_phase.enabled is True
    assert cfg.planning_phase.extract_slots == ("project_name", "site", "client")
    assert cfg.planning_phase.sources == ("email_thread",)


def test_planning_phase_back_brief_parses_when_present():
    toml = """
[planning_phase]
enabled = true
extract_slots = ["client"]
sources = ["email_thread"]

[planning_phase.back_brief]
enabled = true
sources = ["references/clandeboye_original", "references/culverden_scope"]
topics = ["services", "exclusions", "deliverables"]
model = "au.anthropic.claude-haiku-4-5-20251001-v1:0"
max_output_tokens = 2000
"""
    cfg = parse_lambda_rlm_config(toml)
    bb = cfg.planning_phase.back_brief
    assert bb.enabled is True
    assert bb.sources == ("references/clandeboye_original", "references/culverden_scope")
    assert bb.topics == ("services", "exclusions", "deliverables")
    assert bb.model == "au.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert bb.max_output_tokens == 2000


def test_planning_phase_back_brief_defaults_when_absent():
    toml = """
[planning_phase]
enabled = true
extract_slots = ["client"]
sources = ["email_thread"]
"""
    cfg = parse_lambda_rlm_config(toml)
    bb = cfg.planning_phase.back_brief
    assert bb.enabled is False
    assert bb.sources == ()
    assert bb.topics == ()
    assert bb.model is None
    assert bb.max_output_tokens == 2000


def test_planning_phase_scope_evolution_parses_when_present():
    toml = """
[planning_phase]
enabled = true
extract_slots = ["client"]
sources = ["email_thread"]

[planning_phase.scope_evolution]
enabled = true
sources = ["email_thread"]
model = "au.anthropic.claude-haiku-4-5-20251001-v1:0"
max_output_tokens = 1500
"""
    cfg = parse_lambda_rlm_config(toml)
    se = cfg.planning_phase.scope_evolution
    assert se.enabled is True
    assert se.sources == ("email_thread",)
    assert se.model == "au.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert se.max_output_tokens == 1500


def test_planning_phase_scope_evolution_defaults_when_absent():
    toml = """
[planning_phase]
enabled = true
extract_slots = ["client"]
sources = ["email_thread"]
"""
    cfg = parse_lambda_rlm_config(toml)
    se = cfg.planning_phase.scope_evolution
    assert se.enabled is False
    assert se.sources == ()
    assert se.model is None
    assert se.max_output_tokens == 2000


def test_template_meta_parses_when_present():
    template = """
[meta]
voice = "Plain Australian engineering register"
domain = "Example Dairy dairy processing engagement"
planning_guidance = "client_pm is Example Dairy's Engineering PM; supplier_pm is ExampleCo"

[[sections]]
id = "x"
title = "X"
generation_mode = "guided"
"""
    meta = parse_template_meta(template)
    assert meta.voice == "Plain Australian engineering register"
    assert meta.domain == "Example Dairy dairy processing engagement"
    assert "client_pm" in meta.planning_guidance


def test_template_meta_defaults_when_absent():
    template = """
[[sections]]
id = "x"
title = "X"
generation_mode = "guided"
"""
    meta = parse_template_meta(template)
    assert meta.voice is None
    assert meta.domain is None
    assert meta.planning_guidance is None


def test_sandbox_block_disabled_by_default():
    cfg = parse_lambda_rlm_config('[template]\ndefinition="t.toml"\n')
    assert cfg.sandbox.enabled is False
    assert cfg.sandbox.tool_use is False
    assert cfg.sandbox.tool_use_caps.max_fetches_per_block == 5
    assert cfg.sandbox.tool_use_caps.max_total_fetches == 30
    assert cfg.sandbox.extractor_overrides == {}


def test_sandbox_block_parses_overrides():
    toml_text = """
[template]
definition = "t.toml"
[sandbox]
enabled = true
tool_use = false
[sandbox.tool_use_caps]
max_fetches_per_block = 10
max_total_fetches = 50
[sandbox.extractor_overrides]
"thread.md" = "email_thread"
"""
    cfg = parse_lambda_rlm_config(toml_text)
    assert cfg.sandbox.enabled is True
    assert cfg.sandbox.tool_use is False
    assert cfg.sandbox.tool_use_caps.max_fetches_per_block == 10
    assert cfg.sandbox.tool_use_caps.max_total_fetches == 50
    assert cfg.sandbox.extractor_overrides == {"thread.md": "email_thread"}


def test_grounding_block_defaults_when_absent():
    cfg = parse_lambda_rlm_config('[template]\ndefinition = "t.toml"\n')
    assert cfg.grounding.check == "default"
    assert cfg.grounding.custom_facts == {}


def test_grounding_block_parses_check_off():
    toml_text = """
[template]
definition = "t.toml"
[grounding]
check = "off"
"""
    cfg = parse_lambda_rlm_config(toml_text)
    assert cfg.grounding.check == "off"


def test_grounding_custom_facts_compiled_to_regex_patterns():
    toml_text = r"""
[template]
definition = "t.toml"
[grounding.custom_facts]
project_codes = "\\b(?:EST|WWL)\\d{5,6}\\b"
"""
    cfg = parse_lambda_rlm_config(toml_text)
    assert "project_codes" in cfg.grounding.custom_facts
    pattern = cfg.grounding.custom_facts["project_codes"]
    # Compiled regex matches its target
    assert pattern.search("EST112345 found") is not None
    assert pattern.search("just text") is None


def test_structure_enforcement_defaults() -> None:
    cfg = StructureEnforcementConfig()
    assert cfg.enabled is False
    assert cfg.max_retries == 2
    assert cfg.validator_model == "au.anthropic.claude-haiku-4-5"


def test_parse_lambda_rlm_config_omits_structure_enforcement_by_default() -> None:
    cfg = parse_lambda_rlm_config("")
    assert cfg.structure_enforcement.enabled is False


def test_parse_lambda_rlm_config_reads_structure_enforcement_block() -> None:
    toml = """
[structure_enforcement]
enabled = true
max_retries = 1
validator_model = "au.anthropic.claude-haiku-4-5"
"""
    cfg = parse_lambda_rlm_config(toml)
    assert cfg.structure_enforcement.enabled is True
    assert cfg.structure_enforcement.max_retries == 1
    assert cfg.structure_enforcement.validator_model == "au.anthropic.claude-haiku-4-5"


def test_parse_lambda_rlm_config_enabled_only_uses_defaults_for_other_fields() -> None:
    toml = """
[structure_enforcement]
enabled = true
"""
    cfg = parse_lambda_rlm_config(toml)
    assert cfg.structure_enforcement.enabled is True
    assert cfg.structure_enforcement.max_retries == 2
    assert cfg.structure_enforcement.validator_model == "au.anthropic.claude-haiku-4-5"
