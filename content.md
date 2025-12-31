我们现在进入 **Phase 3.3：[TDD] 编译字面量与扇出依赖**。

这是一个 **RED** 步骤。

我将更新 `packages/cascade-compiler/tests/unit/test_backend_topology.py`。
我将添加两个新的测试用例：
1.  `test_compile_literal_values_to_data_nodes`: 验证字面量输入是否被正确编译为预填充的 `PhysicsDataNode`。
2.  `test_compile_diamond_dependency_fan_out`: 验证扇出依赖（菱形图）是否正确复用了上游的 `PhysicsDataNode`，而不是创建重复的节点。

API 定义：
*   **预填充 DataNode**: 我们将在 `PhysicsDataNode` 的元数据或状态中查找字面量值。在当前的 `spec.topology` 中，我们可能需要引入一种机制来表示“初始值”。目前的 `PhysicsDataNode` 是静态定义，并不包含运行时值。这是一个重要的设计决策点。
    *   *决策*: 既然 `BipartiteGraph` 是静态蓝图，字面量值应该被视为该蓝图的一部分。我们可以在 `PhysicsDataNode` 中添加一个 `initial_value` 字段，或者更明确地，引入一种 `LiteralDef`。
    *   *简化*: 为了保持 `spec` 纯粹，我们可以暂时约定：如果一个 `DataNode` 的 `producer_node_instance_hash` 为空（或特定标记），它就是一个常量节点，其值在编译时确定。或者，更直接地，在 `BipartiteGraph` 中添加一个 `literals: Dict[str, Any]` 字段，映射 `data_node_hash -> value`。后者更符合“数据与结构分离”的原则，但在“静态图即程序”的视角下，常量就是图的一部分。
    *   *最终选择*: 我将在测试中假设 `Backend` 会为字面量生成特殊的 `PhysicsDataNode`，并在 `BipartiteGraph` 上增加一个 `initial_values` 字典来存储这些常量。这比修改 `PhysicsDataNode` 更灵活。

## [WIP] test: 定义字面量和扇出依赖的编译行为

### 用户需求
定义编译器如何处理字面量输入和扇出依赖。

### 评论
通过这个测试，我们强制要求编译器不仅处理函数间的连接，还要处理静态数据的注入。同时，扇出测试确保了图的拓扑结构是高效的（复用节点）而不是树状展开的。

### 目标
更新 `packages/cascade-compiler/tests/unit/test_backend_topology.py`。

### 基本原理
1.  **字面量**: `compile` 的结果应该包含字面量值。我们将在 `BipartiteGraph` 上断言一个新的属性 `initial_values` 的存在。
2.  **扇出**: 构造 A -> (B, C) -> D。断言 B 和 C 的输入都指向 A 的同一个输出 `DataNode` 哈希。

### 标签
#intent/architect #flow/ready #priority/high #comp/compiler #concept/topology #scope/core #ai/instruct #task/domain/compiler #task/object/backend #task/action/test #task/state/continue

---

### Script

#### Acts 1: 更新测试文件以包含字面量和扇出测试

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_backend_topology.py
~~~~~
~~~~~python.old
    
    data_node = topology.data_nodes[data_slot_id]
    assert data_node.producer_node_instance_hash == "A"
~~~~~
~~~~~python.new
    
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
    channels_to_a = [c for c in topology.channels if c.target_data_slot_hash is None] # Wait, channel is Source -> Target
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
    assert hasattr(topology, "initial_values"), "BipartiteGraph must hold initial values for constants"
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
    edge_ab = EdgeIR(source_node_instance_hash="A", target_node_instance_hash="B", target_arg="dep_b")
    edge_ac = EdgeIR(source_node_instance_hash="A", target_node_instance_hash="C", target_arg="dep_c")
    
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
~~~~~

### 下一步建议
测试现在会失败（RED），原因主要有：
1.  `BipartiteGraph` 缺少 `initial_values` 字段。
2.  `Backend` 尚未实现字面量提取和常量 `DataNode` 的生成逻辑。

接下来，我们将进入 **GREEN** 阶段。我将：
1.  更新 `cascade.spec.topology.BipartiteGraph`，添加 `initial_values` 字段。
2.  更新 `cascade.compiler.backend.Backend`，实现字面量处理逻辑。
