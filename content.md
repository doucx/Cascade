这是一个完整的 Git 提交计划，包含了所有对 `LocalBusConnector` 的修复、重构和测试隔离的修改。

## [COMMIT] fix(runtime): Stabilize LocalBusConnector for deterministic E2E testing

### 错误分析
本次提交解决了三个核心问题，这些问题在复杂的异步 E2E 测试环境中尤为明显：
1.  **锁的跨 Event Loop 绑定**: `LocalBusConnector` 的类级 `asyncio.Lock` 在 `pytest-asyncio` 环境中被绑定到第一个 Event Loop。后续测试尝试访问该锁时，触发了 `RuntimeError: ... is bound to a different event loop`。
2.  **启动竞态条件**: `LocalBusConnector.subscribe` 异步分发保留消息。Engine 在订阅后立即进入执行循环，导致它在感知到约束（如 `pause` 或 `rate_limit`）之前就开始调度任务，从而导致时序性测试失败（例如 `test_startup_pause_is_respected`）。
3.  **状态泄漏**: 由于 `LocalBusConnector` 状态是类级别的，测试之间没有清理，导致上一个测试遗留的保留消息或订阅干扰了下一个测试。

### 用户需求
恢复 E2E 测试套件的稳定性，确保内存总线在多进程/多 Loop 自动化测试环境下表现正确，并消除测试脚手架中的重复代码。

### 评论
这次修复至关重要，它为后续的“萤火计划”提供了可靠的底层通信保证。通过将保留消息同步化处理，我们确保了 **状态先于执行** 的原则在 Engine 启动时得到了强制执行。通过全局清理 fixture，我们彻底解决了测试间的状态隔离问题。

### 目标
1.  修复 `LocalBusConnector` 中的锁逻辑，使其能够安全地跨 Event Loop 使用。
2.  确保保留消息在 `subscribe` 调用返回之前被完全同步处理。
3.  将测试脚手架 `InProcessConnector` 替换为 `LocalBusConnector` 的别名。
4.  在 `conftest.py` 中引入自动清理机制，确保测试隔离。
5.  创建一个原子提交来封装所有这些基础设施级别的变更。

### 基本原理
我们采用了异常驱动的锁重置机制，捕获 `RuntimeError` 来检测 Loop 切换，并创建新的 `asyncio.Lock`。同时，将保留消息的处理从异步后台任务提升为同步 `await callback()`，保证了启动时的确定性。

### 标签
#intent/fix #flow/ready #priority/high
#comp/runtime #comp/tests #concept/telemetry #scope/dx
#task/domain/telemetry #task/object/local-bus #task/action/cleanup
#task/state/end

---

### Script

#### Acts 1: 暂存所有修改的文件

~~~~~act
git_add
packages/cascade-runtime/src/cascade/connectors/local.py
tests/py/connectors/test_local_connector.py
tests/py/e2e/harness.py
tests/conftest.py
~~~~~

#### Acts 2: 提交变更

~~~~~act
git_commit
~~~~~
~~~~~text
fix(runtime): Stabilize LocalBusConnector for deterministic E2E testing

The LocalBusConnector required significant fixes to operate reliably in a multi-loop asynchronous testing environment (like pytest-asyncio).

Key fixes:
1.  **Synchronous Retain Delivery**: Changed `subscribe` to synchronously `await` the processing of retained messages. This eliminates a critical race condition where the Engine would start scheduling tasks before receiving a pre-existing constraint (e.g., global pause or rate limit). This restores determinism for all startup control plane tests.
2.  **Cross-Loop Lock Management**: Implemented an exception-driven check within `_get_lock()` to detect if the class-level `asyncio.Lock` is bound to a different Event Loop. It safely re-initializes the lock if a conflict is detected, resolving the persistent `RuntimeError: is bound to a different event loop` failures.
3.  **Test Isolation**: Introduced an `autouse` fixture in `tests/conftest.py` to ensure `LocalBusConnector`'s shared class state (`_subscriptions`, `_retained_messages`) is cleared before and after every test, preventing state leakage and inter-test interference.
4.  **Refactor**: Consolidated `tests/py/e2e/harness.py` by replacing its redundant `InProcessConnector` implementation with an alias to the now-stable `LocalBusConnector`.
~~~~~

### 下一步建议
我们已经完成了对通信基础设施的改造和加固（里程碑 1.1）。现在，我们可以正式开始 **里程碑 1.2：实现“尾递归优化” (引擎连续性重构)**。

这一阶段需要重点修改 `packages/cascade-runtime/src/cascade/runtime/engine.py` 中的 `Engine.run` 和 `_execute_graph` 方法，以实现当任务返回 `LazyResult` 时，Engine 能够优雅地进入下一个循环，而不是直接返回结果或引发异常。
