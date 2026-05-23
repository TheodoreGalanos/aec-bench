# ABOUTME: Tests RemediationTaskConfig contract — parse [remediation] block from task.toml.
# ABOUTME: Default enabled=True when table absent; task-level overrides for iterations/target.

import dataclasses

import pytest

from aec_bench.contracts.remediation_config import (
    RemediationTaskConfig,
    parse_remediation_config,
)


def test_config_defaults_enabled_true():
    config = RemediationTaskConfig()
    assert config.enabled is True
    assert config.max_iterations is None
    assert config.target_reward is None


def test_config_is_frozen():
    config = RemediationTaskConfig()
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.enabled = False  # type: ignore[misc]


def test_parse_absent_table_returns_default():
    config = parse_remediation_config({"metadata": {"difficulty": "hard"}})
    assert config.enabled is True
    assert config.max_iterations is None


def test_parse_explicit_disable():
    config = parse_remediation_config({"remediation": {"enabled": False}})
    assert config.enabled is False


def test_parse_overrides():
    config = parse_remediation_config(
        {
            "remediation": {
                "enabled": True,
                "max_iterations": 5,
                "target_reward": 0.90,
            }
        }
    )
    assert config.enabled is True
    assert config.max_iterations == 5
    assert config.target_reward == 0.90


def test_parse_partial_overrides():
    config = parse_remediation_config({"remediation": {"max_iterations": 2}})
    assert config.enabled is True
    assert config.max_iterations == 2
    assert config.target_reward is None
