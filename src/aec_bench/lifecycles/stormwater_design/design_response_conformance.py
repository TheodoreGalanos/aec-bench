# ABOUTME: Exposes the stormwater design-response lifecycle conformance case.
# ABOUTME: Keeps the owner entry point beside the lifecycle definition.

from __future__ import annotations

from pathlib import Path

from aec_bench.lifecycles.conformance import (
    LifecycleConformanceCase,
    build_lifecycle_conformance_case_with_writer,
)
from aec_bench.lifecycles.stormwater_design.design_response import LIFECYCLE_DESCRIPTOR
from aec_bench.lifecycles.stormwater_design.design_response_smoke import (
    write_hydraulic_design_response_smoke_submission,
)


def _write_submission(package: Path, run: Path, checkpoint_id: str, session_id: str, output: Path) -> None:
    write_hydraulic_design_response_smoke_submission(
        package,
        run,
        checkpoint_id,
        session_id,
        output,
        selected_intervention_id="controlled_orifice_resize",
    )


def lifecycle_conformance_case() -> LifecycleConformanceCase:
    return build_lifecycle_conformance_case_with_writer(LIFECYCLE_DESCRIPTOR.definition, _write_submission)
