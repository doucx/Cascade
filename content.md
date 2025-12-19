简要回答
锁的报错依然存在，是因为在 Python 3.10+ 中，直接调用 `lock._get_loop()`（或某些内部方法）如果跨了事件循环会直接抛出 `RuntimeError`，而不仅仅是返回一个不相等的对象。

我将通过 `try...except` 结构安全地检测并重置锁，同时确保通配符匹配逻辑的鲁棒性，彻底解决测试挂起和报错问题。

## [WIP] fix(runtime): 安全处理 LocalBusConnector 的跨 Loop 锁重置

### 错误分析
1.  **锁检测异常**: 在 `_get_lock` 中，`cls._lock._get_loop()` 的调用本身就是触发 `RuntimeError` 的源头。在 pytest 切换测试用例（及其对应的 Event Loop）后，尝试访问旧 Loop 创建的锁会立即报错。
2.  **死锁与超时**: 由于锁的获取失败，导致 `subscribe` 和 `publish` 逻辑在某些用例中无法执行或中途崩溃。这解释了为什么 `test_e2e_rate_limit_control.py` 会卡死（Engine 在等待信号，但信号发布因锁报错而中断）。

### 用户需求
彻底消除 `RuntimeError: ... is bound to a different event loop`，恢复全量 E2E 测试的通过率。

### 评论
处理类级别的异步原语时，必须预期到 `RuntimeError` 的发生。将锁的检查逻辑封装在异常处理中是解决此类兼容性问题的标准模式。

### 目标
1.  重构 `LocalBusConnector._get_lock`，使用 `try...except RuntimeError` 捕获跨 Loop 异常并自动重置。
2.  确保 `_reset_broker_state` 能够彻底清除所有持久化状态，防止测试间的干扰。

### 基本原理
通过捕获异常来检测 Loop 的变动，我们确保了锁始终属于当前活跃的事件循环。这种方式不仅避开了 Python 内部 API 的变动，也保证了在复杂的 pytest 插件环境下运行的稳定性。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/telemetry #task/domain/telemetry #task/object/local-bus #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 健壮的锁获取逻辑

我们将 `_get_lock` 改为异常驱动的重置模式。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/connectors/local.py
~~~~~
~~~~~python
    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        """
        Ensures the lock is bound to the current running event loop.
        This is critical for pytest where each test has its own loop.
        """
        loop = asyncio.get_running_loop()
        if cls._lock is None or cls._lock._get_loop() != loop:
            cls._lock = asyncio.Lock()
        return cls._lock
~~~~~
~~~~~python
    @classmethod
    def _get_lock(cls) -> asyncio.Lock:
        """
        Ensures the lock is bound to the current running event loop.
        This is critical for pytest where each test has its own loop.
        """
        loop = asyncio.get_running_loop()
        try:
            # In modern Python, accessing or using a lock created in a different 
            # loop will raise RuntimeError. We catch this to re-initialize.
            if cls._lock is None or cls._lock._get_loop() != loop:
                cls._lock = asyncio.Lock()
        except RuntimeError:
            cls._lock = asyncio.Lock()
        return cls._lock
~~~~~

#### Acts 2: 完善状态重置

确保锁在重置时被显式设为 `None`。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/connectors/local.py
~~~~~
~~~~~python
    @classmethod
    def _reset_broker_state(cls):
        """Helper for tests to clear the 'broker'."""
        cls._subscriptions.clear()
        cls._retained_messages.clear()
        cls._lock = None  # Force re-creation on next access
~~~~~
~~~~~python
    @classmethod
    def _reset_broker_state(cls):
        """Helper for tests to clear the 'broker'."""
        cls._subscriptions.clear()
        cls._retained_messages.clear()
        # Setting to None ensures _get_lock will create a fresh one for the current loop
        cls._lock = None 
~~~~~

### 下一步建议
现在锁的逻辑已经完全防御化，请重新运行全量测试：
`pytest tests/py/connectors/test_local_connector.py` 
以及
`pytest tests/py/e2e/`

如果通过，说明基座已稳，我们可以真正开始 **里程碑 1.2**：引擎递归改造。
