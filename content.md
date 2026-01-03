你完全正确，我的分析存在疏漏。非常感谢你提供了详细的错误日志。

测试断言失败的根本原因是，我对编译器生成的节点 ID 做了错误的假设。我错误地预测了一个基于简单计数器（如 `t_1`）的、人类可读的 ID `const.t_1.0`。

然而，实际的编译器实现 (`IRGenerator` + `HashingService`) 为每个逻辑节点生成一个基于其内容（代码定义、参数、依赖关系等）的**内容寻址哈希**作为其唯一 ID。`PhysicalIdGenerator` 再以此哈希为基础，生成物理节点的 ID（例如 `...hash....bleach`）。

这种基于哈希的 ID 是动态的，但却是确定性的。直接在测试中硬编码这个哈希值是极其脆弱的，任何微小的改动都会使其失效。

正确的测试方法不应该依赖于不稳定的 ID，而应该断言节点的**稳定属性**，例如它的 `name` 和 `initial_payload`。

我将立即修正这个测试，使其更加健壮。

## [WIP] fix(test): 修正图纯度测试以验证稳定属性而非动态ID

### 用户需求
修复 `test_graph_purity.py` 中失败的断言，使其能够正确验证反序列化后图的完整性。

### 评论
这次修复体现了一个核心的测试原则：**测试应该验证行为和意图，而不是不稳定的实现细节。** 节点的哈希 ID 是一个实现细节，而节点“作为一个值为 1 的常量”是它的核心意图。通过断言 `name` 和 `initial_payload`，我们使测试与哈希算法的实现解耦，从而变得更加健壮。

### 目标
1.  修改 `packages/cascade-compiler/tests/integration/test_graph_purity.py`。
2.  移除对硬编码节点 ID 的断言。
3.  添加新的断言，通过遍历所有节点，来验证图中确实存在 `name` 为 `Const(a)` 且 `initial_payload` 为 `1` 的常量节点，以及 `name` 为 `Const(b)` 且 `initial_payload` 为 `2` 的节点。

### 基本原理
通过遍历反序列化后的 `deserialized_graph.nodes.values()`，我们可以检查每个节点的属性。通过组合对 `isinstance`, `node.name`, 和 `node.initial_payload` 的检查，我们可以唯一地、可靠地识别出我们关心的常量节点，而无需知道它们那由哈希算法生成的、不稳定的 ID。

### 标签
#intent/fix #flow/ready #priority/high #comp/compiler #comp/tests #scope/dx #ai/instruct #task/domain/vm #task/object/graph-purity #task/action/testing #task/state/continue

---

### Script

#### Acts 1: 修正图纯度测试的断言逻辑

我们将修补 `test_graph_purity.py` 文件，用更健壮的属性检查替换脆弱的 ID 检查。

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_graph_purity.py
~~~~~
~~~~~python.old
    # 4. Verify basic integrity after deserialization
    assert len(physical_graph.nodes) == len(deserialized_graph.nodes)
    assert len(physical_graph.channels) == len(deserialized_graph.channels)
    assert "const.t_1.0" in deserialized_graph.nodes
    assert deserialized_graph.nodes["const.t_1.0"].initial_payload == 1
~~~~~
~~~~~python.new
    # 4. Verify basic integrity after deserialization
    assert len(physical_graph.nodes) == len(deserialized_graph.nodes)
    assert len(physical_graph.channels) == len(deserialized_graph.channels)

    # Instead of asserting a brittle, hash-based ID, we assert that nodes
    # with the expected stable properties exist in the graph.
    nodes_collection = deserialized_graph.nodes.values()
    
    # Check for the constant node for argument 'a' with value 1
    assert any(
        node.name == "Const(a)" and node.initial_payload == 1
        for node in nodes_collection
    ), "Constant node for value 1 not found after deserialization"

    # Check for the constant node for argument 'b' with value 2
    assert any(
        node.name == "Const(b)" and node.initial_payload == 2
        for node in nodes_collection
    ), "Constant node for value 2 not found after deserialization"
~~~~~

### 下一步建议

我们已经修正了图纯度测试，使其变得健壮。现在我们可以继续执行路线图的下一步。

下一步是**任务 2.2: 统一函数签名 (Signature Standardization)**。我们将审计 `cascade-std` 和测试用例中的所有 Worker 函数，确保它们的签名严格统一为 `async def (inputs, node, resources) -> dict`。这将为 Rust FFI 桥接提供一个稳定、单一的适配目标。

如果你同意，我将开始对 `cascade-std` 包中的物理函数进行盘点和必要的重构。
