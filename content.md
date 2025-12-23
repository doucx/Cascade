You are absolutely right to point this out. My apologies. I focused on fixing the logic that *produces* the event, but overlooked the unit test that *simulates* the event to test the subscriber. This is the last piece of the puzzle.

## [WIP] fix(tests): Adapt preview tool unit test to new event model

### 错误分析
测试 `tests/sdk/tools/test_preview.py::test_console_subscriber_renders_correctly` 失败的根本原因是，该测试为了独立验证 `DryRunConsoleSubscriber` 的渲染能力，手动创建了一个 `PlanNodeInspected` 事件实例。在我之前的修复中，我更新了 `PlanNodeInspected` 的定义（将 `literal_inputs` 重命名为 `input_inputs`），但忘记更新这个手动创建事件的测试代码。因此，它仍然尝试使用已不存在的 `literal_inputs` 关键字参数，导致了 `TypeError`。

### 用户需求
修复最后一个失败的测试，使测试套件完全通过。

### 评论
这是一个典型的“灯下黑”错误。我们已经非常接近成功，修复这个简单的测试适配问题将为“The Great Split”的第一阶段画上圆满的句号。

### 目标
1.  修改 `test_console_subscriber_renders_correctly` 测试，使其在实例化 `PlanNodeInspected` 时使用正确的 `input_bindings` 关键字。
2.  同时更新该测试中的断言，以匹配新的控制台输出格式。

### 基本原理
通过一个精确的 `patch_file` 操作，我们可以一次性地修正这个测试用例的事件创建和断言逻辑。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/sdk #ai/instruct #task/domain/testing #task/object/unit-test #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `test_preview.py` 中的单元测试

我们将更新 `test_console_subscriber_renders_correctly` 以使用 `input_bindings`。

~~~~~act
patch_file
tests/sdk/tools/test_preview.py
~~~~~
~~~~~python
    # 2. Publish Node Event
    bus.publish(
        PlanNodeInspected(
            index=1,
            total_nodes=2,
            node_id="n1",
            node_name="my_task",
            literal_inputs={"param": 42},
        )
    )
    captured = capsys.readouterr()
    assert "[1/2]" in captured.out
    assert "my_task" in captured.out
    assert "'param': 42" in captured.out
~~~~~
~~~~~python
    # 2. Publish Node Event
    bus.publish(
        PlanNodeInspected(
            index=1,
            total_nodes=2,
            node_id="n1",
            node_name="my_task",
            input_bindings={"param": cs.spec.binding.Constant(42)},
        )
    )
    captured = capsys.readouterr()
    assert "[1/2]" in captured.out
    assert "my_task" in captured.out
    assert "Bindings: {'param': Const(42)}" in captured.out
~~~~~

### 下一步建议
这是最后一个已知的错误。执行此修复后，测试套件应该会 100% 通过。

如果所有测试都通过，我将生成一个 `[COMMIT]` 计划，将“The Great Split”的所有变更作为一个原子提交进行封装。
