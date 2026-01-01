from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class PhysicsFuncNode:
    """
    Represents a computational instance in the physical bipartite graph.
    This is the "Verb" or the transformer.
    """

    current_node_instance_hash: str
    name: str
    code_structure_hash: str  # The stable hash of the function's code definition
    # Map input argument names to the source DataNode hash
    inputs: Dict[str, str] = field(default_factory=dict)
    # If not None, this node acts as an Emitter, pushing its result to the specified sink.
    sink_id: Optional[str] = field(default=None)


@dataclass(frozen=True)
class PhysicsDataNode:
    """
    Represents a data storage slot in the physical bipartite graph.
    This is the "Noun" or the container. It tracks its origin.
    """

    current_data_slot_hash: str
    name: str
    producer_node_instance_hash: str


class ChannelKind(str, Enum):
    """
    Defines the physical nature of a channel, separating data flow from control flow.
    """

    DATA = "DATA"  # Transports a payload. Contributes to 'data potential'.
    SIGNAL = "SIGNAL"  # Transports only an activation signal. Contributes to 'control potential'.


@dataclass(frozen=True)
class ChannelDef:
    """
    Defines a static, directed connection from a FuncNode's output port
    to a DataNode's input slot, with routing logic.
    """

    source_node_instance_hash: str
    target_data_slot_hash: str
    port_name: str
    tag_filter: str = "default"
    kind: ChannelKind = ChannelKind.DATA


@dataclass(frozen=True)
class BipartiteGraph:
    """
    The static, physical blueprint of the computation network, output by the compiler.
    """

    func_nodes: Dict[str, PhysicsFuncNode]
    data_nodes: Dict[str, PhysicsDataNode]
    channels: List[ChannelDef]
    # Map data_slot_hash -> literal value for constant inputs
    initial_values: Dict[str, Any] = field(default_factory=dict)