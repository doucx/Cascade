from dataclasses import dataclass, field
from typing import Any, List, Dict, Union

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

@dataclass
class Blueprint:
    """
    Represents a compiled workflow, ready for execution by the VM.
    """
    instructions: List[Instruction] = field(default_factory=list)
    register_count: int = 0