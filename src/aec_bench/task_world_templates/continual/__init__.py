# ABOUTME: Exposes task-neutral continual-world definition, catalogue, and local durability boundaries.
# ABOUTME: Imports no concrete task world or execution transport.

from aec_bench.task_world_templates.continual.branch_port import (
    ContinualWorldBranchMaterialization,
    ContinualWorldBranchPort,
    VerifiedContinualWorldBranchOrigin,
)
from aec_bench.task_world_templates.continual.catalogue import ContinualWorldCatalogue
from aec_bench.task_world_templates.continual.definition import (
    ContinualWorldDefinition,
    LoadedContinualWorldProfile,
    python_source_sha256,
)
from aec_bench.task_world_templates.continual.durability import (
    ContinualWorldLockConfinementError,
    ContinualWorldLockError,
    DurableFileReplaceConfinementError,
    DurableFileReplaceError,
    DurableFileReplaceIntegrityError,
    ImmutableArtifact,
    ImmutableArtifactCollisionError,
    ImmutableArtifactConfinementError,
    ImmutableArtifactIntegrityError,
    ImmutableArtifactStoreError,
    ImmutableByteStore,
    exclusive_local_file_lock,
    mkdir_durable,
    replace_file_bytes_durable,
)
from aec_bench.task_world_templates.continual.rollout_control import (
    ContinualRolloutControl,
    ContinualRolloutError,
)

__all__ = [
    "ContinualWorldCatalogue",
    "ContinualWorldBranchMaterialization",
    "ContinualWorldBranchPort",
    "ContinualWorldDefinition",
    "ContinualWorldLockConfinementError",
    "ContinualWorldLockError",
    "DurableFileReplaceConfinementError",
    "DurableFileReplaceError",
    "DurableFileReplaceIntegrityError",
    "ImmutableArtifact",
    "ImmutableArtifactCollisionError",
    "ImmutableArtifactConfinementError",
    "ImmutableArtifactIntegrityError",
    "ImmutableArtifactStoreError",
    "ImmutableByteStore",
    "LoadedContinualWorldProfile",
    "ContinualRolloutControl",
    "ContinualRolloutError",
    "VerifiedContinualWorldBranchOrigin",
    "exclusive_local_file_lock",
    "mkdir_durable",
    "python_source_sha256",
    "replace_file_bytes_durable",
]
