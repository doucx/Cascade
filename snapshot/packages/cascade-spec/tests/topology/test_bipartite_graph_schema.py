import pytest
from dataclasses import is_dataclass

# This import is expected to fail initially (RED state)
# We are defining the contract for the new topology module.
from cascade.spec.topology import (
    BipartiteGraph,
    ChannelDef,
    PhysicsFuncNode,
    PhysicsDataNode
)


def test_channel_def_schema_adheres_to_symbol_table():
    """
    Validates that ChannelDef adheres to the 'Hash Naming Axiom' and 'Phase 3 Symbol Table'.
    
    A ChannelDef represents a directed edge in the bipartite graph, connecting
    a specific output port of a Function Node to a Data Node (slot).
    
    It must NOT use vague names like 'source_id' or 'target_id'.
    """
    channel = ChannelDef(
        source_node_instance_hash="func_inst_123",
        target_data_slot_hash="data_slot_456",
        port_name="result",
        tag_filter="default"
    )
    
    assert is_dataclass(channel)
    assert channel.source_node_instance_hash == "func_inst_123"
    assert channel.target_data_slot_hash == "data_slot_456"
    assert channel.port_name == "result"
    assert channel.tag_filter == "default"


def test_physics_nodes_schema():
    """
    Validates the schema for the nodes in the bipartite graph.
    """
    # PhysicsFuncNode: Represents a computation instance (The "Verb")
    f_node = PhysicsFuncNode(
        current_node_instance_hash="func_inst_abc",
        name="calculate_metrics"
    )
    assert is_dataclass(f_node)
    assert f_node.current_node_instance_hash == "func_inst_abc"
    assert f_node.name == "calculate_metrics"

    # PhysicsDataNode: Represents a storage slot (The "Noun")
    # It must track who produced it for lineage.
    d_node = PhysicsDataNode(
        current_data_slot_hash="slot_xyz",
        name="metrics_output",
        producer_node_instance_hash="func_inst_abc"
    )
    assert is_dataclass(d_node)
    assert d_node.current_data_slot_hash == "slot_xyz"
    assert d_node.producer_node_instance_hash == "func_inst_abc"


def test_bipartite_graph_container_structure():
    """
    Validates the top-level container structure.
    It should provide indexed access to nodes and a list of channels.
    """
    graph = BipartiteGraph(
        func_nodes={},
        data_nodes={},
        channels=[]
    )
    
    assert is_dataclass(graph)
    # Must be typed as Dict[str, PhysicsFuncNode]
    assert isinstance(graph.func_nodes, dict)
    # Must be typed as Dict[str, PhysicsDataNode]
    assert isinstance(graph.data_nodes, dict)
    # Must be typed as List[ChannelDef]
    assert isinstance(graph.channels, list)