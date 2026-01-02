from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any

from cascade.spec.fingerprint import Fingerprint


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
    id: str

    name: str

    task: TaskDef

    inputs: Dict[str, Any] = field(default_factory=dict)

    constraints: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphIR:
    nodes: List[NodeIR] = field(default_factory=list)
