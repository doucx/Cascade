Excellent. Tests passing means the initial implementation was correct for the self-loop case. Now we can expand on that foundation.

Your new requirement is a fantastic test case because it moves from a simple self-loop to a more complex, multi-node cycle. This will force our visualization logic to be more robust and correctly handle the general case for `ITERATIVE_JUMP` edges, which aren't always self-referential.

Following our TDD process, I will first create a new plan that adds this failing test case.

## [WIP] test: 为 visualize 添加多节点循环跳转的 TDD 测试

### 用户需求
增强 `cs.visualize` 的测试套件，添加一个测试用例，用于验证一个从下游节点 (`C`) 指向上游节点 (`A`) 的 `ITERATIVE_JUMP` 边能否被正确渲染。

### 评论
这是一个非常好的演进。我们已经验证了 `A -> A` 的情况，现在 `A -> B -> C -> A` 的场景将确保我们的可视化逻辑不仅仅是为简单的自循环硬编码的，而是能够正确理解和绘制图中任意的显式跳转。这大大增强了我们对该功能健壮性的信心。

### 目标
1.  在 `tests/sdk/tools/test_visualize.py` 文件中添加一个新的测试函数。
2.  该测试将构建一个三节点工作流 (`A -> B -> C`)。
3.  节点 `C` 将通过 `cs.bind` 绑定到一个 `JumpSelector`，该选择器可以将控制流跳回节点 `A`。
4.  断言 `cs.visualize` 的输出中包含一条从节点 `C` 指向节点 `A` 的、具有特定 "jump" 样式的边。
5.  此测试预期会失败，因为当前实现硬编码了自引用边 (`source -> source`)。

### 基本原理
我们继续严格遵循 TDD。此计划将定义一个新的、更复杂的验收标准。我们知道当前的实现是 `dot_parts.append(f' "{edge.source.structural_id}" -> "{edge.source.structural_id}"{style};')`，它总是创建一个自环。而我们的新测试将断言一个 `C -> A` 的边。因此，这个测试必然会失败，从而为我们进入下一个 "GREEN" 阶段设置一个明确的目标：通用化 `ITERATIVE_JUMP` 边的渲染逻辑，使其使用 `edge.target`（由图构建器正确设置）而不是硬编码的 `edge.source`。

### 标签
#intent/tooling #flow/ready #priority/medium #comp/sdk #comp/tests #concept/ui #scope/dx #ai/instruct #task/domain/visualization #task/object/explicit-jumps #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 添加多节点循环跳转的可视化测试

我们将再次 `patch` 测试文件，在末尾追加新的测试用例。

~~~~~act
patch_file
tests/sdk/tools/test_visualize.py
~~~~~
~~~~~python
    expected_edge = (
        f'"{node_id}" -> "{node_id}" [style=bold, color=blue, label="jump"]'
    )
    assert expected_edge in dot_string
~~~~~
~~~~~python
    expected_edge = (
        f'"{node_id}" -> "{node_id}" [style=bold, color=blue, label="jump"]'
    )
    assert expected_edge in dot_string


def test_visualize_multi_node_jump_edge():
    """
    Tests that a jump from a downstream node to an upstream node is visualized correctly.
    Creates a workflow like A -> B -> C -> A.
    """

    @cs.task
    def task_a():
        return 1

    @cs.task
    def task_b(val):
        return val + 1

    @cs.task
    def task_c(val):
        # This task will jump back to the start
        return cs.Jump(target_key="restart")

    # 1. Define the workflow chain
    node_a = task_a()
    node_b = task_b(node_a)
    node_c = task_c(node_b)

    # 2. Define the selector that creates the C -> A loop
    selector = cs.select_jump(
        {
            "restart": node_a,  # A jump to "restart" re-invokes the first task
        }
    )

    # 3. Bind the jump signal from C to the selector
    cs.bind(node_c, selector)

    # 4. Build graph to get stable IDs
    from cascade.graph.build import build_graph

    _, instance_map = build_graph(node_c)
    source_id = instance_map[node_c._uuid].structural_id
    target_id = instance_map[node_a._uuid].structural_id

    dot_string = cs.visualize(node_c)

    # 5. Assert that the styled jump edge from C to A exists
    expected_edge = (
        f'"{source_id}" -> "{target_id}" [style=bold, color=blue, label="jump"]'
    )
    assert expected_edge in dot_string
~~~~~

### 下一步建议
我们已经成功地为更复杂的循环场景定义了验收标准。这个测试现在应该会失败。

下一步，请指示我生成一个新的计划来修正 `packages/cascade-sdk/src/cascade/tools/visualize.py` 中的 `ITERATIVE_JUMP` 处理逻辑。我们将移除硬编码的自引用，并使其正确地使用 `GraphBuilder` 在 `Edge` 对象中解析出的、真正的 `target` 节点。
