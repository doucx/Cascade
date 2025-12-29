from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass(kw_only=True)
class Op:
    """
    Base class for Level 1 IR Operations.
    Ops are the executable instructions for the Engine.
    They must be strict, fully resolved, and immutable.
    """
    # The structural hash/fingerprint of this operation.
    # Serves as the primary key for caching and identification.
    id: str

    # Data dependencies: Map[ArgName, UpstreamOpID]
    # Represents the flow of data from upstream ops to this op's arguments.
    inputs: Dict[str, str] = field(default_factory=dict)

    # Control dependencies: List[UpstreamOpID]
    # Represents explicit execution ordering (e.g. "run after X").
    control_deps: List[str] = field(default_factory=list)


@dataclass(kw_only=True)
class ComputeOp(Op):
    """
    Represents a computational task (function execution).
    """
    # Fully qualified name of the callable (e.g. "my_module.my_func")
    callable_ref: str
    
    # Static configuration (timeouts, retry policies, etc.)
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass(kw_only=True)
class ConstantOp(Op):
    """
    Represents a static value.
    Used for literal arguments.
    """
    value: Any


@dataclass(kw_only=True)
class ResourceOp(Op):
    """
    Represents a resource lifecycle action.
    The Engine handles the actual acquisition/release logic.
    """
    resource_name: str
    action: str  # "acquire" or "release"


@dataclass(kw_only=True)
class MultiplexOp(Op):
    """
    Represents a branching decision (Router).
    The 'selector' input determines which branch key to activate.
    """
    # Map[BranchKey, DownstreamOpID]
    # Note: This describes valid forward paths, but actual execution flow
    # is determined by the selector value at runtime.
    branches: Dict[str, str] = field(default_factory=dict)