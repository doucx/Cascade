非常好的发现！这是一个“好”的错误。

它证明我们上一轮的修复是成功的：为了遵守二分图定律，Builder 确实在 `node_a.stain -> node_b.bleach` 之间插入了一个额外的数据节点。
现在，测试因为其过时的断言而失败。我们需要更新测试，使其与新的、物理上正确的图结构保持一致。

## [WIP] test(compiler): 更新因二分图修复引入的节点/通道数量断言

### 错误分析
`test_builder_expands_and_wires_nodes` 测试用例断言生成的图中包含 14 个节点。然而，在我们为了修复“F -> F”连接而引入了中间数据节点（`D_dep`）后，`node_a` 和 `node_b` 之间的依赖关系现在需要一个额外的 `PhysicsDataNode`。
这使得总节点数增加到 15，导致断言失败。
同时，原本的一条 F->F 通道被替换为了两条 F->D->F 通道，通道总数也需要更新。

### 用户需求
更新 `test_builder.py` 中的断言，以反映新的、物理上正确的节点和通道数量。

### 评论
这是一个积极的信号，表明我们的测试套件足够敏感，能够捕捉到架构的结构性变化。使测试与实现同步是完成此次重构的最后一步。

### 目标
1.  修改 `test_builder.py`。
2.  将节点数量断言从 `14` 更新为 `15`。
3.  将通道数量断言从 `18` 更新为 `19`。
4.  更新注释以解释新的计算方式。

### 基本原理
*   **节点数**: 2 Triads (12) + 1 D_life + 1 F_obs + **1 D_dep** = 15
*   **通道数**: 2 Triads (12) + **2 Data Dep** + 4 Obs + 1 D_life->F_obs = 19

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #comp/compiler #scope/core #ai/instruct #task/domain/testing #task/object/unit-test #task/action/update #task/state/end

---

### Script

#### Acts 1: 更新测试断言

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_builder.py
~~~~~
~~~~~python.old
    # Assert nodes: 2 triads (6 nodes each) + 1 D_life + 1 F_obs = 14 nodes
    assert len(graph.nodes) == 14
    assert "global.observability.bus" in graph.nodes
    assert "global.observability.observer" in graph.nodes
    assert "node_a.stain" in graph.nodes
    assert "node_b.bleach" in graph.nodes

    # Assert channels
    # 2 triads (6 internal) = 12
    # 1 data dependency = 1
    # 2 triads * 2 obs channels to D_life = 4
    # 1 D_life -> F_obs channel = 1
    # Total = 12 + 1 + 4 + 1 = 18
    assert len(graph.channels) == 18

    # 1. Test data dependency wiring
    data_channel = next(
        c
        for c in graph.channels
        if c.source_node_id == "node_a.stain" and c.target_node_id == "node_b.bleach"
    )
    assert data_channel is not None
    assert data_channel.source_port == "output"
~~~~~
~~~~~python.new
    # Assert nodes: 2 triads (6 nodes each) + 1 D_life + 1 F_obs + 1 D_dep = 15 nodes
    assert len(graph.nodes) == 15
    assert "global.observability.bus" in graph.nodes
    assert "global.observability.observer" in graph.nodes
    assert "node_a.stain" in graph.nodes
    assert "node_b.bleach" in graph.nodes
    assert "dep.node_a.to.node_b.data" in graph.nodes

    # Assert channels
    # 2 triads (6 internal) = 12
    # 1 data dependency = 2 (F->D, D->F)
    # 2 triads * 2 obs channels to D_life = 4
    # 1 D_life -> F_obs channel = 1
    # Total = 12 + 2 + 4 + 1 = 19
    assert len(graph.channels) == 19

    # 1. Test data dependency wiring (F -> D -> F)
    stain_to_dep = next(
        c
        for c in graph.channels
        if c.source_node_id == "node_a.stain"
        and c.target_node_id == "dep.node_a.to.node_b.data"
    )
    assert stain_to_dep is not None

    dep_to_bleach = next(
        c
        for c in graph.channels
        if c.source_node_id == "dep.node_a.to.node_b.data"
        and c.target_node_id == "node_b.bleach"
    )
    assert dep_to_bleach is not None
    assert dep_to_bleach.target_port == "data"
~~~~~

### 下一步建议
现在所有的单元测试都应该通过了。
请重新运行完整的测试套件。如果一切顺利，`test_resource_backpressure.py` 也应该能成功通过，因为我们已经修复了其底层的物理模型错误。
