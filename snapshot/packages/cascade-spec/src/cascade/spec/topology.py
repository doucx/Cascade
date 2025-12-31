from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class PhysicsFuncNode:
    """
    Represents a computational instance in the physical bipartite graph.
    This is the "Verb" or the transformer.
    """
    current_node_instance_hash: str
    name: str
    # Map input argument names to the source DataNode hash
    inputs: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PhysicsDataNode:
    """
    Represents a data storage slot in the physical bipartite graph.
    This is the "Noun" or the container. It tracks its origin.
    """
    current_data_slot_hash: str
    name: str
    producer_node_instance_hash: str


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


@dataclass(frozen=True)
class BipartiteGraph:
    """
    The static, physical blueprint of the computation network, output by the compiler.
    """
    func_nodes: Dict[str, PhysicsFuncNode]
    data_nodes: Dict[str, PhysicsDataNode]
    channels: List[ChannelDef]