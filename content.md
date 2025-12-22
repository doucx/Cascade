## [WIP] fix: 纠正 LocalConnector 中的 NameError

### 错误分析
`LocalConnector.subscribe` 方法在返回订阅句柄时，错误地引用了已被重命名的 `_SqliteSubscriptionHandle` 类，导致 `NameError`。这个异常中断了 `engine.run()` 的初始化过程，是导致多个端到端测试失败的根本原因。

### 用户需求
修复 `test_e2e_local_connector.py` 中由于 `NameError` 导致的所有测试失败。

### 评论
这是一个简单的疏忽，但影响深远，凸显了在重构过程中保持代码一致性的重要性。幸运的是，错误信息非常明确，使得定位和修复变得直接。

### 目标
1.  定位 `packages/cascade-connector-local/src/cascade/connectors/local/connector.py` 中的 `subscribe` 方法。
2.  将其 `return` 语句中对 `_SqliteSubscriptionHandle` 的调用更改为 `_LocalSubscriptionHandle`。
3.  确保修复后，相关的端到端测试能够全部通过。

### 基本原理
通过修正这个 `NameError`，`LocalConnector` 将能够正确创建和返回订阅句柄，`Engine` 的初始化将不再中断。这将恢复控制平面的正常功能，并使依赖于它的端到端测试（暂停、恢复、TTL等）能够按预期执行。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #comp/tests #scope/dx #ai/instruct #task/domain/storage #task/object/local-backend #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修正 `subscribe` 方法中的类名引用

我将直接修补 `connector.py` 文件中错误的返回语句。

~~~~~act
patch_file
packages/cascade-connector-local/src/cascade/connectors/local/connector.py
~~~~~
~~~~~python
        await ready_event.wait()
        await self._sync_and_notify(callback)
        return _SqliteSubscriptionHandle(self, task)
~~~~~
~~~~~python
        await ready_event.wait()
        await self._sync_and_notify(callback)
        return _LocalSubscriptionHandle(self, task)
~~~~~

### 下一步建议
这个补丁应该能解决所有报告的测试失败。在您确认此计划后，我建议重新运行测试套件。一旦所有测试通过，我们就可以放心地继续执行路线图的 **步骤 2: [核心机制] 实现基于 UDS 的 Telemetry 事件服务器**。
