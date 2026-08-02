# ABOUTME: Exposes shared local durability primitives through the continual-world runtime boundary.
# ABOUTME: Keeps continual-world consumers independent from lower ledger implementation details.

from aec_bench.ledger.durability import (
    DurableFileReplaceConfinementError,
    DurableFileReplaceError,
    DurableFileReplaceIntegrityError,
    mkdir_durable,
    replace_file_bytes_durable,
)
from aec_bench.ledger.immutable_artifact_store import (
    ImmutableArtifact,
    ImmutableArtifactCollisionError,
    ImmutableArtifactConfinementError,
    ImmutableArtifactIntegrityError,
    ImmutableArtifactStoreError,
    ImmutableByteStore,
)
from aec_bench.ledger.local_lock import (
    LocalFileLockConfinementError as ContinualWorldLockConfinementError,
)
from aec_bench.ledger.local_lock import LocalFileLockError as ContinualWorldLockError
from aec_bench.ledger.local_lock import exclusive_local_file_lock as exclusive_local_file_lock

__all__ = [
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
    "exclusive_local_file_lock",
    "mkdir_durable",
    "replace_file_bytes_durable",
]
