# ABOUTME: Instance sampler for task generation templates.
# ABOUTME: Produces SampledInstance by drawing params from archetype ranges and difficulty presets.

import random
from collections.abc import Callable
from datetime import UTC, datetime

from aec_bench.generation.contracts import GenerationMetadata, SampledInstance
from aec_bench.templates.contracts import (
    DifficultyPreset,
    ParamType,
    TemplateConfig,
    VisibilityLevel,
)


def _sample_param_value(
    param_name: str,
    config: TemplateConfig,
    archetype_name: str,
    preset: DifficultyPreset,
    rng: random.Random,
) -> float | int | str:
    """Sample a single parameter value from the archetype range or param spec.

    Priority order:
    1. If the difficulty preset has an `extra` constraint for this param, use it.
    2. If the archetype defines a range for this param, sample from that range.
    3. Otherwise, sample from the param spec's own range or values list.
    """
    param_spec = config.params[param_name]
    archetype_spec = config.archetypes.get(archetype_name)

    # Difficulty-level extra constraints override everything (e.g., footing_shape = ["strip"])
    if param_name in preset.extra:
        constrained_values = preset.extra[param_name]
        if isinstance(constrained_values, list) and constrained_values:
            chosen = rng.choice(constrained_values)
            if param_spec.type is ParamType.FLOAT:
                return float(chosen)
            if param_spec.type is ParamType.INT:
                return int(chosen)
            return str(chosen)

    # Boolean extras can disable optional params. Convention: if preset.extra has
    # a key that is a prefix of param_name and its value is False, use param's max
    # value (effectively "not present"). E.g., water_table=false → water_table_depth_m
    # gets set to its max (100m, effectively no water table).
    if param_spec.optional:
        for extra_key, extra_val in preset.extra.items():
            if extra_val is False and param_name.startswith(extra_key):
                if param_spec.max_value is not None:
                    return param_spec.max_value

    # Archetype-specific range takes precedence over the global param range
    if archetype_spec is not None and param_name in archetype_spec.params:
        arch_range = archetype_spec.params[param_name]
        if param_spec.type is ParamType.FLOAT:
            return rng.uniform(arch_range.min, arch_range.max)
        if param_spec.type is ParamType.INT:
            return int(rng.randint(int(arch_range.min), int(arch_range.max)))
        # Enum inside an archetype range shouldn't occur, fall through

    # Sample from global param spec
    if param_spec.type is ParamType.FLOAT:
        assert param_spec.min_value is not None and param_spec.max_value is not None
        return rng.uniform(param_spec.min_value, param_spec.max_value)

    if param_spec.type is ParamType.INT:
        assert param_spec.min_value is not None and param_spec.max_value is not None
        return int(rng.randint(int(param_spec.min_value), int(param_spec.max_value)))

    # ENUM
    assert param_spec.values is not None
    return rng.choice(param_spec.values)


def _pick_site_context(archetype_name: str, config: TemplateConfig, rng: random.Random) -> str:
    """Pick a site context that lists the given archetype, falling back to the archetype name."""
    archetype_spec = config.archetypes.get(archetype_name)
    if archetype_spec is not None and archetype_spec.site_contexts:
        return rng.choice(archetype_spec.site_contexts)
    return archetype_name


def _make_instance_name(archetype_name: str, site_context: str, instance_index: int) -> str:
    """Produce a human-readable instance name from archetype, site context, and index."""
    # Normalise: replace underscores with hyphens and lower-case
    arch_slug = archetype_name.replace("_", "-").lower()
    site_slug = site_context.replace("_", "-").lower()
    return f"{site_slug}-{arch_slug}-{instance_index:02d}"


def sample_instance(
    config: TemplateConfig,
    engine_compute: Callable[..., dict[str, float]],
    difficulty_name: str,
    seed: int,
    instance_index: int,
) -> SampledInstance:
    """Sample a single task instance from the template configuration.

    Draws parameter values from archetype ranges and difficulty presets,
    calls engine_compute to obtain ground truth, and returns a SampledInstance
    with full provenance metadata.
    """
    preset = config.difficulty[difficulty_name]
    rng = random.Random(seed + instance_index)

    # Choose archetype from those allowed for this difficulty
    archetype_name = rng.choice(preset.archetypes)
    site_context = _pick_site_context(archetype_name, config, rng)

    # Sample all declared parameters
    all_params: dict[str, float | int | str] = {}
    for param_name in config.params:
        all_params[param_name] = _sample_param_value(param_name, config, archetype_name, preset, rng)

    # Compute ground truth by calling the engine
    ground_truth: dict[str, float] = engine_compute(**all_params)

    # Split into visible and hidden based on difficulty visibility level
    if preset.visibility is VisibilityLevel.ALL_GIVEN:
        visible_params = dict(all_params)
        hidden_params: dict[str, float | int | str] = {}
    else:
        # PARTIAL or SCENARIO_ONLY: params in preset.hidden_params go to hidden
        hidden_set = set(preset.hidden_params)
        visible_params = {k: v for k, v in all_params.items() if k not in hidden_set}
        hidden_params = {k: v for k, v in all_params.items() if k in hidden_set}

    instance_name = _make_instance_name(archetype_name, site_context, instance_index)

    metadata = GenerationMetadata(
        origin="generated",
        template=config.meta.name,
        template_version="1.0",
        seed=seed,
        timestamp=datetime.now(tz=UTC),
        difficulty=difficulty_name,
        visibility_level=preset.visibility,
        archetype=archetype_name,
        site_context=site_context,
    )

    return SampledInstance(
        instance_name=instance_name,
        all_params=all_params,
        visible_params=visible_params,
        hidden_params=hidden_params,
        ground_truth=ground_truth,
        archetype_name=archetype_name,
        site_context=site_context,
        difficulty=difficulty_name,
        metadata=metadata,
    )
