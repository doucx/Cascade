from dataclasses import dataclass, field
from typing import Any, List, Dict, Optional
from cascade.spec.constraint import ResourceConstraint
from cascade.spec.policy import ExecutionPolicy, RetryPolicySpec


@dataclass
class Operand:
    pass


@dataclass
class Literal(Operand):
    value: Any


@dataclass
class Register(Operand):
    index: int


@dataclass
class ContextOperand(Operand):
    """Loads a value from the execution context (e.g. user params)."""
    scope: str  # e.g., 'params', 'env'
    key: str


@dataclass
class ResourceOperand(Operand):
    """Loads a resource instance from the resource container."""
    name: str


@dataclass
class Instruction:
    pass


@dataclass
class Call(Instruction):
    output: Register
    args: List[Operand] = field(default_factory=list)
    kwargs: Dict[str, Operand] = field(default_factory=dict)

    # Metadata for observability and constraints
    task_name: str = "unknown"
    constraints: Optional[ResourceConstraint] = None  # Deprecated: prefer policy.resources
    structure_hash: Optional[str] = None
    policy: Optional[ExecutionPolicy] = None


@dataclass
class Jump(Instruction):
    """Unconditionally jumps execution by a relative offset."""

    offset: int


@dataclass
class JumpIfFalse(Instruction):
    """Jumps execution by a relative offset if the condition register is False."""

    condition: Register
    offset: int


@dataclass
class MapCall(Instruction):
    """Represents a map operation over iterable inputs."""

    output: Register
    args: List[Operand] = field(default_factory=list)
    kwargs: Dict[str, Operand] = field(default_factory=dict)

    # Metadata for observability and constraints
    task_name: str = "unknown"
    constraints: Optional[ResourceConstraint] = None
    structure_hash: Optional[str] = None
    policy: Optional[ExecutionPolicy] = None


@dataclass
class TailCall:
    args: List[Any] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    target_blueprint_id: Optional[str] = None  # For mutual recursion in future


@dataclass
class Blueprint:
    instructions: List[Instruction] = field(default_factory=list)
    register_count: int = 0

    # Maps input argument positions to Register indices.
    # Used by the VM to populate the initial frame or refill it on TailCall.
    input_args: List[int] = field(default_factory=list)
    input_kwargs: Dict[str, int] = field(default_factory=dict)
