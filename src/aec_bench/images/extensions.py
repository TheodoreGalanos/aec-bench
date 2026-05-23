# ABOUTME: Docker extension definitions and Dockerfile generator for aec-bench tasks.
# ABOUTME: Combines a core base image with stackable capability extensions.

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Extension:
    """A stackable Docker capability extension."""

    name: str
    description: str
    apt_packages: list[str] = field(default_factory=list)
    pip_packages: list[str] = field(default_factory=list)
    run_commands: list[str] = field(default_factory=list)
    base_image_override: str | None = None


# Core base image — every task gets this
CORE_BASE_IMAGE = "ubuntu:24.04"
CORE_APT_PACKAGES = ["python3", "bc"]

# Extension registry
EXTENSIONS: dict[str, Extension] = {
    "claude-cli": Extension(
        name="claude-cli",
        description="Claude Code CLI for agentic tool use",
        apt_packages=["curl", "procps"],
        run_commands=["curl -fsSL https://claude.ai/install.sh | bash"],
    ),
    "multimodal": Extension(
        name="multimodal",
        description="PydanticAI + matplotlib for multimodal tasks with chart generation",
        pip_packages=["pydantic-ai[anthropic,openai]", "matplotlib"],
        base_image_override="python:3.13-slim",
    ),
    "ocr": Extension(
        name="ocr",
        description="Tesseract OCR and PDF utilities",
        apt_packages=["tesseract-ocr", "poppler-utils"],
    ),
}


def generate_dockerfile(
    extensions: list[str],
    task_description: str = "benchmark task",
    copy_files: list[str] | None = None,
) -> str:
    """Generate a Dockerfile from core + selected extensions.

    The generated Dockerfile:
    1. Starts from the core base image (or an extension's override)
    2. Installs apt packages from core + all extensions
    3. Installs pip packages from all extensions
    4. Runs custom commands from extensions (e.g., Claude CLI install)
    5. Sets WORKDIR to /workspace
    6. COPYs any extra files found in the environment directory
    """
    # Validate extensions
    unknown = set(extensions) - set(EXTENSIONS)
    if unknown:
        valid = ", ".join(sorted(EXTENSIONS))
        raise ValueError(f"Unknown extensions: {unknown}. Valid: {valid}")

    ext_objects = [EXTENSIONS[name] for name in extensions]

    # Determine base image — last extension with override wins
    base_image = CORE_BASE_IMAGE
    for ext in ext_objects:
        if ext.base_image_override:
            base_image = ext.base_image_override

    # Collect apt packages (core + extensions, deduplicated, sorted)
    apt_packages = list(CORE_APT_PACKAGES)
    for ext in ext_objects:
        apt_packages.extend(ext.apt_packages)
    apt_packages = sorted(set(apt_packages))

    # Collect pip packages (extensions only, deduplicated)
    pip_packages: list[str] = []
    for ext in ext_objects:
        pip_packages.extend(ext.pip_packages)
    pip_packages = sorted(set(pip_packages))

    # Collect run commands (order matters — preserve extension order)
    run_commands: list[str] = []
    for ext in ext_objects:
        run_commands.extend(ext.run_commands)

    # Build extension description for ABOUTME
    if extensions:
        ext_desc = " + ".join(extensions)
    else:
        ext_desc = "core only"

    # Generate Dockerfile
    lines = [
        f"# ABOUTME: Auto-generated container for {task_description}.",
        f"# ABOUTME: Extensions: {ext_desc}. Regenerate with: aec-bench generate dockerfiles",
        f"FROM --platform=linux/amd64 {base_image}",
        "",
    ]

    # apt packages
    if apt_packages:
        pkg_line = " \\\n    ".join(apt_packages)
        lines.append("RUN apt-get update && apt-get install -y \\")
        lines.append(f"    {pkg_line} \\")
        lines.append("    && rm -rf /var/lib/apt/lists/*")
        lines.append("")

    # pip packages
    if pip_packages:
        pkg_line = " ".join(pip_packages)
        lines.append(f"RUN pip install --no-cache-dir {pkg_line}")
        lines.append("")

    # Custom run commands
    for cmd in run_commands:
        lines.append(f"RUN {cmd}")
        lines.append("")

    lines.append("WORKDIR /workspace")
    lines.append("")

    # trajectory_writer.py is always present — enables trajectory recording in every task
    lines.append("COPY trajectory_writer.py /workspace/trajectory_writer.py")

    # COPY extra files from the environment directory into /workspace
    if copy_files:
        for filename in sorted(copy_files):
            lines.append(f"COPY {filename} /workspace/{filename}")

    lines.append("")

    return "\n".join(lines)
