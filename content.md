You are absolutely right. API consistency is crucial for a good developer experience. The `visualize` function should behave just like the `run` function and support the new auto-gathering syntax. This is an excellent catch.

Following our TDD process, I will first add a new test case to `test_visualize.py` that uses this new syntax. This test will fail, establishing our "RED" state, and will precisely define the behavior we need to implement.

## [WIP] test: Add TDD test for visualize() auto-gathering

### 用户需求
`cs.visualize()` 函数的 API 应与 `cs.run()` 保持一致，支持接收一个包含 `LazyResult` 实例的列表或元组，并为这个隐式的并行工作流生成正确的图表示。

### 评论
这是一个重要的 API 一致性改进。让 `visualize` 和 `run` 支持相同的输入类型，可以减少用户的困惑，并强化 Cascade 声明式 API 的直观性。用户期望能够可视化他们将要运行的任何有效目标。

### 目标
1.  向 `tests/sdk/tools/test_visualize.py` 文件中添加一个新的测试用例。
2.  这个测试将使用 `cs.visualize([lr_a, lr_b])` 的方式调用函数。
3.  测试将断言生成的 DOT 字符串中包含了 `t_a`、`t_b` 以及隐式的 `_internal_gather` 任务对应的节点。
4.  确保此测试在当前代码下会失败。

### 基本原理
通过创建一个失败的测试，我们为 `visualize` 函数定义了一个新的行为契约。这个测试将作为我们实现此功能的明确指南和最终的验收标准，确保我们完全满足 API 一致性的要求。

### 标签
#intent/tooling #flow/ready #priority/medium #comp/sdk #scope/api #scope/dx #ai/instruct #task/domain/sdk #task/object/visualize #task/action/tdd-setup #task/state/continue

---

### Script

#### Acts 1: 为 `visualize` 添加自动汇合测试用例

我将向 `test_visualize.py` 文件追加一个新的测试，用于验证列表输入。

~~~~~act
patch_file
tests/sdk/tools/test_visualize.py
~~~~~
~~~~~python
    # 5. Assert that the styled jump edge from C to A exists
    expected_edge = (
        f'"{source_id}" -> "{target_id}" [style=bold, color=blue, label="restart"]'
    )
    assert expected_edge in dot_string
~~~~~
~~~~~python
    # 5. Assert that the styled jump edge from C to A exists
    expected_edge = (
        f'"{source_id}" -> "{target_id}" [style=bold, color=blue, label="restart"]'
    )
    assert expected_edge in dot_string


def test_visualize_with_list_of_lazy_results():
    """
    Verifies that visualize() can accept a list of LazyResults and
    correctly renders the implicit gather node.
    """

    @cs.task(pure=True)
    def t_a():
        return "a"

    @cs.task(pure=True)
    def t_b():
        return "b"

    lr_a = t_a()
    lr_b = t_b()

    dot_string = cs.visualize([lr_a, lr_b])

    # Assert that the nodes for the parallel tasks are present
    assert 'label="t_a\\n(task)"' in dot_string
    assert 'label="t_b\\n(task)"' in dot_string

    # Assert that the implicit gather node, which becomes the root, is present
    assert 'label="_internal_gather\\n(task)"' in dot_string
~~~~~

### 下一步建议

我们已经为 `visualize` 函数添加了新的测试用例。请运行测试套件。我预期这个新测试会因为 `build_graph` 无法处理列表输入而失败。一旦我们确认了 "RED" 状态，我将生成下一个计划来修改 `visualize.py` 以支持自动汇合。
