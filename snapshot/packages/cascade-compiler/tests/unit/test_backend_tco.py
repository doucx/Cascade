from typing import List

from cascade.spec.ir.models import (
    GraphIR,
    NodeIR,
    EdgeIR,
    EdgeKind,
    TaskDef,
    ArgumentDef,
    ArgumentKind,
)
from cascade.spec.fingerprint import Fingerprint
from cascade.compiler.backend import Backend
from cascade.spec.topology import BipartiteGraph


def _create_dummy_node(node_id: str, arg_names: List[str] = None) -> NodeIR:
    """Helper to create a minimal NodeIR for TCO tests."""
    args = []
    if arg_names:
        for name in arg_names:
            args.append(ArgumentDef(name=name, kind=ArgumentKind.POSITIONAL_OR_KEYWORD))

    task_def = TaskDef(
        name=node_id,
        args=args,
        canonical_code_structure_hash=f"canonical_code_structure_hash_{node_id}",
    )
    # We use the node_id as the instance hash for clarity in tests
    return NodeIR(current_node_instance_hash=node_id, definition=task_def)


def test_compile_self_recursive_loop_to_feedback_channel():
    """
    Test Case: Self-Recursion (The basic TCO loop)

    IR Structure:
      Node: counter(n)
      Edge: counter -> counter (arg='n') [Kind=JUMP, Case='loop']

    Expected Topology:
      FuncNode(counter)
      Channel:
        Source: FuncNode(counter)
        Target: DataNode(counter.n)  <-- The input slot of the SAME node
        TagFilter: "loop"
    """
    # 1. Setup IR
    # Node 'counter' takes one argument 'n'
    node = _create_dummy_node("counter", arg_names=["n"])

    # Edge representing the recursive jump: counter -> counter
    # This edge carries the 'loop' case key
    # NOTE: This assumes EdgeKind.JUMP and case_key exist (TDD RED)
    edge = EdgeIR(
        source_node_instance_hash="counter",
        target_node_instance_hash="counter",
        target_arg="n",
        kind=EdgeKind.JUMP,
        case_key="loop",
    )

    graph_ir = GraphIR(nodes=[node], edges=[edge])

    # 2. Execute Backend
    topology = Backend.compile(graph_ir)

    # 3. Assertions
    assert isinstance(topology, BipartiteGraph)

    # Verify FuncNode exists
    assert "counter" in topology.func_nodes
    func_node = topology.func_nodes["counter"]

    # Verify Input Slot (DataNode) for 'n' exists
    # The compiler should have created a DataNode for the input 'n'
    assert "n" in func_node.inputs
    current_input_slot_hash = func_node.inputs["n"]
    assert current_input_slot_hash in topology.data_nodes

    # Verify Feedback Channel
    # We look for a channel that:
    # - originates from 'counter'
    # - targets the input slot of 'counter' (current_input_slot_hash)
    # - has tag_filter="loop"

    feedback_channel = next(
        (
            c
            for c in topology.channels
            if c.source_node_instance_hash == "counter"
            and c.target_data_slot_hash == current_input_slot_hash
            and c.tag_filter == "loop"
        ),
        None,
    )

    assert feedback_channel is not None, "Feedback channel for self-recursion not found"


def test_compile_conditional_routing():
    """
    Test Case: Branching (Router logic)

    IR Structure:
      Node A (The Decision Maker)
      Node B (Branch 1)
      Node C (Branch 2)

      Edge 1: A -> B [Kind=JUMP, Case='case_b']
      Edge 2: A -> C [Kind=JUMP, Case='case_c']

    Expected Topology:
      FuncNode A has TWO output channels.
      Channel 1: A -> DataNode(B.input), Filter='case_b'
      Channel 2: A -> DataNode(C.input), Filter='case_c'
    """
    node_a = _create_dummy_node("A")
    node_b = _create_dummy_node("B", arg_names=["val"])
    node_c = _create_dummy_node("C", arg_names=["val"])

    edge_b = EdgeIR(
        source_node_instance_hash="A",
        target_node_instance_hash="B",
        target_arg="val",
        kind=EdgeKind.JUMP,
        case_key="case_b",
    )
    edge_c = EdgeIR(
        source_node_instance_hash="A",
        target_node_instance_hash="C",
        target_arg="val",
        kind=EdgeKind.JUMP,
        case_key="case_c",
    )

    graph_ir = GraphIR(nodes=[node_a, node_b, node_c], edges=[edge_b, edge_c])

    topology = Backend.compile(graph_ir)

    # Verify Channels
    # Helper to find channel by filter
    def find_channel(tag):
        return next(
            (
                c
                for c in topology.channels
                if c.source_node_instance_hash == "A" and c.tag_filter == tag
            ),
            None,
        )

    chan_b = find_channel("case_b")
    chan_c = find_channel("case_c")

    assert chan_b is not None
    assert chan_c is not None

    # Verify targets
    # chan_b should point to B's input
    current_b_input_slot_hash = topology.func_nodes["B"].inputs["val"]
    assert chan_b.target_data_slot_hash == current_b_input_slot_hash

    # chan_c should point to C's input
    current_c_input_slot_hash = topology.func_nodes["C"].inputs["val"]
    assert chan_c.target_data_slot_hash == current_c_input_slot_hash


def test_compile_mutual_recursion():
    """
    Test Case: Mutual Recursion (Ping-Pong)

    IR Structure:
      Ping -> Pong [Kind=JUMP, Case='ping']
      Pong -> Ping [Kind=JUMP, Case='pong']

    Expected Topology:
      Two crossed channels forming a figure-8 loop.
    """
    ping = _create_dummy_node("Ping", arg_names=["x"])
    pong = _create_dummy_node("Pong", arg_names=["y"])

    edge_to_pong = EdgeIR(
        source_node_instance_hash="Ping",
        target_node_instance_hash="Pong",
        target_arg="y",
        kind=EdgeKind.JUMP,
        case_key="ping",
    )
    edge_to_ping = EdgeIR(
        source_node_instance_hash="Pong",
        target_node_instance_hash="Ping",
        target_arg="x",
        kind=EdgeKind.JUMP,
        case_key="pong",
    )

    graph_ir = GraphIR(nodes=[ping, pong], edges=[edge_to_pong, edge_to_ping])

    topology = Backend.compile(graph_ir)

    # Verify Channel Ping -> Pong
    # Note: We must filter by tag because there is also a default output channel
    c1 = next(
        (
            c
            for c in topology.channels
            if c.source_node_instance_hash == "Ping" and c.tag_filter == "ping"
        ),
        None,
    )
    assert c1 is not None, "Channel Ping->Pong with tag 'ping' not found"
    assert c1.target_data_slot_hash == topology.func_nodes["Pong"].inputs["y"]

    # Verify Channel Pong -> Ping
    c2 = next(
        (
            c
            for c in topology.channels
            if c.source_node_instance_hash == "Pong" and c.tag_filter == "pong"
        ),
        None,
    )
    assert c2 is not None, "Channel Pong->Ping with tag 'pong' not found"
    assert c2.target_data_slot_hash == topology.func_nodes["Ping"].inputs["x"]
