好的，日志已经启用，并且我们得到了一个更精确的失败信息：`KeyError: 'signal_arg'`。

这是一个极好的线索，结合日志，我们可以精确地定位问题。

1.  **日志确认了激活逻辑正确**:
    ```
    [is_ready CHECK for process]
     -> Port 'data_arg' (DATA) source excited: True
     -> Port 'signal_arg' (SIGNAL) source excited: True
     -> Final is_ready result: True
    ```
    日志清晰地显示，在最后一次检查中，`is_ready` 正确地返回了 `True`。这意味着 `Reactor` 随后会调用 `_fire`，并执行 `f_node.consume_inputs()`。

2.  **`KeyError` 指向了 `consume_inputs`**:
    *   错误发生在 `assert submitted_inputs["signal_arg"].payload is None`。
    *   `submitted_inputs` 是 `mock_executor.submit` 接收到的参数，它直接来自于 `f_node.consume_inputs()` 的返回值。
    *   `KeyError: 'signal_arg'` 意味着 `consume_inputs()` 返回的字典中，**根本不包含 `'signal_arg'` 这个键**。

3.  **根本原因**:
    让我们回顾一下我们在上一步中对 `consume_inputs` 的修改：
    ```python
    def consume_inputs(self) -> Dict[str, Token]:
        # ...
        for name, port in self.inputs.items():
            if port.source:
                token = port.source.take()
                # Only add to the result if it's a DATA port and a token was present
                if token and port.kind == ChannelKind.DATA:
                    result[name] = token
        return result
    ```
    这段代码**是故意且正确地**只将来自 `DATA` 类型端口的令牌放入 `result` 字典中。`SIGNAL` 端口的令牌被消耗（`take()`），但其结果被丢弃了。这是为了确保业务逻辑函数（由 Executor 调用）不会收到无意义的信号令牌作为参数。

**结论**: `consume_inputs` 的实现是正确的，它忠实地执行了“信号仅用于激活，不传递数据”的原则。然而，我们的**测试用例的断言是错误的**。它错误地期望 `'signal_arg'` 会出现在传递给执行器的参数字典中。

正确的测试应该断言两件事：
1.  `'data_arg'` **在** `submitted_inputs` 中，并且有正确的 `payload`。
2.  `'signal_arg'` **不在** `submitted_inputs` 中。

我们将修改测试用例来反映这个正确的行为。

## [WIP] fix(test): 修正对 consume_inputs 行为的测试断言

### 错误分析
`KeyError: 'signal_arg'` 的出现是因为 `FuncNode.consume_inputs` 方法被正确地实现为只返回来自 `DATA` 类型端口的令牌，从而过滤掉了 `SIGNAL` 类型的输入。这导致传递给 `executor.submit` 的参数字典中不包含 `signal_arg` 键。失败的根本原因是测试用例中的断言与 `consume_inputs` 的正确行为不匹配。

### 用户需求
修正 `test_dual_barrier_activation_waits_for_all_inputs` 测试用例，使其正确地断言 `SIGNAL` 端口的输入不会被传递给执行器。

### 评论
这个修复使我们的测试与物理模型的实现精确对齐。它强制验证了一个核心设计原则：信号（Signal）的物理作用是在满足激活势垒后消失，而不应作为数据（Data）流入计算核心。这是一个更严谨、更正确的测试。

### 目标
1.  修改 `packages/cascade-vm/tests/reactor/test_polarized_channels.py`。
2.  将失败的断言 `assert submitted_inputs["signal_arg"].payload is None` 替换为 `assert "signal_arg" not in submitted_inputs`，以正确验证 `consume_inputs` 的过滤行为。

### 基本原理
我们将使用一个 `patch_file` 操作来精确地修正测试文件中的断言。旧的断言被移除，新的断言则明确表达了 `SIGNAL` 输入不应出现在最终参数字典中的预期，从而使测试逻辑与代码实现保持一致。

### 标签
#intent/fix #intent/tooling #flow/ready #priority/high #comp/tests #concept/state #scope/core #ai/instruct #task/domain/testing #task/object/reactor-physics #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正测试用例中的断言

我们将更新 `test_polarized_channels.py` 以反映 `consume_inputs` 的正确行为。

~~~~~act
patch_file
packages/cascade-vm/tests/reactor/test_polarized_channels.py
~~~~~
~~~~~python.old
    call_args = mock_executor.submit.call_args[0]
    submitted_node = call_args[0]
    submitted_inputs = call_args[1]

    assert submitted_node == f_node
    assert submitted_inputs["data_arg"].payload == "some_data"
    assert submitted_inputs["signal_arg"].payload is None
~~~~~
~~~~~python.new
    call_args = mock_executor.submit.call_args[0]
    submitted_node = call_args[0]
    submitted_inputs = call_args[1]

    assert submitted_node == f_node
    # Assert that DATA token was passed correctly
    assert submitted_inputs["data_arg"].payload == "some_data"
    # Assert that SIGNAL token was consumed but NOT passed to executor
    assert "signal_arg" not in submitted_inputs
~~~~~

### 下一步建议
我们已经根据 `consume_inputs` 的正确行为修正了测试。现在，请再次运行 `pytest`。测试应该会通过，这意味着我们已经成功地、可验证地实现了双势垒物理模型。

测试通过后，我们将正式完成 **阶段 5.A**，并可以进入 **阶段 5.B**。
