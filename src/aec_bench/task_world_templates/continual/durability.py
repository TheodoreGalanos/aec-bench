# ABOUTME: Exposes the shared local POSIX lock through the continual-world runtime boundary.
# ABOUTME: Keeps continual-world consumers independent from lower ledger implementation details.

from aec_bench.ledger.local_lock import (
    LocalFileLockConfinementError as ContinualWorldLockConfinementError,
)
from aec_bench.ledger.local_lock import LocalFileLockError as ContinualWorldLockError
from aec_bench.ledger.local_lock import exclusive_local_file_lock as exclusive_local_file_lock

__all__ = [
    "ContinualWorldLockConfinementError",
    "ContinualWorldLockError",
    "exclusive_local_file_lock",
]
