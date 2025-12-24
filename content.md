好的，我们已经完成了核心架构的演进，现在是时候将这些强大的新能力暴露给开发者了。

你的思路非常正确，让新功能变得**可观测**是第一要务。`cs.visualize` 是我们向开发者展示静态图结构的最直观窗口，增强它以支持新的控制流原语是完美的起点。

遵从我们的 TDD 协议，我将首先生成一个计划，只添加一个预期的、将会失败的测试用例。这将为我们建立一个明确的“RED”状态。

## [WIP] test: 为 visualize 添加显式跳转边的 TDD 测试用例

### 用户需求
更新 `cs.visualize` 功能，使其能够识别并以独特的样式渲染由 `cs.bind` 创建的新的显式跳转 (`ITERATIVE_JUMP`) 边。

### 评论
这是提升新架构开发者体验 (DX) 的关键一步。如果没有可视化支持，新的静态控制流图对于用户来说只是一个抽象概念。通过在 `visualize` 中清晰地展示出循环和状态转移，我们能让这个强大的新功能变得直观、易于理解和调试。

### 目标
1.  在 `tests/sdk/tools/test_visualize.py` 中创建一个新的测试用例。
2.  该测试将构建一个使用 `cs.bind`, `cs.select_jump` 和 `cs.Jump` 的最小化循环工作流。
3.  断言 `cs.visualize` 的输出 DOT 字符串中包含代表 `ITERATIVE_JUMP` 的、特定样式的边。
4.  此测试在当前代码下预期会失败，从而为我们建立一个清晰的 TDD “RED” 状态。

### 基本原理
我们将遵循严格的 TDD 流程。此计划只负责创建“靶子”（失败的测试）。测试用例会定义我们期望的最终结果：一个从任务节点指向自身的、加粗的蓝色 "jump" 边。这清晰地定义了下一阶段实现工作的验收标准。一旦此测试按预期失败，我们就可以安全地进入 GREEN 阶段的开发。

### 标签
#intent/tooling #flow/ready #priority/high #comp/sdk #comp/tests #concept/ui #scope/dx #ai/instruct #task/domain/visualization #task/object/explicit-jumps #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 在 `test_visualize.py` 中添加 TDD 测试用例

我们将向现有的可视化测试文件中追加一个新的测试函数，专门用于验证 `ITERATIVE_JUMP` 边的渲染。

~~~~~act
patch_file
tests/sdk/tools/test_visualize.py
~~~~~
~~~~~python
    # 3. Assert Constraint Edge (dotted, purple)
    expected_constraint_edge = f'"{node_constraint.structural_id}" -> "{node_target.structural_id}" [style=dotted, color=purple, label="constraint: cpu"]'
    assert expected_constraint_edge in dot_string
~~~~~
~~~~~python
    # 3. Assert Constraint Edge (dotted, purple)
    expected_constraint_edge = f'"{node_constraint.structural_id}" -> "{node_target.structural_id}" [style=dotted, color=purple, label="constraint: cpu"]'
    assert expected_constraint_edge in dot_string


def test_visualize_iterative_jump_edge():
    """
    Tests that visualize() correctly renders an ITERATIVE_JUMP edge created via cs.bind.
    """

    @cs.task
    def state_machine(data: int):
        if data < 3:
            # Signal a jump to the "next" state
            return cs.Jump(target_key="next", data=data + 1)
        # Signal a normal exit
        return "done"

    # The selector maps jump keys to their target LazyResults
    selector = cs.select_jump(
        {
            "next": state_machine,  # A jump to "next" re-invokes the same task
            None: None,  # A normal return value exits the loop
        }
    )

    # Initial call to the task, starting the state machine
    start_node = state_machine(0)

    # Statically bind the task's jump signals to the selector
    cs.bind(start_node, selector)

    # Build the graph to get the stable node ID for assertion
    from cascade.graph.build import build_graph

    _, instance_map = build_graph(start_node)
    node_id = instance_map[start_node._uuid].structural_id

    dot_string = cs.visualize(start_node)

    # Assert that a self-referencing, specially styled "jump" edge exists
    expected_edge = (
        f'"{node_id}" -> "{node_id}" [style=bold, color=blue, label="jump"]'
    )
    assert expected_edge in dot_string
~~~~~

### 下一步建议
我们已经成功地定义了验收标准。下一步，请指示我生成一个新的计划来修改 `packages/cascade-sdk/src/cascade/tools/visualize.py` 文件，使其能够识别 `EdgeType.ITERATIVE_JUMP` 并按照我们刚刚在测试中定义的方式进行渲染，从而让测试通过（进入 GREEN 状态）。
