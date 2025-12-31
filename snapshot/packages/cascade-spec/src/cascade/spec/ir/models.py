from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any

from cascade.spec.fingerprint import Fingerprint


class EdgeKind(str, Enum):
    DATA = "DATA"  # Standard data dependency
    CONTROL = "CONTROL"  # Conditional execution (run_if)


class InputKind(str, Enum):
    """Specifies the kind of input an edge provides to a target node."""
    POSITIONAL = "POSITIONAL"
    KEYWORD = "KEYWORD"


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
    # Must contain keys like 'current_code_structure_hash'.
    fingerprint: Fingerprint
    return_annotation: Optional[str] = None
    docstring: Optional[str] = None
    is_async: bool = False
    # Execution mode (e.g. "blocking", "compute") derived from the task definition
    mode: str = "blocking"


@dataclass
class NodeIR:
    id: str
    definition: TaskDef
    # Static literal inputs are now separated
    literal_args: List[Any] = field(default_factory=list)
    literal_kwargs: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EdgeIR:
    source_id: str
    target_id: str
    kind: EdgeKind = EdgeKind.DATA
    
    # The target argument is now explicitly defined
    target_arg_kind: Optional[InputKind] = None
    target_arg_name: Optional[str] = None
    target_arg_index: Optional[int] = None


@dataclass
class GraphIR:
    nodes: List[NodeIR]
    edges: List[EdgeIR]
    meta: Dict[str, Any] = field(default_factory=dict)


# --- VM Instruction Set ---


@dataclass
class Instruction:
    id: str


@dataclass
class Call(Instruction):
    task_name: str
    args: List[Any]
    output_register: str


@dataclass
class Return(Instruction):
    source_register: str
