from typing import Any, Dict, Optional

from .spec.task import task, Param, LazyResult
from .runtime.engine import Engine
from .runtime.bus import MessageBus
from .runtime.subscribers import HumanReadableLogSubscriber

__all__ = ["task", "Param", "run", "LazyResult"]

def run(target: LazyResult, params: Optional[Dict[str, Any]] = None) -> Any:
    """
    Runs a Cascade workflow with a default engine configuration.
    
    This is the primary entry point for users. It sets up a default
    engine with a human-readable logger.
    """
    bus = MessageBus()
    # Attach the default logger
    HumanReadableLogSubscriber(bus)
    
    engine = Engine(bus=bus)
    
    return engine.run(target, params=params)