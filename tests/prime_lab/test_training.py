# ABOUTME: Checks the current Prime hosted config handoff without hosted access.
# ABOUTME: Rejects evaluation-only data and removed fields before any training command starts.

import tomllib

import pytest

from aec_bench.prime_lab.training import render_train_config, validate_training_handoff


@pytest.mark.parametrize("eval_base_model", [True, False])
def test_checkpoint_handoff_and_base_evaluation(eval_base_model: bool) -> None:
    config = tomllib.loads(
        render_train_config(
            environment="hydraulic",
            model="Qwen/Qwen3.5-0.8B",
            max_steps=1,
            batch_size=4,
            rollouts_per_example=4,
            max_tokens=2048,
            env_args_list=[{"split": "train", "num_examples": 50}],
            eval_interval=1,
            eval_num_examples=None,
            eval_rollouts_per_example=1,
            eval_base_model=eval_base_model,
            adapters_keep_last=1,
            checkpoint_id="cp_test",
        )
    )
    validate_training_handoff(config)
    assert config["checkpoint_id"] == "cp_test"
    prime = pytest.importorskip("prime_cli.commands.rl")
    validated = prime.RLConfig.model_validate(config)
    evaluation = validated.eval.to_api_dict()
    assert evaluation is not None
    assert evaluation["eval_base_model"] is eval_base_model
    assert evaluation["environments"][0]["args"] == {"split": "eval"}
    assert config["env"][0]["args"]["num_examples"] == 50


@pytest.mark.parametrize(
    "extra",
    [
        {"buffer": {}},
        {"eval": {"skip_first_step": False}},
        {"env": [{"id": "hydraulic", "args": {"split": "eval"}}]},
        {"env": [{"id": "hydraulic", "args": {"split": "all"}}]},
        {"batch_size": 3},
        {"max_steps": True},
    ],
)
def test_invalid_handoff_is_rejected(extra: dict[str, object]) -> None:
    config = {
        "model": "model",
        "max_steps": 1,
        "batch_size": 4,
        "rollouts_per_example": 4,
        "env": [{"id": "hydraulic", "args": {"split": "train"}}],
    }
    with pytest.raises(ValueError):
        validate_training_handoff(config | extra)
