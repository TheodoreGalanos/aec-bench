# ABOUTME: Exposes the drainage-model lifecycle conformance case.
# ABOUTME: Keeps the owner entry point beside the lifecycle definition.

from __future__ import annotations

from aec_bench.lifecycles.conformance import LifecycleConformanceCase, build_lifecycle_conformance_case
from aec_bench.lifecycles.stormwater_design.drainage_model import LIFECYCLE_DESCRIPTOR


def lifecycle_conformance_case() -> LifecycleConformanceCase:
    return build_lifecycle_conformance_case(LIFECYCLE_DESCRIPTOR.definition)
