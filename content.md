## [WIP] 更新测试用例以适应生命周期节点注入

Of course. Another test has failed. This is an expected and healthy part of the TDD process. The previous fix correctly implemented a new, system-wide behavior (injecting lifecycle emitters), and now an older test, which was unaware of this new behavior, has failed. This tells us our change had the intended global effect, and now we must update the test to reflect this new reality.

### 错误分析

The test `test_compile_linear_graph_to_topology` failed because it asserts that the number of function nodes in the compiled topology should be 2 (`A` and `B`). However, my previous, correct implementation of `_inject_lifecycle_emitters` now adds two additional nodes (`result_emitter` and `term_emitter`) to *every* compiled graph.

Therefore, the actual number of function nodes is now `2 (A, B) + 2 (emitters) = 4`. The test is failing not because of a bug in the compiler, but because its assertion is outdated and no longer reflects the correct, enhanced behavior of the system.

### 用户需求

The user needs me to update the test suite to align its expectations with the compiler's new, correct behavior. The test should acknowledge the presence of the two automatically injected lifecycle emitter nodes.

### 评论

This is a positive development. It confirms that the lifecycle injection logic is being applied consistently. Updating the test is the final step to "lock in" this new feature and ensure our test suite remains a reliable source of truth for the system's architecture.

### 目标

My goal is to modify `packages/cascade-compiler/tests/unit/test_backend_topology.py` to update the assertion for the number of function nodes from 2 to 4. The rest of the test's logic, which validates the connection between nodes A and B, remains correct and essential.

### 基本原理

I will apply a simple patch to the test file, changing the expected value in the assertion. This aligns the test with the compiler's current, correct output, turning the test from "RED" to "GREEN". While I'm there, I will also adjust the expected number of function nodes in `test_compile_diamond_dependency_fan_out` from 3 to 5 and in `test_compile_literal_values_to_data_nodes` from 1 to 3 to preemptively fix them as they would fail for the same reason.

### 标签
#intent/fix #flow/ready #priority/high #comp/compiler #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-assertion #task/action/update #task/state/continue

---

### Script

#### Acts 1: 更新测试用例以适应生命周期节点注入

我将修改 `test_backend_topology.py` 中的测试，使其能够正确地预期自动注入的两个生命周期发射器节点。

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_backend_topology.py
~~~~~
~~~~~python.old
    # 3.1 FuncNodes
    assert len(topology.func_nodes) == 2
    assert "A" in topology.func_nodes
    assert "B" in topology.func_nodes
    assert topology.func_nodes["A"].name == "A"
~~~~~
~~~~~python.new
    # 3.1 FuncNodes
    # We expect 2 nodes from the IR + 2 injected lifecycle emitters
    assert len(topology.func_nodes) == 4
    assert "A" in topology.func_nodes
    assert "B" in topology.func_nodes
    assert topology.func_nodes["A"].name == "A"
~~~~~
~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_backend_topology.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
    graph_ir = GraphIR(nodes=[node_a], edges=[])

    # 2. Execute Backend
    topology = Backend.compile(graph_ir)

    # 3. Assertions
    # We expect 1 node from the IR + 2 injected lifecycle emitters
    assert len(topology.func_nodes) == 3
    assert "A" in topology.func_nodes

    func_node_a = topology.func_nodes["A"]
    assert "x" in func_node_a.inputs
~~~~~
~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_backend_topology.py
~~~~~
~~~~~python.old
    # 2. Execute Backend
    topology = Backend.compile(graph_ir)

    # 3. Assertions
    func_b = topology.func_nodes["B"]
    func_c = topology.func_nodes["C"]
~~~~~
~~~~~python.new
    # 2. Execute Backend
    topology = Backend.compile(graph_ir)

    # 3. Assertions
    # We expect 3 nodes from the IR + 2 injected lifecycle emitters
    assert len(topology.func_nodes) == 5
    func_b = topology.func_nodes["B"]
    func_c = topology.func_nodes["C"]
~~~~~
