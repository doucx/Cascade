简要回答
是的，这是完全符合预期的错误。我在上一轮重写 `cascade/graph/build.py` 时，不慎遗漏了文件末尾模块级函数 `build_graph` 的定义，导致接口断裂。

我们将遵循 TDD 流程：
1.  **RED (Fix Blocker)**: 首先修复 `build.py` 中缺失的导出，消除 `ImportError`，让测试套件能够运行（并预期会失败）。
2.  **RED (Adapt Tests)**: 修改单元测试代码以适应新的 `Node` 结构（例如，将 `node.execution_mode` 更改为 `node.definition.mode`）。这是“焦土政策”的一部分：我们更新测试以反映新的现实，而不是为了兼容性保留旧接口。
3.  **GREEN**: 验证测试通过。

## [WIP] fix(graph): 恢复 build_graph 导出并适配单元测试

### 用户需求
1.  修复 `cascade/graph/build.py` 中的 `ImportError`。
2.  开始 TDD 流程，更新单元测试以匹配破坏性的 `Node` 重构。

### 评论
当前的 `Node` 对象已经失去 `execution_mode` 等直接属性，转而存储在 `definition` 中。与其在 `Node` 上添加复杂的 `__getattr__` 代理，不如直接更新测试代码，使其明确地访问 `definition`。这符合“显式优于隐式”的原则，也强化了架构的清晰度。

### 目标
1.  在 `cascade/graph/build.py` 中添加 `build_graph` 函数。
2.  更新 `tests/test_execution_mode.py` 适配新 API。
3.  更新 `tests/test_build.py` 适配新 API。

### 基本原理
-   **修复接口**: `build_graph` 是公共 API 的入口，必须存在。
-   **测试适配**: 由于我们移除了 `Node` 上的代理属性，测试断言曾经的 `node.execution_mode` 现在必然失败。我们需要将测试断言指向正确的位置 `node.definition.mode`。

### 标签
#intent/fix #flow/draft #priority/critical #comp/graph #concept/testing #scope/core #ai/instruct #task/domain/testing #task/object/unit-tests #task/action/adaptation #task/state/continue

---

### Script

#### Acts 1: 修复 build.py (Restore Export)

~~~~~act
run_command
~~~~~
~~~~~bash
cat >> packages/cascade-graph/src/cascade/graph/build.py <<EOF

def build_graph(
    target: Any, registry: NodeRegistry | None = None
) -> Tuple[Graph, Dict[str, Node]]:
    return GraphBuilder(registry=registry).build(target)
EOF
~~~~~

#### Acts 2: 适配 test_execution_mode.py

将过时的属性访问更新为新的 IR 结构。

~~~~~act
patch_file
packages/cascade-graph/tests/test_execution_mode.py
~~~~~
~~~~~old
    # 4. Assert the execution modes
    assert compute_node.execution_mode == "compute", (
        "Node for compute_task should have mode 'compute'"
    )
    assert blocking_node.execution_mode == "blocking", (
        "Node for blocking_task should have mode 'blocking'"
    )
    assert default_node.execution_mode == "blocking", (
        "Node for default_task should have the default mode 'blocking'"
    )
~~~~~
~~~~~new
    # 4. Assert the execution modes (now in definition)
    assert compute_node.definition.mode == "compute", (
        "Node for compute_task should have mode 'compute'"
    )
    assert blocking_node.definition.mode == "blocking", (
        "Node for blocking_task should have mode 'blocking'"
    )
    assert default_node.definition.mode == "blocking", (
        "Node for default_task should have the default mode 'blocking'"
    )
~~~~~

#### Acts 3: 适配 test_build.py

检查 `test_build.py` 中是否有类似的断言。虽然现在的脚本中 `test_build.py` 主要检查拓扑结构和 `arg_name`，但我们最好检查一下是否直接访问了已删除的属性。

目前 `test_build.py` 中的 `test_build_graph_with_param_factory` 访问了 `node_type` 和 `input_bindings`，这些在 `Node` 上仍然保留。

但是，为了确保一切正常，我们先运行一次测试，看看还有什么挂了。

### 下一步建议
在执行完上述修复后，请运行测试。如果仍有测试失败（这是预期的，因为我们还没有修复运行时层，`test_engine_*.py` 可能会因为 Runtime 代码未适配而崩溃），我们将继续按照 TDD 流程，根据报错信息去修复 Runtime 代码。
