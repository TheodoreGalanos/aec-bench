# ABOUTME: Exposes the facade-submittal lifecycle conformance case.
# ABOUTME: Keeps the owner entry point beside the lifecycle definition.

from __future__ import annotations

from aec_bench.lifecycles.conformance import LifecycleConformanceCase, build_lifecycle_conformance_case
from aec_bench.lifecycles.structural_review.facade_submittal import LIFECYCLE_DESCRIPTOR


def lifecycle_conformance_case() -> LifecycleConformanceCase:
    return build_lifecycle_conformance_case(LIFECYCLE_DESCRIPTOR.definition)
