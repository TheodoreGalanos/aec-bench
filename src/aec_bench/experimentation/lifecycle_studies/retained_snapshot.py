# ABOUTME: Defines neutral value objects for one retained lifecycle study snapshot.
# ABOUTME: Lets current retention and historical validation share paths without a module cycle.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aec_bench.experimentation.lifecycle_studies.ablation_plan import LifecycleAblationPlan


@dataclass(frozen=True, slots=True)
class LifecycleAblationInvocation:
    """Identify the one sealed lifecycle invocation for a planned study trial."""

    manifest_path: Path
    manifest: dict[str, Any]
    metrics_path: Path
    verification_path: Path
    index_entry: dict[str, Any]


@dataclass(frozen=True, slots=True)
class LifecycleAblationSnapshot:
    """Expose the validated roots and invocation of one immutable study snapshot."""

    root: Path
    package_dir: Path
    run_dir: Path
    invocation: LifecycleAblationInvocation
    plan: LifecycleAblationPlan
