import asyncio
from typing import Any, Dict, Optional

from .spec.task import task
from .spec.lazy_types import LazyResult  # NEW
from .spec.common import Param
from .spec.routing import Router
from .spec.resource import resource, inject
from .runtime.engine import Engine
from .runtime.bus import MessageBus
from .runtime.subscribers import HumanReadableLogSubscriber
from .testing import override_resource
from .tools.preview import dry_run
from .tools.visualize import visualize
from .tools.cli import cli
from .graph.serialize import to_json, from_json
from .spec.constraint import with_constraints
from .runtime.exceptions import DependencyMissingError

# Note: 'shell' is removed from static imports to support dynamic provider loading
__all__ = [
    "task",
    "Param",
    "run",
    "dry_run",
    "visualize",
    "cli",
    "to_json",
    "from_json",
    "with_constraints",
    "LazyResult",
    "Router",
    "resource",
    "inject",
    "Engine",
    "override_resource",
    "DependencyMissingError",
]


def __getattr__(name: str) -> Any:
    """
    Dynamic attribute access to support plugin providers.
    E.g., accessing `cascade.shell` will look up the 'shell' provider.
    """
    from .providers import registry

    try:
        return registry.get(name)
    except AttributeError:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


from .messaging.bus import bus as messaging_bus
from .messaging.renderer import CliRenderer

def run(
    target: LazyResult,
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
    log_level: str = "INFO",
) -> Any:
    """
    Runs a Cascade workflow with a default engine configuration.

    Args:
        target: The workflow target.
        params: Runtime parameters.
        system_resources: A dictionary defining total system capacity
                          (e.g. {"gpu": 1, "threads": 4}).
        log_level: Minimum logging level ("DEBUG", "INFO", "WARNING", "ERROR").
                   Defaults to "INFO".
    """
    # 1. Setup the messaging renderer
    renderer = CliRenderer(store=messaging_bus.store, min_level=log_level)
    messaging_bus.set_renderer(renderer)
    
    # 2. Setup the event system
    event_bus = MessageBus()
    # Attach the translator
    HumanReadableLogSubscriber(event_bus)

    engine = Engine(bus=event_bus, system_resources=system_resources)

    return asyncio.run(engine.run(target, params=params))
