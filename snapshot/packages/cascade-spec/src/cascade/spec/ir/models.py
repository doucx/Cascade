from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from cascade.spec.fingerprint import Fingerprint


class ArgumentKind(str, Enum):
    """
    Defines the kind of an argument, aligning with Python's inspect.Parameter kinds
    and the Stitcher specification.
    """

    POSITIONAL_ONLY = "POSITIONAL_ONLY"
    POSITIONAL_OR_KEYWORD = "POSITIONAL_OR_KEYWORD"
    VAR_POSITIONAL = "VAR_POSITIONAL"  # *args
    KEYWORD_ONLY = "KEYWORD_ONLY"
    VAR_KEYWORD = "VAR_KEYWORD"  # **kwargs


@dataclass(frozen=True)
class ArgumentDef:
    """
    A specific definition of a single argument in a task's signature.
    Designed to be serializable.
    """

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
    # Must contain keys like 'current_code_structure_hash'.
    fingerprint: Fingerprint
    return_annotation: Optional[str] = None
    docstring: Optional[str] = None
    is_async: bool = False
    # Execution mode (e.g. "blocking", "compute") derived from the task definition
    mode: str = "blocking"
