Excellent catch. The tests have correctly identified a logic change I introduced in the `standard_bleacher`. My change to always set a canonical `id` in the trace was intentional, but I failed to update the corresponding unit tests to reflect this new, correct behavior. The tests are brittle because they were asserting the old "last write wins" logic for the `id` field, which is no longer true.

The `standard_bleacher` *must* overwrite the `id` to establish the true, unambiguous identity of the lifecycle event it is creating. The tests need to be fixed to assert this correct behavior.

## [WIP] fix(tests): Align bleacher tests with canonical ID trace logic

### 错误分析
`test_bleacher.py` 中的两个测试用例（`test_standard_bleacher_with_empty_inputs` 和 `test_standard_bleacher_merges_traces`）断言了 `standard_bleacher` 的旧 Trace 合并行为。它们没有考虑到新的逻辑，即 `standard_bleacher` 现在会强制用自己的逻辑节点 ID 覆盖 Trace 中的 `id` 字段，以确保 Trace 的身份正确性。因此，测试断言失败。

### 用户需求
修复 `test_bleacher.py` 中失败的断言，使其与 `standard_bleacher` 正确的、新的行为保持一致。

### 评论
这是一个“测试落后于实现”的典型案例。实现本身是正确的——Bleacher 节点必须拥有设置其启动的 Trace ID 的主权。我们必须修复测试，使其验证这一正确的行为，而不是试图回滚实现来满足过时的测试。

### 目标
-   更新 `test_standard_bleacher_with_empty_inputs` 的断言，期望 Trace 中包含由 Mock Node 设置的 `id`。
-   更新 `test_standard_bleacher_merges_traces` 的断言，期望 `id` 字段被 Mock Node 的 ID 覆盖，而不是继承自上游 Token。

### 基本原理
**主权 Trace 原则**: 每个任务生命周期的 Trace 都必须由其自身的 `BleachNode` 进行身份标识。上游任务的 `id` 是上游任务的上下文，当前任务必须建立自己的上下文。测试用例必须验证这一原则。

### 标签
#intent/fix #flow/ready #priority/high #comp/std #comp/tests #scope/core #task/domain/core #task/object/tests #task/action/cleanup #task/state/continue

---

### Script

#### Acts 1: 更新 `test_standard_bleacher.py` 中的断言

我们将修改两个失败测试中的断言，使其符合 `standard_bleacher` 新的、正确的 Trace ID 覆盖逻辑。

~~~~~act
patch_file
packages/cascade-std/tests/unit/triad/test_bleacher.py
~~~~~
~~~~~python.old
    assert "trace_output" in outputs
    assert outputs["trace_output"].payload == {"start_ts": MOCK_TIMESTAMP}
~~~~~
~~~~~python.new
    assert "trace_output" in outputs
    assert outputs["trace_output"].payload == {
        "id": "test_node",
        "start_ts": MOCK_TIMESTAMP,
    }
~~~~~

~~~~~act
patch_file
packages/cascade-std/tests/unit/triad/test_bleacher.py
~~~~~
~~~~~python.old
    # Check for merged data
    assert trace_payload.get("id") == "B"  # Last write wins on conflict
    assert trace_payload.get("source") == "X"
~~~~~
~~~~~python.new
    # Check for merged data
    # The 'id' is ALWAYS overwritten by the bleacher for canonical identity.
    assert trace_payload.get("id") == "test_node"
    assert trace_payload.get("source") == "X"
~~~~~

### 下一步建议
这次修复应该使 `cascade-std` 包的单元测试全部通过。现在，整个 Phase 1 的代码修改和初步修复已经完成。我建议我们重新运行所有包的完整测试套件，以确保这次大规模重构没有引入其他回归问题。一旦测试套件变绿，我们就可以自信地进入 Phase 2。
