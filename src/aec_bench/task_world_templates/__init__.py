# ABOUTME: Composite task-world template catalogue and materialisation helpers.
# ABOUTME: Exposes composite AEC templates through existing task-world contracts.

from aec_bench.task_world_templates.catalogue import get_template, list_templates
from aec_bench.task_world_templates.contracts import CompositeTaskWorldTemplate

__all__ = ["CompositeTaskWorldTemplate", "get_template", "list_templates"]
