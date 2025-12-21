from dataclasses import dataclass, field
from typing import Any, List, Dict, Optional
from cascade.spec.constraint import ResourceConstraint

@dataclass
class Operand:
    """Base class for instruction operands."""
    pass

@dataclass
class Literal(Operand):
    """Represents a static value known at compile time."""
    value: Any

@dataclass
class Register(Operand):
    """Represents a dynamic value stored in a virtual register."""
    index: int

@dataclass
class Instruction:
    """Base class for VM instructions."""
    pass

@dataclass
class Call(Instruction):
    """
    Instruction to call a callable (function/task).
    Results are stored in the 'output' register.
    """
    func: Any
    output: Register
    args: List[Operand] = field(default_factory=list)
    kwargs: Dict[str, Operand] = field(default_factory=dict)
    
    # Metadata for observability and constraints
    task_name: str = "unknown"
    constraints: Optional[ResourceConstraint] = None

@dataclass
class TailCall:
    """
    A special return value indicating a request for tail-recursive execution.
    The VM intercepts this object and restarts execution with the new arguments.
    """
    args: List[Any] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    target_blueprint_id: Optional[str] = None  # For mutual recursion in future

@dataclass
class Blueprint:
    """
    Represents a compiled workflow, ready for execution by the VM.
    """
    instructions: List[Instruction] = field(default_factory=list)
    register_count: int = 0
    
    # Maps input argument positions to Register indices.
    # Used by the VM to populate the initial frame or refill it on TailCall.
    input_args: List[int] = field(default_factory=list)
    input_kwargs: Dict[str, int] = field(default_factory=dict)