# ABOUTME: Exposes task-neutral continual-world definition, catalogue, and local durability boundaries.
# ABOUTME: Imports no concrete task world or execution transport.

from aec_bench.task_world_templates.continual.catalogue import ContinualWorldCatalogue
from aec_bench.task_world_templates.continual.definition import (
    ContinualWorldDefinition,
    LoadedContinualWorldProfile,
    python_source_sha256,
)
from aec_bench.task_world_templates.continual.durability import (
    ContinualWorldLockConfinementError,
    ContinualWorldLockError,
    ImmutableArtifact,
    ImmutableArtifactCollisionError,
    ImmutableArtifactConfinementError,
    ImmutableArtifactIntegrityError,
    ImmutableArtifactStoreError,
    ImmutableByteStore,
    exclusive_local_file_lock,
)

__all__ = [
    "ContinualWorldCatalogue",
    "ContinualWorldDefinition",
    "ContinualWorldLockConfinementError",
    "ContinualWorldLockError",
    "ImmutableArtifact",
    "ImmutableArtifactCollisionError",
    "ImmutableArtifactConfinementError",
    "ImmutableArtifactIntegrityError",
    "ImmutableArtifactStoreError",
    "ImmutableByteStore",
    "LoadedContinualWorldProfile",
    "exclusive_local_file_lock",
    "python_source_sha256",
]
