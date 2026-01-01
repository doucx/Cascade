Of course. As per the TDD workflow, we will now create the test to verify the changes made in the previous step. This ensures the `Backend` correctly implements the contract for lifecycle injection before we proceed to build the `VMExecutionStrategy` that relies on it.

I will add a new test case to `test_backend_topology.py` that specifically validates the injection of the `result_emitter` and `term_emitter`, and the `SIGNAL` channel that connects them.

## [WIP] test(compiler): verify lifecycle emitter injection in Backend

### 评论
This is a crucial validation step. By writing this test, we codify the contract that the `Backend` must fulfill for the `VMExecutionStrategy`. It ensures that the compiler produces a `BipartiteGraph` with the precise, predictable structure needed for decoupled lifecycle management, preventing potential integration errors as we move to the next phase.

### 目标
1.  Add a new unit test named `test_compile_injects_lifecycle_emitters` to the `packages/cascade-compiler/tests/unit/test_backend_topology.py` file.
2.  The test will compile a minimal `GraphIR` (a single node).
3.  It will assert that the resulting `BipartiteGraph` contains the `result_emitter` and `term_emitter` `FuncNode`s with their correct `sink_id`s.
4.  It will assert that a `ChannelDef` of `kind=SIGNAL` correctly connects the output of the result emitter to the input of the termination emitter.

### 基本原理
Following the Test-Driven Development (TDD) process, we are now in the "write a test" phase for our new feature. The previous plan implemented the logic, and this plan validates it in isolation.

I will use a `patch_file` operation to append the new test case to the existing test module. The test will perform a "find-then-assert" strategy: since the hashes of the injected nodes are generated internally, the test will locate them in the compiled graph by their unique `sink_id` and then verify their connections and properties.

### 标签
#intent/tooling #flow/ready #priority/high
#comp/compiler #comp/tests #concept/executor
#scope/core
#ai/instruct
#task/domain/compiler #task/object/backend #task/action/test
#task/state/continue

---

### Script

#### Acts 1: Add Unit Test for Lifecycle Emitter Injection

I will now patch `test_backend_topology.py` to include the new validation test.

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_backend_topology.py
~~~~~
~~~~~python.old
    # Critical: They MUST be the same DataNode (Structural Sharing)
    assert input_hash_b == input_hash_c, "Fan-out should reuse the same source DataNode"

    # Verify that DataNode is produced by A
    data_node = topology.data_nodes[input_hash_b]
    assert data_node.producer_node_instance_hash == "A"
~~~~~
~~~~~python.new
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
~~~~~
