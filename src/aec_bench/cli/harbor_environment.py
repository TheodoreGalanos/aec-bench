# ABOUTME: Selects concrete custom Harbor environments at the CLI composition boundary.
# ABOUTME: Keeps provider selection outside the provider-neutral harness.

from __future__ import annotations

from aec_bench.contracts.execution_environment import HarborEnvironmentBinding
from aec_bench.harness.harbor_dispatch import HARBOR_NATIVE_BACKENDS

MORPH_BACKEND = "morph"
HARBOR_RUN_BACKENDS = (*HARBOR_NATIVE_BACKENDS, MORPH_BACKEND)


def resolve_harbor_environment_binding(backend: str) -> HarborEnvironmentBinding | None:
    """Return the selected custom environment, or None for a Harbor-native backend."""
    if backend != MORPH_BACKEND:
        return None
    from aec_bench.providers.morph_harbor import MORPH_HARBOR_ENVIRONMENT_BINDING

    return MORPH_HARBOR_ENVIRONMENT_BINDING
