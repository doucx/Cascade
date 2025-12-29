from dataclasses import dataclass, field
from typing import Callable, Any, Optional, Dict
from .base import Definition


@dataclass
class TaskDef(Definition):
    """
    Represents a computational task definition.
    Corresponds to functions decorated with @cs.task.
    """
    func: Callable[..., Any]
    name: str
    
    # Configuration policies
    # We use dictionaries for now to avoid circular dependencies with legacy specs,
    # but these will be replaced by strict Policy objects in Phase 1.
    retry_policy: Optional[Dict[str, Any]] = None
    cache_policy: Optional[Dict[str, Any]] = None

    # Argument bindings: Map[ArgName, Value]
    # Value can be a literal, or another Definition (representing a dependency).
    bindings: Dict[str, Any] = field(default_factory=dict)
    
    def __repr__(self):
        return f"<TaskDef {self.name}>"


@dataclass
class ServiceDef(Definition):
    """
    Represents a configuration for an external service operation.
    Corresponds to helper functions like cs.sql, cs.http.
    
    It does NOT implement map(). It is purely data.
    """
    service_type: str  # e.g. "sql", "http", "ipfs"
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MapDef(Definition):
    """
    Represents a mapping operation over another definition.
    """
    target_def: Definition
    mapping_kwargs: Dict[str, Any]