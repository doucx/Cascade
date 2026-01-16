from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any

from .fingerprint import Fingerprint


class ArgumentKind(str, Enum):
    POSITIONAL_ONLY = "POSITIONAL_ONLY"
    POSITIONAL_OR_KEYWORD = "POSITIONAL_OR_KEYWORD"
    VAR_POSITIONAL = "VAR_POSITIONAL"  # *args
    KEYWORD_ONLY = "KEYWORD_ONLY"
    VAR_KEYWORD = "VAR_KEYWORD"  # **kwargs


@dataclass(frozen=True)
class ArgumentDef:
    name: str
    kind: ArgumentKind
    annotation: Optional[str] = None
    default_value_repr: Optional[str] = None


@dataclass(frozen=True)
class TaskDef:
    name: str
    args: List[ArgumentDef]
    # The stable semantic identity of this task definition.
    # Must contain keys like 'canonical_code_structure_hash'.
    fingerprint: Fingerprint
    return_annotation: Optional[str] = None
    docstring: Optional[str] = None
    is_async: bool = False
    # Execution mode (e.g. "blocking", "compute") derived from the task definition
    mode: str = "blocking"


@dataclass(frozen=True)
class NodeIR:
    current_node_instance_hash: str

    name: str

    task: TaskDef

    # "task" | "map" | "param"
    type: str = "task"

    # The logical UUID from the high-level DSL (LazyResult), if available.
    logical_id: Optional[str] = None

    inputs: Dict[str, Any] = field(default_factory=dict)

    constraints: Dict[str, Any] = field(default_factory=dict)

    # The ID of the node that determines if this node should run
    condition: Optional[str] = None

    # IDs of nodes that must complete before this node starts (Sequence dependency)
    dependencies: List[str] = field(default_factory=list)

    # Configuration for iterative jumps (if any)
    # Format: {"target_key": "target_node_id", ...}
    flow_control: Optional[Dict[str, Any]] = None

    # Metadata for retry policies, caching, etc.
    retry_policy: Optional[Dict[str, Any]] = None
    cache_policy: Optional[Any] = None


@dataclass(frozen=True)
class GraphIR:
    nodes: List[NodeIR] = field(default_factory=list)

    # The logical UUIDs of the LazyResults that were the entry points for generation.
    root_logical_ids: List[str] = field(default_factory=list)
