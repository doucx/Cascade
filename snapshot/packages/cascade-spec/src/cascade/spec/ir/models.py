from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from cascade.spec.fingerprint import Fingerprint


class ArgumentKind(str, Enum):
    """
    Defines the kind of an argument, aligning with Python's inspect.Parameter kinds.
    """

    POSITIONAL_ONLY = "POSITIONAL_ONLY"
    POSITIONAL_OR_KEYWORD = "POSITIONAL_OR_KEYWORD"
    VAR_POSITIONAL = "VAR_POSITIONAL"  # *args
    KEYWORD_ONLY = "KEYWORD_ONLY"
    VAR_KEYWORD = "VAR_KEYWORD"  # **kwargs


@dataclass(frozen=True)
class ArgumentDef:
    """
    A serializable, static definition of a single argument in a task's signature.
    """

    name: str
    kind: ArgumentKind
    annotation: Optional[str] = None
    default_value_repr: Optional[str] = None


@dataclass(frozen=True)
class TaskDef:
    """
    The static intermediate representation (IR) of a Task.
    This separates the 'definition' of what a task is from its usage 'node' in a graph.
    """

    name: str
    args: List[ArgumentDef]
    fingerprint: Fingerprint
    return_annotation: Optional[str] = None
    docstring: Optional[str] = None
    is_async: bool = False
    mode: str = "blocking"


@dataclass(frozen=True)
class NodeIR:
    """
    Represents a single node in the computation graph IR.
    """

    id: str
    definition: TaskDef
    inputs: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EdgeIR:
    """
    Represents a dependency edge between two nodes in the graph IR.
    """

    source_id: str
    target_id: str
    target_arg: str


@dataclass(frozen=True)
class GraphIR:
    """
    Represents the entire computation graph IR.
    """

    nodes: List[NodeIR] = field(default_factory=list)
    edges: List[EdgeIR] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


# --- VM Instruction Set IR ---


@dataclass(frozen=True)
class Instruction:
    """
    Base class for all VM instructions.
    """

    id: str


@dataclass(frozen=True)
class Call(Instruction):
    """

    Represents a function call instruction.
    """

    task_name: str
    args: List[Any]
    output_register: str


@dataclass(frozen=True)
class Return(Instruction):
    """
    Represents a return instruction from a function.
    """

    source_register: str