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
        target_arg="arg_val",
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
    channel_from_a = next(
        (c for c in topology.channels if c.source_node_instance_hash == "A"), None
    )
    assert channel_from_a is not None, "Node A must have an output channel"

    # Verify it targets a valid DataNode
    data_slot_id = channel_from_a.target_data_slot_hash
    assert data_slot_id in topology.data_nodes

    data_node = topology.data_nodes[data_slot_id]
    assert data_node.producer_node_instance_hash == "A"


def test_compile_literal_values_to_data_nodes():
    """
    Test Case: A(x=1, y="hello")

    Verifies that literal arguments in GraphIR are compiled into:
    1. Pre-created PhysicsDataNodes (Constant Slots).
    2. Channels connecting these Constant Slots to Node A.
    3. The literal values are stored in the BipartiteGraph's initial_values.
    """
    # 1. Setup IR
    node_a = _create_dummy_node_ir("A")
    # A has two literal inputs in kwargs
    node_a.kwargs = {"x": 1, "y": "hello"}

    graph_ir = GraphIR(nodes=[node_a], edges=[])

    # 2. Execute Backend
    topology = Backend.compile(graph_ir)

    # 3. Assertions
    # A should have 2 input channels (for x and y)
    channels_to_a = [
        c for c in topology.channels if c.target_data_slot_hash is None
    ]  # Wait, channel is Source -> Target
    # Input wiring is stored in PhysicsFuncNode.inputs map (DataNodeHash -> PortName relation is implicit?)
    # Re-reading our spec impl: PhysicsFuncNode.inputs: Dict[str, str] (ArgName -> DataHash)

    func_node_a = topology.func_nodes["A"]
    assert "x" in func_node_a.inputs
    assert "y" in func_node_a.inputs

    data_hash_x = func_node_a.inputs["x"]
    data_hash_y = func_node_a.inputs["y"]

    # Verify DataNodes exist
    assert data_hash_x in topology.data_nodes
    assert data_hash_y in topology.data_nodes

    # Verify they are marked as Constants (no producer)
    # The convention for constants is producer_node_instance_hash being empty or special
    assert topology.data_nodes[data_hash_x].producer_node_instance_hash == "const"
    assert topology.data_nodes[data_hash_y].producer_node_instance_hash == "const"

    # Verify Values are captured
    # We expect BipartiteGraph to have an 'initial_values' map
    assert hasattr(topology, "initial_values"), (
        "BipartiteGraph must hold initial values for constants"
    )
    assert topology.initial_values[data_hash_x] == 1
    assert topology.initial_values[data_hash_y] == "hello"


def test_compile_diamond_dependency_fan_out():
    """
    Test Case: Diamond (Fan-Out)
      A
     / \
    B   C
    
    Verifies that B and C consume the SAME DataNode produced by A.
    """
    # 1. Setup IR
    node_a = _create_dummy_node_ir("A")
    node_b = _create_dummy_node_ir("B")
    node_c = _create_dummy_node_ir("C")

    # Edges: A->B, A->C
    edge_ab = EdgeIR(
        source_node_instance_hash="A", target_node_instance_hash="B", target_arg="dep_b"
    )
    edge_ac = EdgeIR(
        source_node_instance_hash="A", target_node_instance_hash="C", target_arg="dep_c"
    )

    graph_ir = GraphIR(nodes=[node_a, node_b, node_c], edges=[edge_ab, edge_ac])

    # 2. Execute Backend
    topology = Backend.compile(graph_ir)

    # 3. Assertions
    func_b = topology.func_nodes["B"]
    func_c = topology.func_nodes["C"]

    # Get the input DataNode hash for both
    input_hash_b = func_b.inputs["dep_b"]
    input_hash_c = func_c.inputs["dep_c"]

    # Critical: They MUST be the same DataNode (Structural Sharing)
    assert input_hash_b == input_hash_c, "Fan-out should reuse the same source DataNode"

    # Verify that DataNode is produced by A
    data_node = topology.data_nodes[input_hash_b]
    assert data_node.producer_node_instance_hash == "A"


def test_compile_injects_lifecycle_emitters():
    """
    Verifies that the Backend correctly injects the result and termination
    emitters, and connects them with a SIGNAL channel.
    """
    # 1. Setup minimal IR with a single root node
    node_a = _create_dummy_node_ir("A")
    graph_ir = GraphIR(nodes=[node_a], edges=[])

    # 2. Compile
    topology = Backend.compile(graph_ir)

    # 3. Find Emitter Nodes by their unique sink_id
    result_emitter = next(
        (n for n in topology.func_nodes.values() if n.sink_id == "main_output"), None
    )
    term_emitter = next(
        (
            n
            for n in topology.func_nodes.values()
            if n.sink_id == "__system_lifecycle_signal"
        ),
        None,
    )

    # 4. Assertions for Emitter Nodes existence and properties
    assert result_emitter is not None, "Result emitter node was not injected"
    assert term_emitter is not None, "Termination emitter node was not injected"
    assert result_emitter.name == "result_emitter"
    assert term_emitter.name == "term_emitter"

    # 5. Assert that Result Emitter is connected to the graph's output
    # Find the output data slot of the original root node 'A'
    output_of_a_hash = next(
        c.target_data_slot_hash
        for c in topology.channels
        if c.source_node_instance_hash == "A" and c.kind == ChannelKind.DATA
    )
    assert (
        "result" in result_emitter.inputs
    ), "Result emitter must have a 'result' input"
    assert result_emitter.inputs["result"] == output_of_a_hash

    # 6. Assert that a SIGNAL channel connects the two emitters
    signal_channel = next(
        (
            c
            for c in topology.channels
            if c.source_node_instance_hash == result_emitter.current_node_instance_hash
            and c.kind == ChannelKind.SIGNAL
        ),
        None,
    )

    assert signal_channel is not None, "SIGNAL channel between emitters not found"
    assert signal_channel.kind == ChannelKind.SIGNAL
    assert (
        signal_channel.port_name == "result"
    ), "Emitters should signal from their default 'result' output port"

    # 7. Assert that the Termination Emitter receives the signal
    assert (
        "signal" in term_emitter.inputs
    ), "Termination emitter must have a 'signal' input"
    assert signal_channel.target_data_slot_hash == term_emitter.inputs["signal"]

    # 8. Verify the signal's DataNode exists and is correctly produced
    signal_data_node = topology.data_nodes.get(signal_channel.target_data_slot_hash)
    assert signal_data_node is not None, "DataNode for signal channel is missing"
    assert (
        signal_data_node.producer_node_instance_hash
        == result_emitter.current_node_instance_hash
    )
