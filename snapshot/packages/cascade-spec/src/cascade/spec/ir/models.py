from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any

from cascade.spec.fingerprint import Fingerprint


class ArgumentKind(str, Enum):
    """Defines the kind of an argument, aligning with Python's inspect.Parameter kinds."""

    POSITIONAL_ONLY = "POSITIONAL_ONLY"
    POSITIONAL_OR_KEYWORD = "POSITIONAL_OR_KEYWORD"
    VAR_POSITIONAL = "VAR_POSITIONAL"  # *args
    KEYWORD_ONLY = "KEYWORD_ONLY"
    VAR_KEYWORD = "VAR_KEYWORD"  # **kwargs


@dataclass(frozen=True)
class ArgumentDef:
    """A specific definition of a single argument in a task's signature."""

    name: str
    kind: ArgumentKind
    annotation: Optional[str] = None
    default_value_repr: Optional[str] = None


@dataclass(frozen=True)
class TaskDef:
    """
    The static intermediate representation (IR) of a Task.
    This separates the 'definition' of what a task is from the 'node'
    of where it is used in a graph.
    """

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
    """
    Intermediate Representation of a Task instantiation in the logical graph.
    This is the input to the Compiler Backend.
    """

    id: str
    """Unique identifier for this node instance (e.g. current_instance_hash)."""

    name: str
    """Human-readable name."""

    task: TaskDef
    """The definition of the task being invoked."""

    inputs: Dict[str, Any] = field(default_factory=dict)
    """Mapping of argument names to values. 
    Values can be literals or references to other NodeIR IDs."""

    constraints: Dict[str, Any] = field(default_factory=dict)
    """Resource constraints for this node (e.g. {'gpu': 1})."""


@dataclass(frozen=True)
class GraphIR:
    """A collection of NodeIRs representing the full logical workflow."""

    nodes: List[NodeIR] = field(default_factory=list)