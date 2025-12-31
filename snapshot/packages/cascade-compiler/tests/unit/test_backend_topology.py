import pytest
from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, TaskDef
from cascade.spec.fingerprint import Fingerprint
from cascade.spec.topology import BipartiteGraph, ChannelDef

from cascade.compiler.backend import Backend


def _create_dummy_node_ir(node_id: str) -> NodeIR:
    """Helper to create a minimal NodeIR for testing."""
    # We use the node_id as the structure hash for simplicity in tests
    fp = Fingerprint.from_dict({"current_code_structure_hash": f"hash_for_{node_id}"})
    task_def = TaskDef(name=node_id, args=[], fingerprint=fp)
    return NodeIR(current_node_instance_hash=node_id, definition=task_def)


def test_compile_linear_graph_to_topology():
    """
    Test Case: A -> B
    
    Verifies that the Backend compiles a simple linear dependency into a 
    BipartiteGraph with correct FuncNodes, DataNodes, and Channels.
    """
    # 1. Setup IR
    node_a = _create_dummy_node_ir("A")
    node_b = _create_dummy_node_ir("B")
    
    # Edge: Output of A maps to input 'arg_val' of B
    edge = EdgeIR(
        source_node_instance_hash="A", 
        target_node_instance_hash="B", 
        target_arg="arg_val"
    )
    
    graph_ir = GraphIR(nodes=[node_a, node_b], edges=[edge])

    # 2. Execute Backend
    # Note: We intentionally drop the 'plan' argument. 
    # The BipartiteGraph is a static structure; it doesn't need a linear schedule.
    topology = Backend.compile(graph_ir)

    # 3. Assertions on Structure
    assert isinstance(topology, BipartiteGraph), "Backend must return a BipartiteGraph"
    
    # 3.1 FuncNodes
    assert len(topology.func_nodes) == 2
    assert "A" in topology.func_nodes
    assert "B" in topology.func_nodes
    assert topology.func_nodes["A"].name == "A"
    
    # 3.2 DataNodes
    # In this model, every FuncNode output becomes a DataNode (slot).
    # A produces an output (let's assume default port "result" or similar).
    # B produces an output.
    # The edge A->B implies A writes to a DataNode that B reads from.
    
    # We expect at least one DataNode for A's output
    # The naming convention for data slots is implementation detail of the backend,
    # but we can look it up via the channels.
    
    # 3.3 Channels
    # There should be a channel from A -> DataNode -> B (input side wiring is implicit in FuncNode inputs? 
    # Or explicitly modeled? 
    # In 'spec.topology', ChannelDef is Output Port -> DataNode.
    # Input wiring is defined where? 
    # Re-reading spec: "ChannelDef: source_node_instance_hash, target_data_slot_hash"
    # This defines F -> D.
    # The D -> F connection is implicit in the FuncNode's input configuration?
    # Wait, PhysicsFuncNode needs to know its inputs.
    # But PhysicsFuncNode dataclass currently only has (hash, name).
    # We might need to expand PhysicsFuncNode to include input/output port definitions 
    # to fully describe the graph, OR the BipartiteGraph object should hold the edges D->F too.
    
    # For this phase (Backend Output), let's focus on the Output Channels (F->D) 
    # and ensure the DataNodes exist.
    
    assert len(topology.channels) > 0
    
    # Find channel originating from A
    channel_from_a = next((c for c in topology.channels if c.source_node_instance_hash == "A"), None)
    assert channel_from_a is not None, "Node A must have an output channel"
    
    # Verify it targets a valid DataNode
    data_slot_id = channel_from_a.target_data_slot_hash
    assert data_slot_id in topology.data_nodes
    
    data_node = topology.data_nodes[data_slot_id]
    assert data_node.producer_node_instance_hash == "A"