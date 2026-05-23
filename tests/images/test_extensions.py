# ABOUTME: Tests for Docker extension definitions and Dockerfile generator.
# ABOUTME: Verifies extension registry, Dockerfile generation, and edge cases.

import pytest

from aec_bench.images.extensions import (
    CORE_APT_PACKAGES,
    CORE_BASE_IMAGE,
    EXTENSIONS,
    generate_dockerfile,
)


def test_core_base_image_is_ubuntu() -> None:
    assert "ubuntu" in CORE_BASE_IMAGE


def test_core_apt_packages_include_python() -> None:
    assert "python3" in CORE_APT_PACKAGES


def test_extensions_registry_has_expected_keys() -> None:
    assert "claude-cli" in EXTENSIONS
    assert "multimodal" in EXTENSIONS
    assert "ocr" in EXTENSIONS


def test_generate_dockerfile_core_only() -> None:
    result = generate_dockerfile([])
    assert "ubuntu:24.04" in result
    assert "python3" in result
    assert "WORKDIR /workspace" in result
    assert "Auto-generated" in result


def test_generate_dockerfile_claude_cli() -> None:
    result = generate_dockerfile(["claude-cli"])
    assert "curl" in result
    assert "procps" in result
    assert "claude.ai/install.sh" in result


def test_generate_dockerfile_multimodal() -> None:
    result = generate_dockerfile(["multimodal"])
    assert "python:3.13-slim" in result
    assert "pydantic-ai" in result
    assert "matplotlib" in result


def test_generate_dockerfile_stacked_extensions() -> None:
    result = generate_dockerfile(["claude-cli", "multimodal"])
    assert "pydantic-ai" in result
    assert "claude.ai/install.sh" in result


def test_generate_dockerfile_unknown_extension_raises() -> None:
    with pytest.raises(ValueError, match="Unknown extensions"):
        generate_dockerfile(["nonexistent"])


def test_generate_dockerfile_deduplicates_apt_packages() -> None:
    result = generate_dockerfile(["claude-cli"])
    # python3 appears in both core and should only appear once
    lines = result.split("\n")
    apt_lines = [line for line in lines if "python3" in line]
    assert len(apt_lines) == 1


def test_generate_dockerfile_includes_task_description() -> None:
    result = generate_dockerfile([], task_description="voltage drop calc")
    assert "voltage drop calc" in result


def test_generate_dockerfile_ocr_extension() -> None:
    result = generate_dockerfile(["ocr"])
    assert "tesseract-ocr" in result
    assert "poppler-utils" in result
    assert "ubuntu:24.04" in result


def test_generate_dockerfile_base_image_override_last_wins() -> None:
    """When multiple extensions have base_image_override, last one wins."""
    result = generate_dockerfile(["multimodal"])
    assert "python:3.13-slim" in result
    assert "ubuntu:24.04" not in result


def test_generate_dockerfile_platform_always_present() -> None:
    """The --platform=linux/amd64 flag should always be in the FROM line."""
    for exts in [[], ["claude-cli"], ["multimodal"], ["ocr"]]:
        result = generate_dockerfile(exts)
        assert "--platform=linux/amd64" in result


def test_generate_dockerfile_extension_order_preserves_run_commands() -> None:
    """Run commands should appear in the order extensions are listed."""
    result = generate_dockerfile(["claude-cli"])
    assert "curl -fsSL https://claude.ai/install.sh | bash" in result


def test_generate_dockerfile_copy_files_none_by_default() -> None:
    """When copy_files is not provided, only the trajectory_writer.py COPY line appears."""
    result = generate_dockerfile(["claude-cli"])
    copy_lines = [line for line in result.split("\n") if line.startswith("COPY")]
    assert len(copy_lines) == 1
    assert "trajectory_writer.py" in copy_lines[0]


def test_generate_dockerfile_copy_files_empty_list() -> None:
    """An empty copy_files list still includes the trajectory_writer.py COPY line."""
    result = generate_dockerfile(["claude-cli"], copy_files=[])
    copy_lines = [line for line in result.split("\n") if line.startswith("COPY")]
    assert len(copy_lines) == 1
    assert "trajectory_writer.py" in copy_lines[0]


def test_generate_dockerfile_copy_files_adds_copy_lines() -> None:
    """Extra files in the environment directory are COPYed into /workspace."""
    result = generate_dockerfile(
        ["claude-cli"],
        copy_files=["heat_load_calc.py", "system_prompt.md"],
    )
    assert "COPY heat_load_calc.py /workspace/heat_load_calc.py" in result
    assert "COPY system_prompt.md /workspace/system_prompt.md" in result


def test_generate_dockerfile_copy_files_sorted() -> None:
    """Copy files are sorted alphabetically for deterministic output; trajectory_writer.py appears first."""
    result = generate_dockerfile(
        ["claude-cli"],
        copy_files=["zebra.txt", "alpha.txt"],
    )
    lines = result.split("\n")
    copy_lines = [line for line in lines if line.startswith("COPY")]
    # trajectory_writer.py + alpha.txt + zebra.txt = 3 COPY lines
    assert len(copy_lines) == 3
    assert "trajectory_writer.py" in copy_lines[0]
    assert "alpha.txt" in copy_lines[1]
    assert "zebra.txt" in copy_lines[2]


def test_generate_dockerfile_copy_files_after_workdir() -> None:
    """COPY lines appear after the WORKDIR directive."""
    result = generate_dockerfile(
        ["claude-cli"],
        copy_files=["data.csv"],
    )
    lines = result.split("\n")
    workdir_idx = next(i for i, line in enumerate(lines) if "WORKDIR" in line)
    copy_idx = next(i for i, line in enumerate(lines) if "COPY" in line)
    assert copy_idx > workdir_idx


def test_generate_dockerfile_always_includes_trajectory_writer() -> None:
    """trajectory_writer.py COPY line is always present even with no extensions and no copy_files."""
    result = generate_dockerfile([], copy_files=[])
    assert "COPY trajectory_writer.py /workspace/trajectory_writer.py" in result


def test_generate_dockerfile_trajectory_writer_with_extensions() -> None:
    """trajectory_writer.py COPY line is present alongside extension-driven copy files."""
    result = generate_dockerfile(["claude-cli"], copy_files=["system_prompt.md"])
    assert "COPY trajectory_writer.py /workspace/trajectory_writer.py" in result
    assert "COPY system_prompt.md /workspace/system_prompt.md" in result
