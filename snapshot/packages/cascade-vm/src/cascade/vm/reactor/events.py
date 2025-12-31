from dataclasses import dataclass, field
from typing import Dict, Any
from cascade.spec.physics import DataNode, FuncNode, Token


@dataclass
class ReactorEvent:
    """Base class for all reactor events."""
    pass


@dataclass
class TokenGenerated(ReactorEvent):
    """
    Event emitted when a Token is destined for a DataNode.
    Handler should put the token into the node.
    """
    node: DataNode
    token: Token


@dataclass
class ExecutionFinished(ReactorEvent):
    """
    Event emitted when an Executor finishes a job.
    Handler should route outputs to downstream DataNodes.
    """
    node: FuncNode
    outputs: Dict[str, Token] = field(default_factory=dict)
    error: Any = None