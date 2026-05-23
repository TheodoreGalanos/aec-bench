# ABOUTME: Bootstrap tests for the Phase 0B aec-bench Python scaffold.
# ABOUTME: Verifies package import and the expected minimal configuration defaults.

from pathlib import Path

from aec_bench import __version__
from aec_bench.config import load_config


def test_package_version_is_exposed() -> None:
    assert __version__ == "0.1.0"


def test_load_config_returns_expected_default_paths() -> None:
    config = load_config()

    assert config.project_root.name == "aec-bench"
    assert config.tasks_root == config.project_root / "tasks"
    assert config.ledger_root == config.project_root / "artefacts" / "ledger"
    assert config.default_compute_backend == "modal"
    assert isinstance(config.project_root, Path)
