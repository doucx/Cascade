好的，收到了测试失败的反馈。这是两个在重构过程中引入的简单 `NameError`。我将立即修复它们。

 错误分析
1.  **`test_e2e_rate_limit_control.py`**: 在重构时，我将 `MockWorkExecutor` 重命名为 `TimingWorkExecutor` 以提高其语义清晰度，但在实例化 `Engine` 时忘记更新这个名称。
2.  **`test_e2e_ttl.py`**: 我将 `ControllerTestApp` 的实例化移除了，并用一个本地的辅助函数 `pause_with_ttl` 替代了其功能，但在调用时仍然错误地使用了 `controller.pause_with_ttl` 而不是直接调用 `pause_with_ttl`。

## [WIP] fix: 修复 E2E 测试重构引入的 NameError

### 用户需求
修复 `test_e2e_rate_limit_control.py` 和 `test_e2e_ttl.py` 中由于重构不完整导致的 `NameError`。

### 评论
这是典型的重构后遗症。修复很简单，只需将错误的变量名和函数调用更正即可。

### 目标
1.  在 `test_e2e_rate_limit_control.py` 中，使用正确的 `TimingWorkExecutor` 类名。
2.  在 `test_e2e_ttl.py` 中，调用正确的本地辅助函数 `pause_with_ttl`。

### 基本原理
对齐代码中的实现与调用，确保变量和函数名的一致性。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/test-harness #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `test_e2e_rate_limit_control.py`
将 `Engine` 的 executor 参数从 `MockWorkExecutor()` 修改为 `TimingWorkExecutor()`。

~~~~~act
patch_file
tests/py/e2e/test_e2e_rate_limit_control.py
~~~~~
~~~~~python
    # 5. Setup the Engine
    engine = Engine(
        solver=NativeSolver(),
        executor=MockWorkExecutor(),
        bus=MessageBus(),
        connector=connector,
    )
~~~~~
~~~~~python
    # 5. Setup the Engine
    engine = Engine(
        solver=NativeSolver(),
        executor=TimingWorkExecutor(),
        bus=MessageBus(),
        connector=connector,
    )
~~~~~

#### Acts 2: 修复 `test_e2e_ttl.py`
将 `controller.pause_with_ttl` 调用修改为 `pause_with_ttl`。

~~~~~act
patch_file
tests/py/e2e/test_e2e_ttl.py
~~~~~
~~~~~python
    # 1. Publish a pause with short TTL (0.2s)
    # We use a slightly longer TTL than the check interval to ensure we catch the pause state
    await controller.pause_with_ttl(scope="global", ttl=0.25)

    @cs.task
~~~~~
~~~~~python
    # 1. Publish a pause with short TTL (0.2s)
    # We use a slightly longer TTL than the check interval to ensure we catch the pause state
    await pause_with_ttl(scope="global", ttl=0.25)

    @cs.task
~~~~~

### 下一步建议
我们已经修复了测试代码。现在应该再次运行测试套件以确认所有测试都已通过。如果通过，我将生成一个 `[COMMIT]` 计划来提交这些重构和修复。
