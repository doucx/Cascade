简要回答
我们正在加速 **Phase 6 (功能对齐)**。我们现在一次性编写所有剩余的测试用例，覆盖 `Frontend` 的控制流识别、动态参数支持 (`Param`/`Env`) 以及 Map 节点的初步支持。

这将使我们进入一个较大的 RED 状态，然后我们逐一实现功能以使其变绿。

## [WIP] test(compiler): 全面覆盖 Phase 6 功能对齐需求

### 用户需求
1.  在 `test_frontend.py` 中添加 `run_if` (Control Edge) 的测试。
2.  添加 `Param` 和 `Env` (Input Context) 的测试。
3.  添加 `Map` 节点的测试（如果决定在 IR 中支持）。

### 评论
我们遵循“正规军”路线。
*   对于 **Map**，我们不搞黑盒，我们在 IR 中引入 `MapNodeIR`。这需要 Spec 的配合。
*   对于 **Param/Env**，我们在 IR 中引入 `ParamNodeIR` 或特殊的 Input 标记。目前的 Spec 中 `NodeIR.definition` 已经足够通用，但我们需要确保 `Frontend` 能正确识别 `cs.Param` 返回的特殊 `LazyResult`。

### 目标
创建一组全面的测试，定义新架构必须满足的功能契约。

### 基本原理
一次性定义好测试可以让我们更清晰地看到 Spec 和 Implementation 之间的差距，避免反复修改 Spec。

### 标签
#intent/test #flow/ready #priority/high #comp/tests #comp/compiler #task/domain/core #task/object/frontend #task/action/test #task/state/continue

---

### Script

#### Acts 1: 扩充 `test_frontend.py`

我们将添加以下测试：
1.  `test_compile_conditional_task`: 验证 `run_if` 生成 `EdgeKind.CONTROL`。
2.  `test_compile_param_input`: 验证 `cs.Param` 生成正确的 Node 和 Input。
3.  `test_compile_map_node`: 验证 `task.map()` 生成特殊的 Map 结构（虽然 Spec 还未更新，我们先写测试来驱动）。

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_frontend.py
~~~~~
~~~~~python.old
    assert edge.source_id == source_node.id
    assert edge.target_id == target_node.id
    assert edge.target_arg == "val"
~~~~~
~~~~~python.new
    assert edge.source_id == source_node.id
    assert edge.target_id == target_node.id
    assert edge.target_arg == "val"


def test_compile_conditional_task():
    """
    Case 3: Conditional Execution (run_if).
    Verify that Frontend generates an EdgeKind.CONTROL edge.
    """
    @task
    def condition(): return True
    
    @task
    def action(): return "done"

    t_cond = condition()
    t_action = action().run_if(t_cond)

    ir = Frontend.compile(t_action)

    assert len(ir.edges) == 1
    edge = ir.edges[0]
    
    # We check for the new EdgeKind
    from cascade.spec.ir.models import EdgeKind
    assert edge.kind == EdgeKind.CONTROL
    assert edge.target_arg == "_condition"  # Internal convention, or explicit field


def test_compile_param_input():
    """
    Case 4: Param Input.
    Verify that cs.Param is compiled into a NodeIR with correct metadata.
    """
    import cascade as cs
    
    # cs.Param returns a LazyResult that wraps a special internal task
    p = cs.Param("my_param", default=42)
    
    @task
    def consume(x): return x

    workflow = consume(x=p)
    
    ir = Frontend.compile(workflow)
    
    # Should have 2 nodes: Param node and Consume node
    assert len(ir.nodes) == 2
    
    # Find param node
    param_node = next(n for n in ir.nodes if n.definition.name == "_get_param_value")
    
    # Check inputs
    # The Param LazyResult stores the param name in its args/kwargs
    assert param_node.inputs.get("name") == "my_param" or param_node.inputs.get("0") == "my_param"


def test_compile_map_node():
    """
    Case 5: Map Node.
    Verify that task.map() creates a node marked as a map operation.
    """
    @task
    def double(x): return x * 2
    
    # Map over a list literal
    workflow = double.map(x=[1, 2, 3])
    
    ir = Frontend.compile(workflow)
    
    assert len(ir.nodes) == 1
    node = ir.nodes[0]
    
    # The definition should point to the underlying 'double' task
    assert node.definition.name == "double"
    
    # But the NodeIR needs a way to distinguish itself as a Map.
    # We expect a 'type' or 'mode' field in NodeIR or TaskDef.
    # Currently NodeIR doesn't have it explicitly, let's assume we add it to inputs or separate field.
    # Driving the requirement: NodeIR should have an 'execution_strategy' or similar.
    # For now, let's assert that inputs contain the list.
    assert node.inputs["x"] == [1, 2, 3]
    
    # Spec Requirement: We need to know this is a MAP, not a single call with a list arg.
    # The Frontend must populate a field. Let's assume 'meta' in NodeIR for now.
    assert node.meta.get("is_map") is True
~~~~~

### 下一步建议
测试现在会失败（RED）。我们需要系统性地修补 Spec 和 Frontend。

1.  **Spec 更新**: 修改 `NodeIR`，添加 `meta` 字段（虽然 `GraphIR` 有，但 `NodeIR` 之前定义里好像漏了，或者我们利用现有的机制）。根据测试，我们需要在 `NodeIR` 上支持 `meta` 字典。
2.  **Frontend 更新**:
    *   处理 `_condition` -> `EdgeKind.CONTROL`。
    *   处理 `MappedLazyResult` -> 设置 `meta={"is_map": True}`。

请确认是否继续执行 Spec 和 Frontend 的修复。
