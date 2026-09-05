# ABOUTME: Renders Prime hosted training configuration for CLI and qualification callers.
# ABOUTME: Keeps external TOML field spelling at one provider boundary.

from __future__ import annotations

import json
import math


def render_train_config(
    *,
    environment: str,
    model: str,
    max_steps: int,
    batch_size: int,
    rollouts_per_example: int,
    max_tokens: int,
    env_args_list: list[dict[str, object]],
    eval_interval: int | None,
    eval_num_examples: int | None,
    eval_rollouts_per_example: int,
    eval_base_model: bool,
    adapters_keep_last: int,
    checkpoint_id: str | None = None,
) -> str:
    lines = [
        f"model = {_toml_string(model)}",
        f"max_steps = {max_steps}",
        f"batch_size = {batch_size}",
        f"rollouts_per_example = {rollouts_per_example}",
        "",
        "[sampling]",
        f"max_tokens = {max_tokens}",
    ]
    if checkpoint_id is not None:
        lines.insert(4, f"checkpoint_id = {_toml_string(checkpoint_id)}")
    for env_args in env_args_list:
        lines.extend(
            [
                "",
                "[[env]]",
                f"id = {_toml_string(environment)}",
            ]
        )
        if env_args:
            lines.append(f"args = {_toml_inline_table(env_args)}")

    if eval_interval is not None:
        lines.extend(
            [
                "",
                "[eval]",
                f"interval = {eval_interval}",
            ]
        )
        if eval_num_examples is not None:
            lines.append(f"num_examples = {eval_num_examples}")
        lines.extend(
            [
                f"rollouts_per_example = {eval_rollouts_per_example}",
                f"eval_base_model = {_toml_bool(eval_base_model)}",
            ]
        )

        for env_args in env_args_list:
            evaluation_args = dict(env_args)
            evaluation_args["split"] = "eval"
            if eval_num_examples is not None:
                evaluation_args["num_examples"] = eval_num_examples
            else:
                evaluation_args.pop("num_examples", None)
            lines.extend(
                [
                    "",
                    "[[eval.env]]",
                    f"id = {_toml_string(environment)}",
                    f"args = {_toml_inline_table(evaluation_args)}",
                ]
            )

    lines.extend(
        [
            "",
            "[adapters]",
            "interval = 0",
            f"keep_last = {adapters_keep_last}",
            "",
        ]
    )
    return "\n".join(lines)


def _toml_inline_table(values: dict[str, object]) -> str:
    bits = [f"{key} = {_toml_value(value)}" for key, value in values.items()]
    return "{ " + ", ".join(bits) + " }"


def _toml_value(value: object) -> str:
    if isinstance(value, str):
        return _toml_string(value)
    if isinstance(value, bool):
        return _toml_bool(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return _toml_float(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise TypeError(f"unsupported TOML value: {value!r}")


def _toml_string(value: str) -> str:
    return json.dumps(value)


def _toml_bool(value: bool) -> str:
    return "true" if value else "false"


def _toml_float(value: float) -> str:
    if not math.isfinite(value):
        raise TypeError(f"unsupported TOML float: {value!r}")
    text = format(value, ".15g")
    if "." not in text and "e" not in text.lower():
        return f"{text}.0"
    return text


def validate_training_handoff(config: dict[str, object]) -> None:
    """Reject known unsafe or removed fields before handing a config to Prime.

    Prime still owns complete configuration and model-availability validation.
    This check needs no credentials and does not establish hosted compatibility.
    """
    if not isinstance(config.get("model"), str) or not str(config["model"]).strip():
        raise ValueError("training requires an explicit model")
    checkpoint = config.get("checkpoint_id")
    if checkpoint is not None and (not isinstance(checkpoint, str) or not checkpoint.strip()):
        raise ValueError("checkpoint_id must be a non-empty string")
    if "buffer" in config:
        raise ValueError("Prime removed the difficulty buffer; use a current rollout-filter configuration")
    evaluation = config.get("eval", {})
    if isinstance(evaluation, dict) and "skip_first_step" in evaluation:
        raise ValueError("the pinned Prime CLI uses eval.eval_base_model instead of eval.skip_first_step")
    environments = config.get("env")
    if not isinstance(environments, list) or not environments:
        raise ValueError("training requires at least one environment")
    for environment in environments:
        if not isinstance(environment, dict):
            raise ValueError("training environment must be a table")
        arguments = environment.get("args", {})
        if isinstance(arguments, dict) and arguments.get("split") in ("eval", "all", "test", "acceptance"):
            raise ValueError("an evaluation-only split cannot supply training data")
    for key in ("max_steps", "batch_size", "rollouts_per_example"):
        value = config.get(key)
        if type(value) is not int or value <= 0:
            raise ValueError(f"{key} must be a positive integer")
    batch_size = config["batch_size"]
    rollouts = config["rollouts_per_example"]
    assert isinstance(batch_size, int) and isinstance(rollouts, int)
    if batch_size % rollouts:
        raise ValueError("batch_size must be divisible by rollouts_per_example")
