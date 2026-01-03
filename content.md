分析完全正确。测试失败是我的责任，这暴露出我之前生成的 `libcst` 脚本存在一个明显的缺陷。

这是一个典型的重构不彻底导致的问题。脚本成功地重命名了 `NodeIR` 类定义中的 `id` 属性，但它用于查找和替换属性*访问*（例如 `some_variable.id`）的逻辑过于简单，未能覆盖所有真实世界的使用场景。

## [WIP] fix: 修正因 id 重构不完全导致的属性访问错误

### 错误分析

根本原因在于 `scripts/refactor_hash_ids.py` 脚本中的 `leave_Attribute` 方法。其重命名 `.id` 的逻辑依赖于一个简单的启发式规则：它只在持有该对象的变量名（如 `node_ir`）出现在一个预定义的“白名单”中时才进行重命名。

然而，在失败的测试用例中，`NodeIR` 对象是通过更复杂的方式被访问的，例如：
*   通过字典访问: `nodes["producer"].id`
*   通过列表索引: `graph_ir.nodes[0].id`

在这些情况下，`libcst` 看到的基础对象是 `Subscript` 节点，而不是一个简单的 `Name` 节点，因此白名单检查逻辑被跳过，导致 `.id` 未被重命名为 `.current_node_instance_hash`，从而引发了 `AttributeError`。

### 用户需求

修复所有因 `NodeIR.id` 重构不完全而失败的测试用例，确保它们使用新的 `current_node_instance_hash` 属性。

### 评论

虽然可以进一步完善 `libcst` 脚本以覆盖这些边缘情况，但这会显著增加脚本的复杂性。考虑到失败的范围被限定在少数几个测试文件中，当前最高效、最安全的操作是进行一次精确的手动修复，以快速让测试套件恢复到“绿色”状态。这为我们后续更大范围的清理工作提供了一个稳定的基线。

### 目标

1.  精确定位四个失败测试文件中的 `AttributeError` 来源。
2.  通过 `patch_file` 操作，将所有对 `NodeIR` 实例的 `.id` 属性的访问，全部修正为 `.current_node_instance_hash`。

### 基本原理

我们将直接针对 `lint` 报告和测试失败日志指出的具体代码行进行修复。由于我们已经明确知道 `NodeIR` 的 `id` 属性是唯一被重命名的目标，因此可以安全地在这些上下文中进行替换，而不会影响其他类的 `.id` 属性。

### 标签

#intent/fix #flow/ready #priority/critical #comp/compiler #comp/tests #scope/dx #ai/refine #task/domain/tooling #task/object/refactor-script #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `test_resource_contention.py`

此文件在两个测试用例中错误地访问了 `NodeIR.id`。我们将一次性修复它们。

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
    # Verify Wiring
    # Pick a random task node to verify its path
    sample_node_ir = graph_ir.nodes[0]
    # Path: Allocator -> D_gnt -> Bleacher
    # We need to find the specific grant port for this task.
    # It requires the ID of the Requestor node.
    req_id = PhysicalIdGenerator.requestor(sample_node_ir.id, RESOURCE_NAME)
    expected_port = f"gnt_for_{req_id}"

    inspector.assert_port_exists(allocator_id, expected_port)
~~~~~
~~~~~python.new
    # Verify Wiring
    # Pick a random task node to verify its path
    sample_node_ir = graph_ir.nodes[0]
    # Path: Allocator -> D_gnt -> Bleacher
    # We need to find the specific grant port for this task.
    # It requires the ID of the Requestor node.
    req_id = PhysicalIdGenerator.requestor(
        sample_node_ir.current_node_instance_hash, RESOURCE_NAME
    )
    expected_port = f"gnt_for_{req_id}"

    inspector.assert_port_exists(allocator_id, expected_port)
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
    # Verify D_gnt -> Bleacher
    bleacher_id = PhysicalIdGenerator.bleach_node(sample_node_ir.id)
    inspector.assert_connection(
        d_gnt_id, bleacher_id, target_port=f"res_{RESOURCE_NAME}"
    )
~~~~~
~~~~~python.new
    # Verify D_gnt -> Bleacher
    bleacher_id = PhysicalIdGenerator.bleach_node(
        sample_node_ir.current_node_instance_hash
    )
    inspector.assert_connection(
        d_gnt_id, bleacher_id, target_port=f"res_{RESOURCE_NAME}"
    )
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
        # We wait until we have 2 * TASK_COUNT logical task completions.
        # But we log EVERY physical event to diagnose the deadlock.
        def collection_predicate(e: ObservedEvent):
            # Log ALL physical events for debugging
            node_id = e.trace_data.get("id", "unknown")
            print(
                f"[OBS-START] {node_id}"
                if e.event_type == "start"
~~~~~
~~~~~python.new
        # We wait until we have 2 * TASK_COUNT logical task completions.
        # But we log EVERY physical event to diagnose the deadlock.
        def collection_predicate(e: ObservedEvent):
            # Log ALL physical events for debugging
            node_id = e.trace_data.get("current_node_instance_hash", "unknown")
            print(
                f"[OBS-START] {node_id}"
                if e.event_type == "start"
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
    # t_gpu's bleacher should NOT be connected to CPU allocator
    # We need to find t_gpu's node ID. Since it's list input, IDs are generated.
    # IR generator uses hashing.
    node_ids = [n.id for n in graph_ir.nodes]
    # Let's assume index 0 is gpu, 1 is cpu (list order preserved)
    gpu_node_id = node_ids[0]
~~~~~
~~~~~python.new
    # t_gpu's bleacher should NOT be connected to CPU allocator
    # We need to find t_gpu's node ID. Since it's list input, IDs are generated.
    # IR generator uses hashing.
    node_ids = [n.current_node_instance_hash for n in graph_ir.nodes]
    # Let's assume index 0 is gpu, 1 is cpu (list order preserved)
    gpu_node_id = node_ids[0]
~~~~~

#### Acts 2: 修复 `test_sovereign_wiring.py`

此文件通过字典访问 `NodeIR`，同样需要修正。

~~~~~act
patch_file
packages/cascade-compiler/tests/integration/test_sovereign_wiring.py
~~~~~
~~~~~python.old
    # Get nodes
    nodes = {n.name: n for n in graph_ir.nodes}
    t1_id = nodes["producer"].id
    t2_id = nodes["consumer"].id

    t1_stainer_id = f"{t1_id}.stain"
~~~~~
~~~~~python.new
    # Get nodes
    nodes = {n.name: n for n in graph_ir.nodes}
    t1_id = nodes["producer"].current_node_instance_hash
    t2_id = nodes["consumer"].current_node_instance_hash

    t1_stainer_id = f"{t1_id}.stain"
~~~~~

#### Acts 3: 修复 `test_generator.py`

这是最直接的失败案例，修复它。

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/frontend/test_generator.py
~~~~~
~~~~~python.old
    # Verify downstream node correctly references the upstream node's ID
    assert downstream_node.name == "add"
    assert downstream_node.inputs == {"0": upstream_node.id, "1": 3}
~~~~~
~~~~~python.new
    # Verify downstream node correctly references the upstream node's ID
    assert downstream_node.name == "add"
    assert downstream_node.inputs == {"0": upstream_node.current_node_instance_hash, "1": 3}
~~~~~

### 下一步建议

我们已经针对性地修复了所有已知的 `AttributeError`。现在最关键的步骤是：

1.  **重新运行测试套件**: 立即执行 `pytest`，确保所有测试都能通过，验证我们的修复是正确且完整的。
2.  **提交修复**: 一旦测试通过，应将这些修复和之前的 `libcst` 脚本作为一个原子提交，以记录完整的重构过程。
3.  **继续清理**: 在测试套件稳定的基础上，我们可以回过头来处理 `lint` 脚本报告的其他 `_id` 模糊命名警告，继续推进代码库的规范化。

如果您同意，我将为您生成一个运行 `pytest` 的计划。
