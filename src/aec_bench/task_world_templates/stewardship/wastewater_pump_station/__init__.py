# ABOUTME: Exposes the certified wastewater pump-station reference-package boundary.
# ABOUTME: Keeps package validation and models local to the pump-station environment.

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_models import (
    ReferencePackage,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    EXPECTED_MANIFEST_CONTENT_ID,
    EXPECTED_PACKAGE_CONTENT_ID,
    REFERENCE_PACKAGE_FILE_NAMES,
    ReferencePackageError,
    bundled_reference_package_root,
    load_reference_package,
)

__all__ = [
    "EXPECTED_MANIFEST_CONTENT_ID",
    "EXPECTED_PACKAGE_CONTENT_ID",
    "REFERENCE_PACKAGE_FILE_NAMES",
    "ReferencePackage",
    "ReferencePackageError",
    "bundled_reference_package_root",
    "load_reference_package",
]
