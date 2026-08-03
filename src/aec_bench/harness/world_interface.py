# ABOUTME: Preserves the public harness import path for continual-world actor calls.
# ABOUTME: Re-exports the canonical session protocol and validation from its runtime owner.

from aec_bench.contracts.world_interface import WorldInterfaceError
from aec_bench.task_world_templates.continual.actor_session import (
    ActorWorldSession,
    invoke_world_actor,
    observe_world_actor,
)

__all__ = (
    "ActorWorldSession",
    "WorldInterfaceError",
    "invoke_world_actor",
    "observe_world_actor",
)
